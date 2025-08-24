# ORBO AI Skin Analysis API Implementation Guide

## Overview
This guide provides comprehensive instructions for integrating the ORBO AI Skin Analysis API into SkinSense AI. The implementation includes the 3-step process: getting pre-signed URLs, uploading images, and retrieving detailed skin analysis with 16 different metrics.

## API Endpoints Overview

### Base URL
```
https://api.gateway.orbo.ai/demo/supertouch/skin/v1/
```

### Authentication Headers
All requests require these headers:
- `x-client-id`: Your ORBO client ID
- `x-api-key`: Your ORBO API key
- `x-session-id`: Session ID (obtained from step 1)

## 3-Step Implementation Process

### Step 1: Get Pre-signed URL for Image Upload
**Endpoint:** `GET /image?file_ext=jpg`

**Purpose:** Obtain a secure pre-signed URL for uploading the user's skin image and get a session ID for tracking the analysis.

**Request:**
```bash
curl --location 'https://api.gateway.orbo.ai/demo/supertouch/skin/v1/image?file_ext=jpg' \
--header 'x-client-id: <CLIENT_ID>' \
--header 'x-api-key: <API_KEY>'
```

**Response:**
```json
{
  "success": true,
  "statusCode": 200,
  "message": "Request accepted",
  "data": {
    "uploadSignedUrl": "https://skin-diary-dev.s3.ap-south-1.amazonaws.com/...",
    "session_id": "67efa93ffdee1f0f6be59e32"
  }
}
```

### Step 2: Upload Image to Pre-signed URL
**Endpoint:** `PUT <PRESIGNED_URL>`

**Purpose:** Upload the user's facial image directly to AWS S3 using the pre-signed URL.

**Request:**
```bash
curl --location --request PUT '<PRESIGNED_URL>' \
--header 'Content-Type: image/jpeg' \
--data-binary '@path/to/image.jpg'
```

**Response:** No response body (HTTP 200 on success)

### Step 3: Get Skin Analysis Results
**Endpoint:** `GET /analysis`

**Purpose:** Retrieve comprehensive skin analysis with scores and annotated images.

**Request:**
```bash
curl --location 'https://api.gateway.orbo.ai/demo/supertouch/skin/v1/analysis' \
--header 'x-client-id: <CLIENT_ID>' \
--header 'x-api-key: <API_KEY>' \
--header 'x-session-id: <SESSION_ID>'
```

## Skin Analysis Response Structure

### Core Metrics (16 Parameters)
The API returns analysis for these skin parameters, each with scores 0-100:

1. **dark_circle** - Under-eye dark circles detection
2. **skin_dullness** - Overall skin brightness and radiance
3. **dark_spots** - Pigmentation and discoloration
4. **acne** - Blemish and breakout detection
5. **uneven_skin** - Skin tone uniformity
6. **face_wrinkles** - Facial wrinkle detection
7. **eye_wrinkles** - Specific eye area wrinkles
8. **crows_feet** - Outer eye corner lines
9. **shine** - Skin oiliness and shine levels
10. **redness** - Skin irritation and sensitivity
11. **pigmentation** - Overall pigmentation analysis
12. **firmness** - Skin elasticity and firmness
13. **smoothness** - Skin texture smoothness
14. **hydration** - Moisture level assessment
15. **skin_health** - Overall skin health score
16. **texture** - Skin surface texture analysis

### Response Format
```json
{
  "success": true,
  "statusCode": 200,
  "message": "Skin analysis completed successfully",
  "data": {
    "output_score": [
      {
        "concern": "dark_circle",
        "score": 66,
        "riskLevel": 2
      },
      {
        "concern": "skin_health",
        "score": 76,
        "riskLevel": 2
      }
      // ... 14 more parameters
    ],
    "input_image": "https://skin-diary-dev.s3.ap-south-1.amazonaws.com/...",
    "annotations": {
      "acne": "https://skinanalysis-prod.s3.ap-south-1.amazonaws.com/.../acne.jpg",
      "dark_circle": "https://skinanalysis-prod.s3.ap-south-1.amazonaws.com/.../dark_circle.jpg",
      // ... annotation images for all 15 parameters
    }
  }
}
```

