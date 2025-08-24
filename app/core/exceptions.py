from fastapi import HTTPException, status

class SkinSenseException(Exception):
    """Base exception for SkinSense API"""
    pass

class AuthenticationError(SkinSenseException):
    """Raised when authentication fails"""
    pass

class AuthorizationError(SkinSenseException):
    """Raised when user lacks permissions"""
    pass

class ResourceNotFoundError(SkinSenseException):
    """Raised when requested resource doesn't exist"""
    pass

class RateLimitError(SkinSenseException):
    """Raised when rate limit is exceeded"""
    pass

class ValidationError(SkinSenseException):
    """Raised when data validation fails"""
    pass

class ServiceUnavailableError(SkinSenseException):
    """Raised when external service is unavailable"""
    pass

# Common HTTP exceptions
def not_found(detail: str = "Resource not found"):
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail
    )

def bad_request(detail: str = "Bad request"):
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail
    )

def unauthorized(detail: str = "Unauthorized"):
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"}
    )

def forbidden(detail: str = "Forbidden"):
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail
    )

def internal_error(detail: str = "Internal server error"):
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail
    )