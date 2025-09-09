import aiohttp
import asyncio
from typing import Dict, Any, Optional
from app.core.config import settings
import logging
from datetime import datetime
from app.middleware.orbo_middleware import OrboAnalysisMiddleware
from app.core.orbo_errors import OrboErrorHandler, OrboErrorMonitor, OrboErrorType
import json

logger = logging.getLogger(__name__)

class OrboSkinAnalysisService:
    def __init__(self, db=None):
        self.base_url = settings.ORBO_BASE_URL
        self.client_id = settings.ORBO_CLIENT_ID
        self.api_key = settings.ORBO_API_KEY
        self.middleware = OrboAnalysisMiddleware(db) if db else None
        self.error_handler = OrboErrorHandler()
        self.error_monitor = OrboErrorMonitor(db) if db else None
        self.timeout = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)
        
    def _get_headers(self, session_id: Optional[str] = None) -> Dict[str, str]:
        headers = {
            'x-client-id': self.client_id,
            'x-api-key': self.api_key,
        }
        if session_id:
            headers['x-session-id'] = session_id
        return headers
    
    async def get_presigned_url(self, file_ext: str = "jpg") -> Dict[str, Any]:
        """Step 1: Get pre-signed URL for image upload"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                url = f"{self.base_url}image"
                params = {'file_ext': file_ext}
                headers = self._get_headers()
                
                async with session.get(url, params=params, headers=headers) as response:
                    if response.status == 200:
                        data = await response.json()
                        return {
                            'success': True,
                            'upload_url': data['data']['uploadSignedUrl'],
                            'session_id': data['data']['session_id']
                        }
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to get presigned URL: {response.status} - {error_text}")
                        
                        # Parse error for user-friendly message
                        try:
                            error_json = json.loads(error_text)
                        except:
                            error_json = {'message': error_text}
                        
                        user_error = self.error_handler.get_user_friendly_error(error_json)
                        return {'success': False, 'error': user_error, 'raw_error': error_text}
                        
        except asyncio.TimeoutError:
            logger.error("Timeout getting presigned URL")
            user_error = self.error_handler.get_user_friendly_error('timeout')
            return {'success': False, 'error': user_error}
        except Exception as e:
            logger.error(f"Error getting presigned URL: {str(e)}")
            user_error = self.error_handler.get_user_friendly_error(str(e))
            return {'success': False, 'error': user_error}
    
    async def upload_image_to_s3(self, upload_url: str, image_data: bytes) -> Dict[str, Any]:
        """Step 2: Upload image to pre-signed URL"""
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                headers = {'Content-Type': 'image/jpeg'}
                
                async with session.put(upload_url, data=image_data, headers=headers) as response:
                    if response.status == 200:
                        return {'success': True}
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to upload image: {response.status} - {error_text}")
                        user_error = self.error_handler.get_user_friendly_error({'message': 'upload_failed'})
                        return {'success': False, 'error': user_error}
                    
        except asyncio.TimeoutError:
            logger.error("Timeout uploading image to S3")
            user_error = self.error_handler.get_user_friendly_error('timeout')
            return {'success': False, 'error': user_error}
        except Exception as e:
            logger.error(f"Error uploading image: {str(e)}")
            user_error = self.error_handler.get_user_friendly_error({'message': 'upload_failed'})
            return {'success': False, 'error': user_error}
    
    async def get_skin_analysis(self, session_id: str, max_retries: int = 10) -> Dict[str, Any]:
        """Step 3: Get skin analysis results with retry logic"""
        try:
            # Use longer timeout for analysis polling
            analysis_timeout = aiohttp.ClientTimeout(total=120, connect=10, sock_read=30)
            async with aiohttp.ClientSession(timeout=analysis_timeout) as session:
                url = f"{self.base_url}analysis"
                headers = self._get_headers(session_id)
                
                for attempt in range(max_retries):
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('success'):
                                return self._process_analysis_response(data)
                            else:
                                # Check for specific ORBO errors
                                if 'error' in data:
                                    user_error = self.error_handler.get_user_friendly_error(data)
                                    logger.error(f"ORBO analysis error: {data}")
                                    return {'success': False, 'error': user_error, 'orbo_error': data}
                        elif response.status == 400:
                            # Bad request - likely face detection issue
                            error_data = await response.json()
                            user_error = self.error_handler.get_user_friendly_error(error_data)
                            logger.warning(f"ORBO validation error: {error_data}")
                            return {'success': False, 'error': user_error, 'validation_error': True}
                        else:
                            error_text = await response.text()
                            logger.info(f"Analysis processing (attempt {attempt + 1}/{max_retries}): {response.status}")
                        
                        # Wait before retry (analysis might still be processing)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3)
                
                # Timeout after all retries
                user_error = self.error_handler.get_user_friendly_error('timeout')
                return {'success': False, 'error': user_error, 'timeout': True}
                
        except asyncio.TimeoutError:
            logger.error("Timeout getting skin analysis")
            user_error = self.error_handler.get_user_friendly_error('timeout')
            return {'success': False, 'error': user_error}
        except Exception as e:
            logger.error(f"Error getting skin analysis: {str(e)}")
            user_error = self.error_handler.get_user_friendly_error(str(e))
            return {'success': False, 'error': user_error}
    
    def _process_analysis_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and standardize the ORBO response for SkinSense"""
        try:
            analysis_data = data['data']
            
            # Extract scores and organize by parameter
            scores = {}
            for item in analysis_data['output_score']:
                scores[item['concern']] = {
                    'score': item['score'],
                    'risk_level': item['riskLevel']
                }
            
            # Map to SkinSense parameters (10 key metrics from CLAUDE.md)
            # ORBO output_score provides scores where 100 = best, 0 = worst (confirmed by ORBO AI)
            skinsense_metrics = {
                'overall_skin_health_score': scores.get('skin_health', {}).get('score', 0),
                'hydration': scores.get('hydration', {}).get('score', 0),
                'smoothness': scores.get('smoothness', {}).get('score', 0),
                'radiance': scores.get('radiance', {}).get('score', 0) if 'radiance' in scores else scores.get('skin_dullness', {}).get('score', 0),  # Use radiance directly or dullness as fallback
                'dark_spots': scores.get('dark_spots', {}).get('score', 0),   # Higher score = better (less dark spots)
                'firmness': scores.get('firmness', {}).get('score', 0),
                'fine_lines_wrinkles': scores.get('fine_lines_wrinkles', {}).get('score', 0) if 'fine_lines_wrinkles' in scores else scores.get('face_wrinkles', {}).get('score', 0),  # Higher score = better (fewer wrinkles)
                'acne': scores.get('acne', {}).get('score', 0),  # Higher score = better (less acne)
                'dark_circles': scores.get('dark_circles', {}).get('score', 0) if 'dark_circles' in scores else scores.get('dark_circle', {}).get('score', 0),  # Higher score = better (less dark circles)
                'redness': scores.get('redness', {}).get('score', 0),  # Higher score = better (less redness)
            }
            
            return {
                'success': True,
                'metrics': skinsense_metrics,
                'detailed_scores': scores,
                'input_image': analysis_data.get('input_image'),
                'annotations': analysis_data.get('annotations', {}),
                'raw_response': data  # Keep original for debugging
            }
        except Exception as e:
            logger.error(f"Error processing analysis response: {str(e)}")
            return {
                'success': False,
                'error': f'Failed to process analysis response: {str(e)}'
            }
    
    async def complete_analysis_pipeline(self, image_data: bytes, user_id: str = None) -> Dict[str, Any]:
        """Complete 3-step analysis pipeline with comprehensive error handling"""
        logger.info("Starting ORBO analysis pipeline")
        
        # Validate image data
        if not image_data:
            user_error = self.error_handler.get_user_friendly_error({'message': 'invalid_image'})
            return {'success': False, 'error': user_error}
        
        # Check image size (should be at least 500x500)
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(image_data))
            if img.width < 500 or img.height < 500:
                user_error = self.error_handler.get_user_friendly_error({'message': 'Image Resolution is too small'})
                return {'success': False, 'error': user_error, 'image_size': f"{img.width}x{img.height}"}
        except Exception as e:
            logger.warning(f"Could not validate image size: {e}")
        
        # Step 1: Get presigned URL
        logger.info("Step 1: Getting presigned URL")
        presigned_result = await self.get_presigned_url()
        if not presigned_result['success']:
            if self.error_monitor and user_id:
                await self.error_monitor.log_error(
                    user_id, 
                    OrboErrorType.PRESIGNED_URL_FAILED,
                    presigned_result.get('raw_error', {})
                )
            return presigned_result
        
        upload_url = presigned_result['upload_url']
        session_id = presigned_result['session_id']
        logger.info(f"Got presigned URL and session ID: {session_id}")
        
        # Step 2: Upload image
        logger.info("Step 2: Uploading image to S3")
        upload_result = await self.upload_image_to_s3(upload_url, image_data)
        if not upload_result['success']:
            if self.error_monitor and user_id:
                await self.error_monitor.log_error(
                    user_id,
                    OrboErrorType.UPLOAD_FAILED,
                    upload_result.get('error', {}),
                    session_id
                )
            return upload_result
        logger.info("Image uploaded successfully")
        
        # Step 3: Get analysis (with retries for processing time)
        logger.info("Step 3: Getting skin analysis (this may take up to 30 seconds)")
        analysis_result = await self.get_skin_analysis(session_id)
        
        if analysis_result['success']:
            analysis_result['session_id'] = session_id
            logger.info("Analysis completed successfully")
        else:
            logger.error(f"Analysis failed: {analysis_result.get('error')}")
            
            # Log error for monitoring
            if self.error_monitor and user_id:
                error_type = OrboErrorType.ANALYSIS_FAILED
                if analysis_result.get('validation_error'):
                    # Parse specific validation error
                    error_type = self.error_handler.parse_orbo_error(
                        analysis_result.get('orbo_error', {})
                    )
                elif analysis_result.get('timeout'):
                    error_type = OrboErrorType.TIMEOUT
                
                await self.error_monitor.log_error(
                    user_id,
                    error_type,
                    analysis_result.get('orbo_error', analysis_result.get('error', {})),
                    session_id
                )
            
        return analysis_result
    
    async def complete_analysis_pipeline_with_middleware(
        self, 
        image_data: bytes, 
        user_id: str,
        image_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Complete analysis pipeline with data sovereignty middleware
        """
        
        if not self.middleware:
            raise ValueError("Middleware not initialized. Pass database instance to constructor.")
        
        # STEP 0: Pre-analysis middleware (store in our DB first)
        pre_result = await self.middleware.pre_analysis_middleware(
            user_id, 
            image_data, 
            image_metadata or {}
        )
        
        if not pre_result['success']:
            return {'success': False, 'error': 'Pre-analysis processing failed'}
        
        internal_analysis_id = pre_result['internal_analysis_id']
        
        try:
            # STEP 1: Get presigned URL from ORBO
            presigned_result = await self.get_presigned_url()
            if not presigned_result['success']:
                await self.middleware.mark_analysis_failed(internal_analysis_id, 'presigned_url_failed')
                return presigned_result
            
            upload_url = presigned_result['upload_url']
            orbo_session_id = presigned_result['session_id']
            
            # STEP 2: Upload image to ORBO S3
            upload_success = await self.upload_image_to_s3(upload_url, image_data)
            if not upload_success:
                await self.middleware.mark_analysis_failed(internal_analysis_id, 'upload_failed')
                return {'success': False, 'error': 'Failed to upload image to ORBO'}
            
            # STEP 3: Get analysis from ORBO
            orbo_analysis_result = await self.get_skin_analysis(orbo_session_id)
            
            # STEP 4: Post-analysis middleware (update our DB with results)
            post_result = await self.middleware.post_analysis_middleware(
                internal_analysis_id,
                orbo_analysis_result,
                orbo_session_id
            )
            
            # Combine results
            final_result = {
                **orbo_analysis_result,
                'internal_analysis_id': internal_analysis_id,
                'database_stored': pre_result['database_record_created'],
                'database_updated': post_result.get('database_updated', False),
                'data_sovereignty_compliant': True
            }
            
            return final_result
            
        except Exception as e:
            # Mark analysis as failed in our database
            await self.middleware.mark_analysis_failed(internal_analysis_id, str(e))
            logger.error(f"Analysis pipeline failed: {e}")
            return {'success': False, 'error': str(e)}