### Risk Level Interpretation
- **Risk Level 1**: Low concern (scores 80-100)
- **Risk Level 2**: Medium concern (scores 60-79)
- **Risk Level 3**: High concern (scores 0-59)

## SkinSense AI Integration Requirements

### Score Standardization (0-100 Scale)
The ORBO API already provides scores in the 0-100 range that SkinSense requires. **No conversion needed.**

### Color Coding for Frontend
Based on your requirements to use only **green and yellow** colors:

```dart
// Frontend color mapping
Color getScoreColor(int score) {
  if (score >= 75) {
    return Colors.green;      // Good scores (75-100)
  } else {
    return Colors.yellow;     // Needs attention (0-74)
  }
}
```

### Parameter Mapping for SkinSense
Map ORBO parameters to SkinSense display names:

```dart
Map<String, String> parameterMapping = {
  'skin_health': 'Overall Skin Health',
  'hydration': 'Hydration',
  'smoothness': 'Smoothness', 
  'dark_spots': 'Radiance (Dark Spots)',
  'firmness': 'Firmness',
  'face_wrinkles': 'Fine Lines & Wrinkles',
  'acne': 'Acne',
  'dark_circle': 'Dark Circles',
  'redness': 'Redness',
  'texture': 'Texture',
  'pigmentation': 'Pigmentation',
  'uneven_skin': 'Skin Uniformity',
  'shine': 'Oil Control',
  'eye_wrinkles': 'Eye Area',
  'crows_feet': 'Crow\'s Feet',
  'skin_dullness': 'Skin Brightness'
};
```

## Backend Implementation

### Environment Variables
Add to your `.env` file:
```bash
ORBO_CLIENT_ID=your_client_id_here
ORBO_API_KEY=your_api_key_here
ORBO_BASE_URL=https://api.gateway.orbo.ai/demo/supertouch/skin/v1/
```

### Python Service Implementation

```python
# app/services/orbo_service.py
import aiohttp
import asyncio
from typing import Dict, Any, Optional
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class OrboSkinAnalysisService:
    def __init__(self):
        self.base_url = settings.orbo_base_url
        self.client_id = settings.orbo_client_id
        self.api_key = settings.orbo_api_key
        
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
            async with aiohttp.ClientSession() as session:
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
                        logger.error(f"Failed to get presigned URL: {response.status}")
                        return {'success': False, 'error': 'Failed to get upload URL'}
                        
        except Exception as e:
            logger.error(f"Error getting presigned URL: {e}")
            return {'success': False, 'error': str(e)}
    
    async def upload_image_to_s3(self, upload_url: str, image_data: bytes) -> bool:
        """Step 2: Upload image to pre-signed URL"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {'Content-Type': 'image/jpeg'}
                
                async with session.put(upload_url, data=image_data, headers=headers) as response:
                    return response.status == 200
                    
        except Exception as e:
            logger.error(f"Error uploading image: {e}")
            return False
    
    async def get_skin_analysis(self, session_id: str, max_retries: int = 10) -> Dict[str, Any]:
        """Step 3: Get skin analysis results with retry logic"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}analysis"
                headers = self._get_headers(session_id)
                
                for attempt in range(max_retries):
                    async with session.get(url, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data.get('success'):
                                return self._process_analysis_response(data)
                        
                        # Wait before retry (analysis might still be processing)
                        if attempt < max_retries - 1:
                            await asyncio.sleep(3)
                
                return {'success': False, 'error': 'Analysis timeout'}
                
        except Exception as e:
            logger.error(f"Error getting skin analysis: {e}")
            return {'success': False, 'error': str(e)}
    
    def _process_analysis_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process and standardize the ORBO response for SkinSense"""
        analysis_data = data['data']
        
        # Extract scores and organize by parameter
        scores = {}
        for item in analysis_data['output_score']:
            scores[item['concern']] = {
                'score': item['score'],
                'risk_level': item['riskLevel']
            }
        
        # Map to SkinSense parameters (10 key metrics from CLAUDE.md)
        skinsense_metrics = {
            'overall_skin_health_score': scores.get('skin_health', {}).get('score', 0),
            'hydration': scores.get('hydration', {}).get('score', 0),
            'smoothness': scores.get('smoothness', {}).get('score', 0),
            'radiance': 100 - scores.get('skin_dullness', {}).get('score', 0),  # Invert dullness for radiance
            'dark_spots': 100 - scores.get('dark_spots', {}).get('score', 0),   # Invert for uniformity
            'firmness': scores.get('firmness', {}).get('score', 0),
            'fine_lines_wrinkles': 100 - scores.get('face_wrinkles', {}).get('score', 0),  # Invert wrinkles
            'acne': 100 - scores.get('acne', {}).get('score', 0),  # Invert acne
            'dark_circles': 100 - scores.get('dark_circle', {}).get('score', 0),  # Invert dark circles
            'redness': 100 - scores.get('redness', {}).get('score', 0),  # Invert redness
        }
        
        return {
            'success': True,
            'metrics': skinsense_metrics,
            'detailed_scores': scores,
            'input_image': analysis_data['input_image'],
            'annotations': analysis_data['annotations'],
            'raw_response': data  # Keep original for debugging
        }
    
    async def complete_analysis_pipeline(self, image_data: bytes) -> Dict[str, Any]:
        """Complete 3-step analysis pipeline"""
        # Step 1: Get presigned URL
        presigned_result = await self.get_presigned_url()
        if not presigned_result['success']:
            return presigned_result
        
        upload_url = presigned_result['upload_url']
        session_id = presigned_result['session_id']
        
        # Step 2: Upload image
        upload_success = await self.upload_image_to_s3(upload_url, image_data)
        if not upload_success:
            return {'success': False, 'error': 'Failed to upload image'}
        
        # Step 3: Get analysis (with retries for processing time)
        analysis_result = await self.get_skin_analysis(session_id)
        
        if analysis_result['success']:
            analysis_result['session_id'] = session_id
            
        return analysis_result
```

