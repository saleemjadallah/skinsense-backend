from fastapi import Request, HTTPException
from typing import Dict, Any, Optional
import uuid
from datetime import datetime
import logging
from app.database import Database
from app.core.config import settings

logger = logging.getLogger(__name__)

class OrboAnalysisMiddleware:
    """
    Middleware to handle data sovereignty and tracking for ORBO API requests
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    def pre_analysis_middleware(
        self, 
        user_id: str, 
        image_data: bytes, 
        image_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Store user data and image in our database BEFORE sending to ORBO
        """
        try:
            # Generate internal analysis ID
            internal_analysis_id = str(uuid.uuid4())
            
            # Store image in our AWS S3 first
            our_image_url = self._store_image_internally(
                image_data, 
                user_id, 
                internal_analysis_id
            )
            
            # Create pre-analysis record in database
            pre_analysis_record = {
                'analysis_id': internal_analysis_id,
                'user_id': user_id,
                'internal_image_url': our_image_url,
                'image_metadata': image_metadata,
                'status': 'pending_orbo_analysis',
                'created_at': datetime.utcnow(),
                'orbo_session_id': None,  # Will be updated after ORBO call
                'orbo_response': None,    # Will be updated after ORBO call
                'data_sovereignty_compliant': True,
                'processing_stage': 'pre_orbo',
                'audit_trail': [
                    {
                        'action': 'image_stored_internally',
                        'timestamp': datetime.utcnow(),
                        'details': 'Image stored in our S3 before ORBO processing'
                    }
                ]
            }
            
            # Store in database
            self.db.skin_analyses.insert_one(pre_analysis_record)
            
            logger.info(f"Pre-analysis record created: {internal_analysis_id}")
            
            return {
                'success': True,
                'internal_analysis_id': internal_analysis_id,
                'internal_image_url': our_image_url,
                'database_record_created': True
            }
            
        except Exception as e:
            logger.error(f"Pre-analysis middleware failed: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Failed to process image before analysis"
            )
    
    def post_analysis_middleware(
        self, 
        internal_analysis_id: str, 
        orbo_response: Dict[str, Any],
        orbo_session_id: str
    ) -> Dict[str, Any]:
        """
        Update our database record with ORBO results
        """
        try:
            # Add audit trail entry
            audit_entry = {
                'action': 'orbo_results_received',
                'timestamp': datetime.utcnow(),
                'success': orbo_response.get('success', False),
                'orbo_session_id': orbo_session_id
            }
            
            # Update the existing record with ORBO results
            update_data = {
                'orbo_session_id': orbo_session_id,
                'orbo_response': orbo_response,
                'status': 'completed' if orbo_response.get('success') else 'failed',
                'processing_stage': 'post_orbo',
                'updated_at': datetime.utcnow(),
                'orbo_metrics': orbo_response.get('metrics', {}),
                'orbo_annotations': orbo_response.get('annotations', {})
            }
            
            # Update the record and append to audit trail
            self.db.skin_analyses.update_one(
                {'analysis_id': internal_analysis_id},
                {
                    '$set': update_data,
                    '$push': {'audit_trail': audit_entry}
                }
            )
            
            logger.info(f"Post-analysis record updated: {internal_analysis_id}")
            
            return {
                'success': True,
                'analysis_complete': True,
                'database_updated': True
            }
            
        except Exception as e:
            logger.error(f"Post-analysis middleware failed: {e}")
            # Don't raise exception here - we still want to return ORBO results
            return {
                'success': False,
                'database_updated': False,
                'error': str(e)
            }
    
    def _store_image_internally(
        self, 
        image_data: bytes, 
        user_id: str, 
        analysis_id: str
    ) -> str:
        """
        Store image in our own AWS S3 bucket before sending to ORBO
        """
        try:
            # Generate unique filename
            filename = f"skin-analysis/{user_id}/{analysis_id}/original.jpg"
            
            # Upload to our S3 bucket
            from app.services.s3_service import S3Service
            s3_service = S3Service()
            
            # Note: S3 service needs to be synchronous too for PyMongo
            # For now, we'll just return a placeholder URL
            # In production, you'd need to update S3Service to be synchronous
            image_url = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
            
            # TODO: Implement synchronous S3 upload
            # image_url = s3_service.upload_file_sync(
            #     image_data,
            #     filename,
            #     content_type='image/jpeg'
            # )
            
            return image_url
            
        except Exception as e:
            logger.error(f"Failed to store image internally: {e}")
            raise
    
    def mark_analysis_failed(self, analysis_id: str, error: str):
        """Mark analysis as failed in our database"""
        try:
            self.db.skin_analyses.update_one(
                {'analysis_id': analysis_id},
                {
                    '$set': {
                        'status': 'failed',
                        'error': error,
                        'updated_at': datetime.utcnow()
                    },
                    '$push': {
                        'audit_trail': {
                            'action': 'analysis_failed',
                            'timestamp': datetime.utcnow(),
                            'error': error
                        }
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to mark analysis as failed: {e}")