# Onboarding API Documentation

## Overview
The onboarding API endpoints allow the Flutter app to save and retrieve user preferences collected during the onboarding flow.

## Database Connection
- **MongoDB Atlas URL**: Configure in `.env` file using `MONGODB_URL` variable
- **Database Name**: `skinpal`
- **Main Collection**: `users`

## Endpoints

### 1. Save Onboarding Preferences
**POST** `/api/v1/users/preferences`

Saves the user's onboarding preferences after completing the onboarding flow.

**Request Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body:**
```json
{
  "gender": "female",
  "age_group": "25_34",
  "skin_type": "combination"
}
```

**Valid Values:**
- `gender`: "female", "male", "other", "prefer_not_to_say"
- `age_group`: "under_18", "18_24", "25_34", "35_44", "45_54", "55_plus"
- `skin_type`: "dry", "oily", "normal", "combination", "sensitive"

**Response (200 OK):**
```json
{
  "gender": "female",
  "age_group": "25_34",
  "skin_type": "combination",
  "is_completed": true,
  "completed_at": "2024-12-28T10:30:00Z"
}
```

### 2. Get Onboarding Preferences
**GET** `/api/v1/users/preferences`

Retrieves the user's saved onboarding preferences.

**Request Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "gender": "female",
  "age_group": "25_34",
  "skin_type": "combination",
  "is_completed": true,
  "completed_at": "2024-12-28T10:30:00Z"
}
```

### 3. Update Onboarding Preferences
**PUT** `/api/v1/users/preferences`

Updates specific onboarding preferences (partial update supported).

**Request Headers:**
```
Authorization: Bearer <access_token>
Content-Type: application/json
```

**Request Body (example - only update skin type):**
```json
{
  "skin_type": "sensitive"
}
```

**Response (200 OK):**
```json
{
  "gender": "female",
  "age_group": "25_34",
  "skin_type": "sensitive",
  "is_completed": true,
  "completed_at": "2024-12-28T10:30:00Z"
}
```

## Additional User Endpoints

### Get User Profile
**GET** `/api/v1/users/me`

Returns complete user profile including onboarding preferences.

**Response includes:**
- Basic user info (email, username)
- Onboarding preferences
- Skin profile
- Product preferences
- Subscription info
- Privacy settings

### Get User Statistics
**GET** `/api/v1/users/stats`

Returns user activity statistics.

**Response:**
```json
{
  "total_analyses": 15,
  "monthly_analyses": 3,
  "analyses_remaining": 2,
  "latest_analysis_date": "2024-12-27T15:30:00Z",
  "saved_products": 8,
  "subscription_tier": "basic",
  "onboarding_completed": true,
  "member_since": "2024-10-15T08:00:00Z"
}
```

## Flutter Integration Example

```dart
// Save onboarding preferences
Future<void> saveOnboardingPreferences(UserPreferences preferences) async {
  final response = await dio.post(
    '/api/v1/users/preferences',
    data: preferences.toJson(),
    options: Options(
      headers: {'Authorization': 'Bearer $accessToken'},
    ),
  );
  
  if (response.statusCode == 200) {
    // Preferences saved successfully
    // Navigate to home screen
  }
}

// Get user preferences
Future<UserPreferences> getUserPreferences() async {
  final response = await dio.get(
    '/api/v1/users/preferences',
    options: Options(
      headers: {'Authorization': 'Bearer $accessToken'},
    ),
  );
  
  return UserPreferences.fromJson(response.data);
}
```

## Database Schema

The user document in MongoDB includes:

```javascript
{
  "_id": ObjectId,
  "email": "user@example.com",
  "username": "testuser",
  "password_hash": "...",
  "onboarding": {
    "gender": "female",
    "age_group": "25_34", 
    "skin_type": "combination",
    "is_completed": true,
    "completed_at": ISODate("2024-12-28T10:30:00Z")
  },
  "profile": {
    "age_range": "25-34",  // Legacy field, auto-converted from age_group
    "skin_type": "combination",  // Synced with onboarding.skin_type
    "skin_concerns": ["acne", "hydration"],
    "current_routine": ["cleanser", "moisturizer"],
    "goals": ["clear_skin", "hydration"],
    "ai_detected_skin_type": null,  // Updated after AI analysis
    "ai_confidence_score": null,
    "last_analysis_date": null
  },
  "product_preferences": {
    "budget_range": "mid_range",
    "ingredient_preferences": ["hyaluronic_acid", "niacinamide"],
    "ingredient_blacklist": ["fragrance", "alcohol"],
    "preferred_brands": [],
    "preferred_categories": ["cleanser", "serum", "moisturizer"]
  },
  "subscription": {
    "tier": "basic",
    "is_active": true,
    "expires_at": null
  },
  "privacy_settings": {
    "blur_face_in_photos": true,
    "share_anonymous_data": false,
    "email_notifications": true,
    "push_notifications": true,
    "data_retention_days": 365
  },
  "created_at": ISODate("2024-10-15T08:00:00Z"),
  "updated_at": ISODate("2024-12-28T10:30:00Z"),
  "is_active": true,
  "is_verified": false
}
```

## Notes

1. **Authentication Required**: All endpoints require a valid JWT access token
2. **Backward Compatibility**: The system maintains both new onboarding fields and legacy profile fields
3. **Auto-conversion**: Age group is automatically converted to age range format for legacy compatibility
4. **Skin Type Sync**: Skin type is stored in both onboarding and profile for compatibility
5. **AI Enhancement**: The initial preferences serve as baseline that gets refined with each AI analysis