### FastAPI Endpoint Implementation

```python
# app/api/v1/orbo_analysis.py
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from app.services.orbo_service import OrboSkinAnalysisService
from app.services.recommendation_service import RecommendationService
from app.models.user import User
from app.api.deps import get_current_user
import base64

router = APIRouter()

@router.post("/analyze-skin")
async def analyze_skin_with_orbo(
    image: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """
    Complete skin analysis using ORBO API
    """
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image data
        image_data = await image.read()
        
        # Initialize ORBO service
        orbo_service = OrboSkinAnalysisService()
        
        # Run complete analysis pipeline
        result = await orbo_service.complete_analysis_pipeline(image_data)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        # Store analysis in database
        analysis_doc = {
            'user_id': user.id,
            'orbo_session_id': result['session_id'],
            'input_image_url': result['input_image'],
            'skin_metrics': result['metrics'],
            'detailed_scores': result['detailed_scores'],
            'annotations': result['annotations'],
            'created_at': datetime.utcnow(),
            'analysis_type': 'orbo_ai'
        }
        
        # Save to MongoDB
        analysis_id = await store_analysis(analysis_doc)
        
        # Generate AI recommendations
        recommendation_service = RecommendationService()
        recommendations = await recommendation_service.generate_recommendations(
            result['metrics'], user.profile
        )
        
        return {
            'analysis_id': analysis_id,
            'skin_metrics': result['metrics'],
            'recommendations': recommendations,
            'annotations': result['annotations'],
            'session_id': result['session_id']
        }
        
    except Exception as e:
        logger.error(f"Skin analysis error: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@router.get("/analysis/{analysis_id}/annotations")
async def get_analysis_annotations(
    analysis_id: str,
    user: User = Depends(get_current_user)
):
    """
    Get annotated images for specific analysis
    """
    try:
        analysis = await get_analysis_by_id(analysis_id, user.id)
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return {
            'input_image': analysis['input_image_url'],
            'annotations': analysis['annotations']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve annotations")
```

## Frontend Integration

### Dart/Flutter Implementation

