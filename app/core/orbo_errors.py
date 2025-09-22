"""
ORBO API Error Handling and User-Friendly Messages
"""
from enum import Enum
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class OrboErrorType(Enum):
    """ORBO-specific error types"""
    FACE_NOT_DETECTED = "face_not_detected"
    IMAGE_TOO_SMALL = "image_too_small"
    FACE_OUT_OF_FOCUS = "face_out_of_focus"
    FACE_ANGLE_TILTED = "face_angle_tilted"
    NETWORK_ERROR = "network_error"
    TIMEOUT = "timeout"
    PRESIGNED_URL_FAILED = "presigned_url_failed"
    UPLOAD_FAILED = "upload_failed"
    ANALYSIS_FAILED = "analysis_failed"
    INVALID_IMAGE = "invalid_image"
    API_KEY_ERROR = "api_key_error"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    UNKNOWN = "unknown"

class OrboErrorHandler:
    """
    Centralized error handling for ORBO API interactions
    Maps technical errors to user-friendly messages
    """
    
    # Map ORBO error messages to error types
    ERROR_MESSAGE_MAPPING = {
        "Face not detected": OrboErrorType.FACE_NOT_DETECTED,
        "Image Resolution is too small": OrboErrorType.IMAGE_TOO_SMALL,
        "Face is out of focus": OrboErrorType.FACE_OUT_OF_FOCUS,
        "Face angle tilted": OrboErrorType.FACE_ANGLE_TILTED,
        "face_not_detected": OrboErrorType.FACE_NOT_DETECTED,
        "image_too_small": OrboErrorType.IMAGE_TOO_SMALL,
        "out_of_focus": OrboErrorType.FACE_OUT_OF_FOCUS,
        "angle_tilted": OrboErrorType.FACE_ANGLE_TILTED,
    }
    
    # User-friendly messages with actionable advice
    USER_MESSAGES = {
        OrboErrorType.FACE_NOT_DETECTED: {
            "title": "No Face Detected",
            "message": "We couldn't detect a face in the photo. Please ensure your face is clearly visible and centered in the frame.",
            "action": "Try taking another photo with better lighting and your face centered.",
            "icon": "face_not_found",
            "retry_allowed": True
        },
        OrboErrorType.IMAGE_TOO_SMALL: {
            "title": "Image Quality Too Low",
            "message": "The image resolution is too small for accurate analysis. The photo should be at least 500x500 pixels.",
            "action": "Please take a higher quality photo or move closer to the camera.",
            "icon": "low_quality",
            "retry_allowed": True
        },
        OrboErrorType.FACE_OUT_OF_FOCUS: {
            "title": "Photo is Blurry",
            "message": "The photo appears to be out of focus. A clear image is needed for accurate skin analysis.",
            "action": "Hold your device steady and tap to focus on your face before taking the photo.",
            "icon": "blur",
            "retry_allowed": True
        },
        OrboErrorType.FACE_ANGLE_TILTED: {
            "title": "Face Angle Issue",
            "message": "Please face the camera directly. Your face appears to be tilted or turned to the side.",
            "action": "Look straight at the camera with your face level and centered.",
            "icon": "face_angle",
            "retry_allowed": True
        },
        OrboErrorType.NETWORK_ERROR: {
            "title": "Connection Problem",
            "message": "We're having trouble connecting to our analysis servers.",
            "action": "Please check your internet connection and try again.",
            "icon": "wifi_off",
            "retry_allowed": True
        },
        OrboErrorType.TIMEOUT: {
            "title": "Analysis Taking Too Long",
            "message": "The skin analysis is taking longer than expected.",
            "action": "This may be due to server load. Please try again in a few moments.",
            "icon": "timer",
            "retry_allowed": True
        },
        OrboErrorType.PRESIGNED_URL_FAILED: {
            "title": "Upload Preparation Failed",
            "message": "We couldn't prepare your photo for analysis.",
            "action": "Please try again. If the problem persists, contact support.",
            "icon": "upload_error",
            "retry_allowed": True
        },
        OrboErrorType.UPLOAD_FAILED: {
            "title": "Photo Upload Failed",
            "message": "We couldn't upload your photo for analysis.",
            "action": "Please check your internet connection and try again.",
            "icon": "upload_error",
            "retry_allowed": True
        },
        OrboErrorType.ANALYSIS_FAILED: {
            "title": "Analysis Failed",
            "message": "We encountered an error while analyzing your skin.",
            "action": "Please try taking a new photo with good lighting.",
            "icon": "error",
            "retry_allowed": True
        },
        OrboErrorType.INVALID_IMAGE: {
            "title": "Invalid Image Format",
            "message": "The image format is not supported. Please use JPEG or PNG format.",
            "action": "Try taking a new photo or select a different image.",
            "icon": "image_error",
            "retry_allowed": True
        },
        OrboErrorType.API_KEY_ERROR: {
            "title": "Configuration Error",
            "message": "There's a problem with our analysis service configuration.",
            "action": "Please contact support if this persists.",
            "icon": "settings_error",
            "retry_allowed": False
        },
        OrboErrorType.RATE_LIMIT: {
            "title": "Too Many Requests",
            "message": "You've reached the analysis limit. Please wait a moment.",
            "action": "Try again in a few minutes.",
            "icon": "rate_limit",
            "retry_allowed": True
        },
        OrboErrorType.SERVER_ERROR: {
            "title": "Server Error",
            "message": "Our analysis servers are experiencing issues.",
            "action": "Please try again later or contact support if the problem persists.",
            "icon": "server_error",
            "retry_allowed": True
        },
        OrboErrorType.UNKNOWN: {
            "title": "Unexpected Error",
            "message": "Something went wrong with the skin analysis.",
            "action": "Please try again or contact support if the problem continues.",
            "icon": "error",
            "retry_allowed": True
        }
    }
    
    @classmethod
    def parse_orbo_error(cls, error_data: Dict[str, Any]) -> OrboErrorType:
        """
        Parse ORBO API error response and determine error type
        """
        if isinstance(error_data, dict):
            # Check for ORBO-specific error format
            if 'error' in error_data:
                error_info = error_data['error']
                if isinstance(error_info, dict):
                    message = error_info.get('message', '').lower()
                    description = error_info.get('description', '').lower()
                    
                    # Check both message and description
                    for check_text in [message, description]:
                        for key, error_type in cls.ERROR_MESSAGE_MAPPING.items():
                            if key.lower() in check_text:
                                return error_type
            
            # Check for direct message field
            if 'message' in error_data:
                message = error_data['message'].lower()
                for key, error_type in cls.ERROR_MESSAGE_MAPPING.items():
                    if key.lower() in message:
                        return error_type
        
        # Check for string error
        elif isinstance(error_data, str):
            error_lower = error_data.lower()
            if 'timeout' in error_lower:
                return OrboErrorType.TIMEOUT
            elif 'network' in error_lower or 'connection' in error_lower:
                return OrboErrorType.NETWORK_ERROR
            elif 'upload' in error_lower:
                return OrboErrorType.UPLOAD_FAILED
            elif 'presigned' in error_lower:
                return OrboErrorType.PRESIGNED_URL_FAILED
            elif 'rate' in error_lower and 'limit' in error_lower:
                return OrboErrorType.RATE_LIMIT
            elif '401' in error_lower or 'unauthorized' in error_lower:
                return OrboErrorType.API_KEY_ERROR
            elif '500' in error_lower or 'server' in error_lower:
                return OrboErrorType.SERVER_ERROR
        
        return OrboErrorType.UNKNOWN
    
    @classmethod
    def get_user_friendly_error(
        cls, 
        error_data: Any,
        include_technical: bool = False
    ) -> Dict[str, Any]:
        """
        Convert technical error to user-friendly format
        
        Args:
            error_data: Raw error from ORBO or exception
            include_technical: Whether to include technical details for debugging
            
        Returns:
            Dictionary with user-friendly error information
        """
        # Determine error type
        error_type = cls.parse_orbo_error(error_data)
        
        # Get user-friendly message
        user_error = cls.USER_MESSAGES[error_type].copy()
        
        # Add error code for support
        user_error['error_code'] = error_type.value
        
        # Add technical details if requested (for logging/debugging)
        if include_technical:
            user_error['technical_details'] = {
                'raw_error': str(error_data),
                'error_type': error_type.value,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Log the error for monitoring
        logger.warning(
            f"ORBO Error: {error_type.value}",
            extra={
                'error_type': error_type.value,
                'raw_error': str(error_data)[:500],  # Limit size for logging
                'user_message': user_error['message']
            }
        )
        
        return user_error
    
    @classmethod
    def create_error_response(
        cls,
        error_data: Any,
        request_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a complete error response for API endpoints
        """
        user_error = cls.get_user_friendly_error(error_data, include_technical=False)
        
        response = {
            'success': False,
            'error': user_error,
            'request_id': request_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Log for monitoring
        logger.error(
            f"ORBO API Error Response",
            extra={
                'user_id': user_id,
                'request_id': request_id,
                'error_code': user_error['error_code'],
                'error_message': user_error['message']
            }
        )
        
        return response

from datetime import datetime

class OrboErrorMonitor:
    """
    Monitor and track ORBO errors for analytics and improvements
    """
    
    def __init__(self, db):
        self.db = db
    
    def log_error(
        self,
        user_id: str,
        error_type: OrboErrorType,
        error_details: Dict[str, Any],
        session_id: Optional[str] = None
    ):
        """
        Log error to database for monitoring and analytics
        """
        error_log = {
            'user_id': user_id,
            'error_type': error_type.value,
            'error_details': error_details,
            'session_id': session_id,
            'timestamp': datetime.utcnow(),
            'app_version': error_details.get('app_version'),
            'device_info': error_details.get('device_info')
        }

        try:
            self.db.orbo_errors.insert_one(error_log)
        except Exception as e:
            logger.error(f"Failed to log ORBO error to database: {e}")
    
    def get_error_statistics(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Get error statistics for monitoring dashboard
        """
        pipeline = [
            {
                '$match': {
                    'timestamp': {
                        '$gte': start_date,
                        '$lte': end_date
                    }
                }
            },
            {
                '$group': {
                    '_id': '$error_type',
                    'count': {'$sum': 1},
                    'unique_users': {'$addToSet': '$user_id'}
                }
            },
            {
                '$project': {
                    'error_type': '$_id',
                    'total_occurrences': '$count',
                    'affected_users': {'$size': '$unique_users'},
                    '_id': 0
                }
            }
        ]

        results = list(self.db.orbo_errors.aggregate(pipeline))
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'errors_by_type': results,
            'total_errors': sum(r['total_occurrences'] for r in results)
        }