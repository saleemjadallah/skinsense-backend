"""
Social Authentication Service
Handles Google and Apple sign-in token verification
"""
import httpx
import jwt
import json
from typing import Dict, Any, Optional
from datetime import datetime
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)

class SocialAuthService:
    """Service for handling social authentication providers"""
    
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        self.google_client_ids = [
            # Add your Google OAuth client IDs here
            # settings.google_oauth_client_id_ios,
            # settings.google_oauth_client_id_web,
        ]
        # Accept both the iOS app bundle ID and the Service ID for web/backend
        self.apple_client_ids = [
            "app.skinsense.ios",  # iOS app bundle ID
            "app.skinsense.service",  # Service ID for backend (create this in Apple Developer)
            "app.skinsense.ios.service"  # Alternative service ID format
        ]
    
    async def verify_google_token(self, id_token: str) -> Optional[Dict[str, Any]]:
        """
        Verify Google ID token and extract user information
        
        Returns:
            Dict with email, name, picture, and sub (Google user ID)
            None if verification fails
        """
        try:
            # Google's token verification endpoint
            url = f"https://oauth2.googleapis.com/tokeninfo?id_token={id_token}"
            
            response = await self.client.get(url)
            
            if response.status_code != 200:
                logger.error(f"Google token verification failed: {response.text}")
                return None
            
            token_info = response.json()
            
            # Verify the token is for our app
            # if token_info.get("aud") not in self.google_client_ids:
            #     logger.error(f"Invalid audience: {token_info.get('aud')}")
            #     return None
            
            # Extract user information
            return {
                "provider": "google",
                "provider_user_id": token_info.get("sub"),
                "email": token_info.get("email"),
                "name": token_info.get("name"),
                "picture": token_info.get("picture"),
                "email_verified": token_info.get("email_verified", False)
            }
            
        except Exception as e:
            logger.error(f"Error verifying Google token: {e}")
            return None
    
    async def verify_apple_token(
        self, 
        identity_token: str,
        user_identifier: str,
        email: Optional[str] = None,
        full_name: Optional[Dict[str, str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Verify Apple identity token and extract user information
        
        Note: Apple only provides email and name on first sign-in
        
        Returns:
            Dict with email, name, and sub (Apple user ID)
            None if verification fails
        """
        try:
            logger.info(f"Verifying Apple token for user_identifier: {user_identifier}")
            logger.info(f"Email provided: {email}")
            logger.info(f"Full name provided: {full_name}")
            
            # Fetch Apple's public keys
            keys_response = await self.client.get("https://appleid.apple.com/auth/keys")
            if keys_response.status_code != 200:
                logger.error(f"Failed to fetch Apple public keys. Status: {keys_response.status_code}")
                return None
            
            apple_keys = keys_response.json()["keys"]
            logger.info(f"Fetched {len(apple_keys)} Apple public keys")
            
            # Decode the token header to get the key ID
            header = jwt.get_unverified_header(identity_token)
            kid = header.get("kid")
            logger.info(f"Token kid: {kid}")
            
            # Find the matching public key
            public_key = None
            for key in apple_keys:
                if key["kid"] == kid:
                    public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                    logger.info(f"Found matching public key for kid: {kid}")
                    break
            
            if not public_key:
                logger.error(f"No matching public key found for Apple token with kid: {kid}")
                return None
            
            # Verify and decode the token - try each accepted client ID
            decoded = None
            last_error = None
            
            for client_id in self.apple_client_ids:
                try:
                    decoded = jwt.decode(
                        identity_token,
                        public_key,
                        algorithms=["RS256"],
                        audience=client_id,
                        issuer="https://appleid.apple.com"
                    )
                    logger.info(f"Token decoded successfully with client_id: {client_id}")
                    logger.info(f"Token sub: {decoded.get('sub')}")
                    logger.info(f"Token audience: {decoded.get('aud')}")
                    logger.info(f"Token issuer: {decoded.get('iss')}")
                    break  # Successfully decoded
                except jwt.InvalidAudienceError:
                    logger.debug(f"Token audience doesn't match {client_id}, trying next...")
                    continue
                except jwt.InvalidIssuerError as e:
                    last_error = f"Invalid issuer: {e}"
                    break
                except jwt.ExpiredSignatureError as e:
                    last_error = f"Token expired: {e}"
                    break
                except jwt.InvalidTokenError as e:
                    last_error = f"Invalid token: {e}"
                    break
            
            if not decoded:
                if last_error:
                    logger.error(f"Token verification failed: {last_error}")
                else:
                    logger.error(f"Invalid audience. Token audience not in: {self.apple_client_ids}")
                return None
            
            # Verify the user identifier matches
            if decoded.get("sub") != user_identifier:
                logger.error(f"User identifier mismatch. Expected: {user_identifier}, Got: {decoded.get('sub')}")
                return None
            
            # Build user info
            user_info = {
                "provider": "apple",
                "provider_user_id": user_identifier,
                "email": email or decoded.get("email"),
                "email_verified": decoded.get("email_verified", False)
            }
            
            # Add name if provided (only on first sign-in)
            if full_name:
                name_parts = []
                if full_name.get("givenName"):
                    name_parts.append(full_name["givenName"])
                if full_name.get("familyName"):
                    name_parts.append(full_name["familyName"])
                if name_parts:
                    user_info["name"] = " ".join(name_parts)
            
            logger.info(f"Apple token verified successfully for user: {user_info.get('email', user_identifier)}")
            return user_info
            
        except Exception as e:
            logger.error(f"Unexpected error verifying Apple token: {e}", exc_info=True)
            return None
    
    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

# Global service instance
social_auth_service = SocialAuthService()