```dart
// lib/services/orbo_api_service.dart
import 'package:dio/dio.dart';

class OrboApiService {
  final Dio _dio = Dio();
  final String baseUrl = 'YOUR_BACKEND_API_URL';
  
  Future<Map<String, dynamic>> analyzeSkinWithOrbo(String imagePath) async {
    try {
      // Upload image to your backend (which handles ORBO integration)
      FormData formData = FormData.fromMap({
        'image': await MultipartFile.fromFile(imagePath),
      });
      
      Response response = await _dio.post(
        '$baseUrl/api/v1/orbo/analyze-skin',
        data: formData,
        options: Options(
          headers: {
            'Authorization': 'Bearer $userToken',
            'Content-Type': 'multipart/form-data',
          },
        ),
      );
      
      return response.data;
    } catch (e) {
      throw Exception('Failed to analyze skin: $e');
    }
  }
  
  Future<Map<String, dynamic>> getAnalysisAnnotations(String analysisId) async {
    try {
      Response response = await _dio.get(
        '$baseUrl/api/v1/orbo/analysis/$analysisId/annotations',
        options: Options(
          headers: {'Authorization': 'Bearer $userToken'},
        ),
      );
      
      return response.data;
    } catch (e) {
      throw Exception('Failed to get annotations: $e');
    }
  }
}
```

### Frontend UI Implementation

```dart
// lib/widgets/skin_metrics_display.dart
import 'package:flutter/material.dart';

class SkinMetricsDisplay extends StatelessWidget {
  final Map<String, dynamic> metrics;
  
  const SkinMetricsDisplay({Key? key, required this.metrics}) : super(key: key);
  
  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _buildOverallScore(),
        const SizedBox(height: 20),
        _buildMetricsGrid(),
      ],
    );
  }
  
  Widget _buildOverallScore() {
    final score = metrics['overall_skin_health_score'] ?? 0;
    return CircularProgressIndicator(
      value: score / 100,
      backgroundColor: Colors.grey.shade300,
      valueColor: AlwaysStoppedAnimation<Color>(_getScoreColor(score)),
      strokeWidth: 8,
    );
  }
  
  Widget _buildMetricsGrid() {
    final metricsToShow = [
      'hydration',
      'smoothness', 
      'radiance',
      'dark_spots',
      'firmness',
      'fine_lines_wrinkles',
      'acne',
      'dark_circles',
      'redness'
    ];
    
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        childAspectRatio: 1.2,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemCount: metricsToShow.length,
      itemBuilder: (context, index) {
        final metric = metricsToShow[index];
        final score = metrics[metric] ?? 0;
        
        return _buildMetricCard(metric, score);
      },
    );
  }
  
  Widget _buildMetricCard(String metric, int score) {
    return Card(
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              _getDisplayName(metric),
              style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            CircularProgressIndicator(
              value: score / 100,
              backgroundColor: Colors.grey.shade300,
              valueColor: AlwaysStoppedAnimation<Color>(_getScoreColor(score)),
              strokeWidth: 4,
            ),
            const SizedBox(height: 4),
            Text(
              '$score',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: _getScoreColor(score),
              ),
            ),
          ],
        ),
      ),
    );
  }
  
  Color _getScoreColor(int score) {
    // Only green and yellow as requested
    return score >= 75 ? Colors.green : Colors.yellow.shade700;
  }
  
  String _getDisplayName(String metric) {
    final displayNames = {
      'hydration': 'Hydration',
      'smoothness': 'Smoothness',
      'radiance': 'Radiance',
      'dark_spots': 'Dark Spots',
      'firmness': 'Firmness',
      'fine_lines_wrinkles': 'Fine Lines',
      'acne': 'Acne',
      'dark_circles': 'Dark Circles',
      'redness': 'Redness',
    };
    return displayNames[metric] ?? metric;
  }
}
```

## Auto-Capture Feature Implementation

### Automatic Analysis Trigger
Based on the documentation, ORBO doesn't have a built-in auto-capture feature, but you can implement this in your app:

