import boto3
from botocore.exceptions import ClientError
from typing import Optional
import uuid
from datetime import datetime
import logging
from urllib.parse import urlparse
from PIL import Image
# Try to enable HEIC/HEIF support if the optional dependency is present
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()  # Registers HEIF opener for Pillow
except Exception:  # pragma: no cover - optional enhancement
    pass
from io import BytesIO

from app.core.config import settings

logger = logging.getLogger(__name__)

class S3Service:
    def __init__(self):
        # Support both old (lowercase) and new (UPPERCASE) settings attributes
        aws_access_key = getattr(settings, 'AWS_ACCESS_KEY_ID', None) or getattr(settings, 'aws_access_key_id', None)
        aws_secret_key = getattr(settings, 'AWS_SECRET_ACCESS_KEY', None) or getattr(settings, 'aws_secret_access_key', None)
        aws_region = getattr(settings, 'AWS_REGION', None) or getattr(settings, 'aws_region', 'us-east-1')

        self.bucket_name = getattr(settings, 'S3_BUCKET_NAME', None) or getattr(settings, 's3_bucket_name', '')
        self.cloudfront_domain = getattr(settings, 'CLOUDFRONT_DOMAIN', None) or getattr(settings, 'cloudfront_domain', None)
        self.aws_region = aws_region
        self.has_s3_config = bool(self.bucket_name and aws_access_key and aws_secret_key)

        # Lazily initialize client only if config exists to avoid runtime errors in dev
        if self.has_s3_config:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key,
                region_name=aws_region
            )
        else:
            self.s3_client = None  # type: ignore
    
    async def upload_image(
        self, 
        image_bytes: bytes, 
        user_id: str,
        image_type: str = "analysis"  # "analysis", "profile", "product"
    ) -> tuple[str, str]:  # Returns (full_url, thumbnail_url)
        """
        Upload image to S3 and create thumbnail
        Returns URLs for both full image and thumbnail
        """
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            filename = f"{image_type}/{user_id}/{timestamp}_{unique_id}.jpg"
            thumbnail_filename = f"{image_type}/{user_id}/thumbs/{timestamp}_{unique_id}_thumb.jpg"
            
            processed_image: bytes
            thumbnail_image: bytes
            
            # If S3 is not configured, skip processing and return placeholder URLs
            if not self.has_s3_config:
                logger.warning("S3 not configured. Skipping upload and returning placeholder URLs.")
                placeholder = f"s3-disabled://{image_type}/{user_id}/{timestamp}_{unique_id}.jpg"
                return placeholder, placeholder

            # Process main image with safe fallbacks for unsupported formats (e.g., HEIC)
            used_original_for_main = False
            try:
                processed_image = self._process_image(image_bytes, max_size=1024, quality=90)
            except Exception:
                logger.warning("Falling back to original bytes for main image upload (processing failed)")
                processed_image = image_bytes
                used_original_for_main = True
            
            # Create thumbnail; if processing fails, fall back to the processed/original bytes
            try:
                thumbnail_image = self._process_image(image_bytes, max_size=300, quality=85)
            except Exception:
                logger.warning("Falling back to original bytes for thumbnail upload (processing failed)")
                thumbnail_image = processed_image
            
            # Determine content type
            content_type_main = "image/jpeg"
            if used_original_for_main:
                content_type_main = self._detect_mime_from_bytes(processed_image) or "image/jpeg"

            # Upload main image
            full_url = await self._upload_to_s3(processed_image, filename, content_type_main)
            
            # Upload thumbnail
            thumbnail_url = await self._upload_to_s3(thumbnail_image, thumbnail_filename, "image/jpeg")
            
            return full_url, thumbnail_url
            
        except Exception as e:
            logger.error(f"Image upload failed: {e}")
            raise
    
    def _process_image(self, image_bytes: bytes, max_size: int, quality: int) -> bytes:
        """
        Process image: resize, optimize, convert to JPEG
        """
        try:
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if needed
            if image.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparency
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'P':
                    image = image.convert('RGBA')
                background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                image = background
            elif image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Resize if needed
            if max(image.size) > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Save to bytes
            buffer = BytesIO()
            image.save(buffer, format='JPEG', quality=quality, optimize=True)
            return buffer.getvalue()
            
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise

    def _detect_mime_from_bytes(self, data: bytes) -> Optional[str]:
        """Very small helper to detect common image mime types from magic bytes."""
        try:
            if len(data) >= 12:
                # JPEG
                if data[0:3] == b"\xFF\xD8\xFF":
                    return "image/jpeg"
                # PNG
                if data[0:8] == b"\x89PNG\r\n\x1a\n":
                    return "image/png"
                # HEIC/HEIF brands reside in ftyp box
                if data[4:8] == b"ftyp" and data[8:12] in [b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"]:
                    return "image/heic"
            return None
        except Exception:
            return None
    
    async def _upload_to_s3(self, image_bytes: bytes, filename: str, content_type: str) -> str:
        """
        Upload bytes to S3 bucket
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=image_bytes,
                ContentType=content_type,
                CacheControl="max-age=31536000",  # 1 year cache
                Metadata={
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'service': 'skinsense-ai'
                }
            )
            
            # Return URL
            if self.cloudfront_domain:
                return f"https://{self.cloudfront_domain}/{filename}"
            else:
                return f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{filename}"
                
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise
    
    async def delete_image(self, image_url: str) -> bool:
        """
        Delete image from S3
        """
        try:
            if not image_url:
                return False
            if image_url.startswith("s3-disabled://"):
                # Nothing was uploaded when S3 is disabled, treat as success
                return True
            if not self.has_s3_config or not self.s3_client:
                logger.warning("S3 not configured, cannot delete image: %s", image_url)
                return False

            key = self._extract_key_from_url(image_url)
            if not key:
                logger.warning("Could not determine S3 key for URL: %s", image_url)
                return False

            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
            
        except Exception as e:
            logger.error(f"S3 delete failed: {e}")
            return False
    
    def generate_presigned_url(self, key: str, expiration: int = 3600) -> Optional[str]:
        """
        Generate presigned URL for direct upload
        """
        try:
            response = self.s3_client.generate_presigned_url(
                'put_object',
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration
            )
            return response
        except ClientError as e:
            logger.error(f"Presigned URL generation failed: {e}")
            return None
    
    async def upload_file(self, file_data: bytes, filename: str, content_type: str = 'image/jpeg') -> str:
        """
        Upload file to S3 bucket (for middleware use)
        """
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=filename,
                Body=file_data,
                ContentType=content_type,
                CacheControl="max-age=31536000",
                Metadata={
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'service': 'skinsense-ai'
                }
            )
            
            # Return URL
            if self.cloudfront_domain:
                return f"https://{self.cloudfront_domain}/{filename}"
            else:
                return f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{filename}"
                
        except ClientError as e:
            logger.error(f"S3 upload failed: {e}")
            raise
    
    async def upload_community_image(self, file_data: bytes, filename: str, folder: str = "community") -> str:
        """
        Upload community post image to S3
        """
        try:
            # Generate unique filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            extension = filename.split('.')[-1] if '.' in filename else 'jpg'
            final_filename = f"{folder}/{timestamp}_{unique_id}.{extension}"
            
            # If S3 is not configured, return placeholder
            if not self.has_s3_config:
                logger.warning("S3 not configured. Returning placeholder URL.")
                return f"s3-disabled://{final_filename}"
            
            # Process image
            try:
                processed_image = self._process_image(file_data, max_size=1024, quality=90)
                content_type = "image/jpeg"
            except Exception:
                logger.warning("Using original image without processing")
                processed_image = file_data
                content_type = self._detect_mime_from_bytes(file_data) or "image/jpeg"
            
            # Upload to S3
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=final_filename,
                Body=processed_image,
                ContentType=content_type,
                CacheControl="max-age=31536000",
                Metadata={
                    'uploaded_at': datetime.utcnow().isoformat(),
                    'service': 'skinsense-community'
                }
            )
            
            # Return URL
            if self.cloudfront_domain:
                return f"https://{self.cloudfront_domain}/{final_filename}"
            else:
                return f"https://{self.bucket_name}.s3.{self.aws_region}.amazonaws.com/{final_filename}"
                
        except Exception as e:
            logger.error(f"Community image upload failed: {e}")
            raise

    def is_managed_url(self, image_url: Optional[str]) -> bool:
        """
        Check if the provided URL points to this service's managed storage.
        """
        if not image_url or not isinstance(image_url, str):
            return False
        if image_url.startswith("s3-disabled://"):
            return False
        return self._extract_key_from_url(image_url) is not None

    def _extract_key_from_url(self, image_url: str) -> Optional[str]:
        """
        Extract the object key from a URL pointing to this service's S3 bucket or CloudFront.
        """
        try:
            parsed = urlparse(image_url.strip())
            if not parsed.netloc:
                return None

            path = parsed.path.lstrip("/")
            if not path:
                return None

            # CloudFront distribution
            if self.cloudfront_domain:
                if parsed.netloc == self.cloudfront_domain or self.cloudfront_domain in parsed.netloc:
                    return path

            # Direct S3 access patterns
            if self.bucket_name:
                bucket_hosts = {
                    f"{self.bucket_name}.s3.{self.aws_region}.amazonaws.com",
                    f"{self.bucket_name}.s3.amazonaws.com",
                    self.bucket_name,
                }
                host = parsed.netloc
                if host in bucket_hosts or host.startswith(f"{self.bucket_name}.s3"):
                    return path

            # Support s3://bucket/key format
            if parsed.scheme == "s3" and parsed.netloc == self.bucket_name:
                return path

            return None
        except Exception as exc:
            logger.error(f"Failed to extract S3 key from URL '{image_url}': {exc}")
            return None

# Global instance
s3_service = S3Service()
