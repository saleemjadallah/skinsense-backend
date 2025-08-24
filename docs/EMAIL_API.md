# Email & Authentication API Documentation

## Overview
SkinSense AI uses Zoho ZeptoMail for sending transactional emails including OTP verification, password reset, and welcome emails.

## Email Endpoints

### 1. Verify OTP
Verify the OTP code sent to user's email during registration.

**Endpoint:** `POST /api/v1/auth/verify-otp`

**Request Body:**
```json
{
  "email": "user@example.com",
  "otp": "123456"
}
```

**Response:**
```json
{
  "message": "Email verified successfully"
}
```

**Error Responses:**
- `400`: Invalid or expired OTP
- `404`: User not found

**Notes:**
- OTP expires after 15 minutes
- Maximum 3 attempts allowed
- Welcome email is sent after successful verification

### 2. Resend OTP
Resend OTP code for email verification or password reset.

**Endpoint:** `POST /api/v1/auth/resend-otp`

**Request Body:**
```json
{
  "email": "user@example.com",
  "purpose": "verification"  // or "reset"
}
```

**Response:**
```json
{
  "message": "OTP sent to user@example.com"
}
```

**Error Responses:**
- `404`: User not found
- `400`: Invalid purpose

### 3. Forgot Password
Request a password reset OTP.

**Endpoint:** `POST /api/v1/auth/forgot-password`

**Request Body:**
```json
{
  "email": "user@example.com"
}
```

**Response:**
```json
{
  "message": "If the email exists, a reset code will be sent"
}
```

**Notes:**
- Always returns success to prevent email enumeration
- OTP is sent only if user exists

### 4. Reset Password
Reset password using the OTP received via email.

**Endpoint:** `POST /api/v1/auth/reset-password`

**Request Body:**
```json
{
  "email": "user@example.com",
  "otp": "123456",
  "new_password": "NewSecurePassword123!"
}
```

**Response:**
```json
{
  "message": "Password reset successfully"
}
```

**Error Responses:**
- `400`: Invalid or expired OTP
- `404`: User not found

**Password Requirements:**
- Minimum 8 characters

## Email Templates

### 1. OTP Verification Email
- **Subject:** "SkinSense AI - Verify Your Email"
- **Content:** Contains 6-digit OTP code
- **Expiry:** 15 minutes
- **Design:** Gradient header with brand colors

### 2. Password Reset Email
- **Subject:** "SkinSense AI - Reset Your Password"
- **Content:** Contains 6-digit OTP code
- **Expiry:** 15 minutes
- **Design:** Security-focused messaging

### 3. Welcome Email
- **Subject:** "Welcome to SkinSense AI - Your Skincare Journey Begins!"
- **Content:** 
  - Welcome message
  - Key features overview
  - Getting started tips
  - Call-to-action button
- **Design:** Feature-rich template with icons

## Implementation Details

### OTP Storage
- **Primary:** Redis with 15-minute TTL
- **Fallback:** In-memory storage if Redis unavailable
- **Format:** `otp:{email}:{purpose}`

### Security Features
1. **Rate Limiting:** 3 attempts per OTP
2. **Expiration:** 15-minute validity
3. **Secure Generation:** Cryptographically secure random numbers
4. **No Email Enumeration:** Consistent responses for privacy

### Integration Flow

#### Registration with Email Verification
1. User registers → OTP sent automatically
2. User enters OTP → Email verified
3. Welcome email sent → User can access app

#### Password Reset Flow
1. User requests reset → OTP sent
2. User enters OTP + new password → Password updated
3. User can login with new password

## Testing

### Test Script
Run the test script to verify email functionality:
```bash
cd backend
python test_email.py your-email@example.com
```

### Manual Testing via API
```bash
# 1. Register new user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "password": "Test1234!"
  }'

# 2. Verify OTP (check email for code)
curl -X POST http://localhost:8000/api/v1/auth/verify-otp \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "otp": "123456"
  }'

# 3. Test password reset
curl -X POST http://localhost:8000/api/v1/auth/forgot-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com"
  }'

# 4. Reset password with OTP
curl -X POST http://localhost:8000/api/v1/auth/reset-password \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "otp": "654321",
    "new_password": "NewPassword123!"
  }'
```

## Environment Variables
```env
# ZeptoMail Configuration
ZEPTOMAIL_SEND_TOKEN="your-send-token"
ZEPTOMAIL_HOST="api.zeptomail.com"
ZEPTOMAIL_DOMAIN="skinsense.app"

# Redis (for OTP storage)
REDIS_URL="redis://localhost:6379"
```

## Error Handling
All email operations are wrapped with try-catch blocks and include:
- Logging for debugging
- Graceful fallbacks
- User-friendly error messages
- No sensitive information in responses

## Best Practices
1. Always verify email before granting full access
2. Use background tasks for sending emails
3. Implement retry logic for failed sends
4. Monitor email delivery rates
5. Keep templates mobile-responsive