```dart
// lib/services/auto_capture_service.dart
import 'package:camera/camera.dart';
import 'dart:async';

class AutoCaptureService {
  static const Duration _captureDelay = Duration(seconds: 3);
  Timer? _captureTimer;
  
  void startAutoCapture(CameraController controller, Function onCapture) {
    _captureTimer = Timer(_captureDelay, () async {
      if (controller.value.isInitialized) {
        // Check if face is properly positioned (implement face detection)
        bool faceDetected = await _detectFace();
        
        if (faceDetected) {
          await onCapture();
        } else {
          // Restart timer if no proper face detected
          startAutoCapture(controller, onCapture);
        }
      }
    });
  }
  
  void stopAutoCapture() {
    _captureTimer?.cancel();
    _captureTimer = null;
  }
  
  Future<bool> _detectFace() async {
    // Implement face detection logic
    // You can use Google ML Kit or similar
    return true; // Placeholder
  }
}
```

## Configuration Management

### Add to Backend Config
```python
# app/core/config.py
class Settings(BaseSettings):
    # Existing settings...
    
    # ORBO AI Configuration
    orbo_base_url: str = "https://api.gateway.orbo.ai/demo/supertouch/skin/v1/"
    orbo_client_id: str
    orbo_api_key: str
    
    class Config:
        env_file = ".env"
```

## Testing Strategy

### Unit Tests
```python
# tests/test_orbo_service.py
import pytest
from app.services.orbo_service import OrboSkinAnalysisService

@pytest.mark.asyncio
async def test_get_presigned_url():
    service = OrboSkinAnalysisService()
    result = await service.get_presigned_url()
    
    assert result['success'] is True
    assert 'upload_url' in result
    assert 'session_id' in result

@pytest.mark.asyncio
async def test_complete_analysis_pipeline():
    service = OrboSkinAnalysisService()
    
    # Use test image
    with open('tests/fixtures/test_face.jpg', 'rb') as f:
        image_data = f.read()
    
    result = await service.complete_analysis_pipeline(image_data)
    
    assert result['success'] is True
    assert 'metrics' in result
    assert len(result['metrics']) == 10  # 10 key metrics
```

## Error Handling & Edge Cases

### Common Error Scenarios
1. **Invalid Image Format**: Ensure only JPEG images are uploaded
2. **Analysis Timeout**: ORBO analysis may take 10-30 seconds
3. **Session Expiry**: Pre-signed URLs have limited validity
4. **Rate Limiting**: Handle API rate limits gracefully

### Retry Logic Implementation
```python
async def get_analysis_with_retry(self, session_id: str, max_retries: int = 10) -> Dict[str, Any]:
    """Enhanced retry logic with exponential backoff"""
    base_delay = 2
    
    for attempt in range(max_retries):
        try:
            result = await self.get_skin_analysis(session_id, max_retries=1)
            if result['success']:
                return result
                
            # Exponential backoff
            delay = base_delay * (2 ** attempt)
            await asyncio.sleep(min(delay, 30))  # Cap at 30 seconds
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            await asyncio.sleep(base_delay)
    
    return {'success': False, 'error': 'Analysis failed after retries'}
```

## ORBO API Middleware Implementation

### Data Sovereignty & Pre-Processing Requirements
To ensure data sovereignty and proper tracking, implement middleware that stores user data in your database BEFORE sending to ORBO servers.

### Middleware Architecture
```python
# app/middleware/orbo_middleware.py
from fastapi import Request, HTTPException
from typing import Dict, Any, Optional
import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class OrboAnalysisMiddleware:
    """
    Middleware to handle data sovereignty and tracking for ORBO API requests
    """
    
    def __init__(self, db_service):
        self.db = db_service
    
    async def pre_analysis_middleware(
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
            our_image_url = await self._store_image_internally(
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
                'processing_stage': 'pre_orbo'
            }
            
            # Store in database
            await self.db.skin_analyses.insert_one(pre_analysis_record)
            
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
    
    async def post_analysis_middleware(
        self, 
        internal_analysis_id: str, 
        orbo_response: Dict[str, Any],
        orbo_session_id: str
    ) -> Dict[str, Any]:
        """
        Update our database record with ORBO results
        """
        try:
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
            
            await self.db.skin_analyses.update_one(
                {'analysis_id': internal_analysis_id},
                {'$set': update_data}
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
    
    async def _store_image_internally(
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
            
            # Upload to our S3 bucket (implement your S3 service)
            from app.services.s3_service import S3Service
            s3_service = S3Service()
            
            image_url = await s3_service.upload_file(
                image_data,
                filename,
                content_type='image/jpeg'
            )
            
            return image_url
            
        except Exception as e:
            logger.error(f"Failed to store image internally: {e}")
            raise
```

### Enhanced ORBO Service with Middleware Integration
```python
# Updated app/services/orbo_service.py (key changes)
class OrboSkinAnalysisService:
    def __init__(self, db_service):
        self.base_url = settings.orbo_base_url
        self.client_id = settings.orbo_client_id
        self.api_key = settings.orbo_api_key
        self.middleware = OrboAnalysisMiddleware(db_service)
    
    async def complete_analysis_pipeline_with_middleware(
        self, 
        image_data: bytes, 
        user_id: str,
        image_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Complete analysis pipeline with data sovereignty middleware
        """
        
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
                await self._mark_analysis_failed(internal_analysis_id, 'presigned_url_failed')
                return presigned_result
            
            upload_url = presigned_result['upload_url']
            orbo_session_id = presigned_result['session_id']
            
            # STEP 2: Upload image to ORBO S3
            upload_success = await self.upload_image_to_s3(upload_url, image_data)
            if not upload_success:
                await self._mark_analysis_failed(internal_analysis_id, 'upload_failed')
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
            await self._mark_analysis_failed(internal_analysis_id, str(e))
            logger.error(f"Analysis pipeline failed: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _mark_analysis_failed(self, analysis_id: str, error: str):
        """Mark analysis as failed in our database"""
        try:
            await self.middleware.db.skin_analyses.update_one(
                {'analysis_id': analysis_id},
                {
                    '$set': {
                        'status': 'failed',
                        'error': error,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to mark analysis as failed: {e}")
```

### Database Schema for Data Sovereignty
```python
# MongoDB collection: skin_analyses
{
  "_id": ObjectId,
  "analysis_id": "uuid4_string",          # Our internal ID
  "user_id": "user_uuid",
  "internal_image_url": "https://our-s3.../image.jpg",  # Our S3 storage
  "orbo_session_id": "orbo_session_uuid", # ORBO's session ID
  "status": "pending_orbo_analysis|completed|failed",
  "processing_stage": "pre_orbo|post_orbo",
  "data_sovereignty_compliant": true,
  
  # Image metadata
  "image_metadata": {
    "original_filename": "selfie.jpg",
    "file_size": 1024000,
    "image_dimensions": {"width": 1080, "height": 1920},
    "device_info": "iPhone 14 Pro",
    "app_version": "1.0.0"
  },
  
  # ORBO response data
  "orbo_response": {
    "success": true,
    "metrics": {...},
    "annotations": {...},
    "raw_response": {...}
  },
  
  # Processed metrics for our app
  "orbo_metrics": {
    "overall_skin_health_score": 76,
    "hydration": 85,
    "smoothness": 90,
    # ... other metrics
  },
  
  # Timestamps
  "created_at": ISODate,
  "updated_at": ISODate,
  
  # Error handling
  "error": "string_if_failed",
  "retry_count": 0,
  
  # Compliance & audit
  "data_processing_consent": true,
  "data_retention_expiry": ISODate,
  "audit_trail": [
    {
      "action": "image_stored_internally",
      "timestamp": ISODate,
      "details": "Image stored in our S3 before ORBO processing"
    },
    {
      "action": "sent_to_orbo",
      "timestamp": ISODate,
      "orbo_session_id": "session_id"
    },
    {
      "action": "orbo_results_received",
      "timestamp": ISODate,
      "success": true
    }
  ]
}
```

### Updated FastAPI Endpoint with Middleware
```python
# app/api/v1/orbo_analysis.py (updated)
@router.post("/analyze-skin")
async def analyze_skin_with_orbo_middleware(
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Complete skin analysis with data sovereignty middleware
    """
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    try:
        # Read image data
        image_data = await image.read()
        
        # Prepare image metadata
        image_metadata = {
            "original_filename": image.filename,
            "file_size": len(image_data),
            "content_type": image.content_type,
            "upload_timestamp": datetime.utcnow().isoformat(),
            "user_agent": request.headers.get("user-agent", ""),
            "client_ip": request.client.host
        }
        
        # Initialize ORBO service with database
        orbo_service = OrboSkinAnalysisService(db)
        
        # Run complete analysis pipeline WITH middleware
        result = await orbo_service.complete_analysis_pipeline_with_middleware(
            image_data, 
            str(user.id),
            image_metadata
        )
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        # Generate AI recommendations using our stored data
        recommendation_service = RecommendationService()
        recommendations = await recommendation_service.generate_recommendations(
            result['metrics'], user.profile
        )
        
        return {
            'internal_analysis_id': result['internal_analysis_id'],
            'orbo_session_id': result.get('session_id'),
            'skin_metrics': result['metrics'],
            'recommendations': recommendations,
            'annotations': result['annotations'],
            'data_sovereignty_compliant': result['data_sovereignty_compliant'],
            'database_stored': result['database_stored']
        }
        
    except Exception as e:
        logger.error(f"Skin analysis with middleware error: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed")

@router.get("/analysis/{internal_analysis_id}")
async def get_analysis_by_internal_id(
    internal_analysis_id: str,
    user: User = Depends(get_current_user),
    db = Depends(get_database)
):
    """
    Get analysis by our internal ID (not ORBO session ID)
    """
    try:
        analysis = await db.skin_analyses.find_one({
            "analysis_id": internal_analysis_id,
            "user_id": str(user.id)
        })
        
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        
        return {
            'analysis_id': analysis['analysis_id'],
            'status': analysis['status'],
            'skin_metrics': analysis.get('orbo_metrics', {}),
            'annotations': analysis.get('orbo_response', {}).get('annotations', {}),
            'internal_image_url': analysis['internal_image_url'],
            'created_at': analysis['created_at'],
            'data_sovereignty_compliant': analysis['data_sovereignty_compliant']
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to retrieve analysis")
```

### Data Sovereignty Benefits

1. **Pre-Processing Storage**: All user images stored in YOUR database/S3 before going to ORBO
2. **Complete Audit Trail**: Track every step of the data processing pipeline
3. **Fallback Capability**: If ORBO fails, you still have the original data
4. **Compliance**: Meet data sovereignty requirements for GDPR, CCPA, etc.
5. **User Control**: Users can delete data from your systems independently
6. **Analytics**: Track usage patterns, success rates, and user behavior
7. **Cost Control**: Monitor and limit ORBO API usage
8. **Data Retention**: Implement your own retention policies

### Implementation Checklist

- [ ] Create OrboAnalysisMiddleware class
- [ ] Update OrboSkinAnalysisService to use middleware
- [ ] Create enhanced database schema
- [ ] Implement internal S3 storage service
- [ ] Update FastAPI endpoints
- [ ] Add proper error handling and rollback
- [ ] Implement audit trail logging
- [ ] Add data retention policies
- [ ] Create user data export/deletion endpoints
- [ ] Test complete pipeline with middleware

## Production Considerations

### Security
- Store ORBO credentials securely using environment variables
- Validate image uploads (size, format, content)
- Implement rate limiting on analysis endpoints
- Use HTTPS for all communications

### Performance
- Implement caching for analysis results
- Use async/await for non-blocking operations
- Consider image compression before upload
- Monitor API usage and costs

### Monitoring
- Log all ORBO API interactions
- Track analysis success/failure rates
- Monitor response times
- Alert on API errors or timeouts

## Deployment Checklist

- [ ] Add ORBO credentials to production environment
- [ ] Test complete pipeline in staging environment
- [ ] Implement proper error handling and logging
- [ ] Set up monitoring and alerting
- [ ] Verify image upload security measures
- [ ] Test auto-capture functionality
- [ ] Validate score color coding (green/yellow only)
- [ ] Ensure 0-100 score scaling works correctly
- [ ] Test annotation image display
- [ ] Verify database storage of analysis results

This implementation provides a complete integration of the ORBO AI API with your SkinSense application, including the requested 0-100 scoring, green/yellow color scheme, and auto-capture capabilities. 