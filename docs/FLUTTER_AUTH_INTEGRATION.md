# Flutter Authentication Integration Guide

## Overview
This guide shows how to integrate the Flutter app with the SkinSense backend authentication system.

## API Base URL
```
Development: http://localhost:8000/api/v1
Production: https://api.skinsense.ai/api/v1
```

## Authentication Endpoints

### 1. Email/Password Registration
**POST** `/auth/register`

**Request:**
```dart
final response = await dio.post(
  '$baseUrl/auth/register',
  data: {
    'email': email,
    'username': username,
    'password': password,
  },
);
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "token_type": "bearer",
  "expires_in": 1800,
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "email": "user@example.com",
    "username": "testuser",
    "onboarding": {
      "is_completed": false
    },
    "subscription": {
      "tier": "basic"
    }
  },
  "is_new_user": true
}
```

### 2. Email/Password Login
**POST** `/auth/login`

**Request:**
```dart
final response = await dio.post(
  '$baseUrl/auth/login',
  data: {
    'email': email,
    'password': password,
  },
);
```

**Response:** Same as registration, but `is_new_user` may be `false`

### 3. Google Sign In
**POST** `/auth/google`

**Request:**
```dart
// After Google Sign In
final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
final GoogleSignInAuthentication googleAuth = await googleUser!.authentication;

final response = await dio.post(
  '$baseUrl/auth/google',
  data: {
    'id_token': googleAuth.idToken,
  },
);
```

**Response:** Same as registration

### 4. Apple Sign In
**POST** `/auth/apple`

**Request:**
```dart
// After Apple Sign In
final credential = await SignInWithApple.getAppleIDCredential(
  scopes: [
    AppleIDAuthorizationScopes.email,
    AppleIDAuthorizationScopes.fullName,
  ],
);

final response = await dio.post(
  '$baseUrl/auth/apple',
  data: {
    'identity_token': credential.identityToken,
    'user_identifier': credential.userIdentifier,
    'email': credential.email,
    'full_name': {
      'givenName': credential.givenName,
      'familyName': credential.familyName,
    },
  },
);
```

**Response:** Same as registration

### 5. Token Refresh
**POST** `/auth/refresh`

**Request:**
```dart
final response = await dio.post(
  '$baseUrl/auth/refresh',
  data: {
    'refresh_token': storedRefreshToken,
  },
);
```

**Response:**
```json
{
  "access_token": "new_access_token",
  "refresh_token": "new_refresh_token",
  "token_type": "bearer",
  "expires_in": 1800
}
```

## Flutter Implementation

### 1. Update AuthNotifier
```dart
class AuthNotifier extends StateNotifier<AuthState> {
  final Dio _dio = Dio(BaseOptions(
    baseUrl: 'http://localhost:8000/api/v1',
    contentType: 'application/json',
  ));

  Future<void> signUp(String email, String username, String password) async {
    state = const AuthState.loading();
    try {
      final response = await _dio.post('/auth/register', data: {
        'email': email,
        'username': username,
        'password': password,
      });

      final data = response.data;
      final user = User(
        id: data['user']['id'],
        email: data['user']['email'],
        username: data['user']['username'],
        isNewUser: data['is_new_user'],
      );

      // Store tokens
      await _secureStorage.write(key: 'access_token', value: data['access_token']);
      await _secureStorage.write(key: 'refresh_token', value: data['refresh_token']);

      state = AuthState.authenticated(user);
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }

  Future<void> signInWithGoogle() async {
    state = const AuthState.loading();
    try {
      final GoogleSignInAccount? googleUser = await _googleSignIn.signIn();
      if (googleUser == null) {
        state = const AuthState.unauthenticated();
        return;
      }

      final GoogleSignInAuthentication googleAuth = await googleUser.authentication;
      
      final response = await _dio.post('/auth/google', data: {
        'id_token': googleAuth.idToken,
      });

      final data = response.data;
      final user = User(
        id: data['user']['id'],
        email: data['user']['email'],
        username: data['user']['username'],
        isNewUser: data['is_new_user'],
      );

      // Store tokens
      await _secureStorage.write(key: 'access_token', value: data['access_token']);
      await _secureStorage.write(key: 'refresh_token', value: data['refresh_token']);

      state = AuthState.authenticated(user);
    } catch (e) {
      state = AuthState.error(e.toString());
    }
  }
}
```

### 2. Add Dio Interceptor for Auth
```dart
class AuthInterceptor extends Interceptor {
  final FlutterSecureStorage _storage;
  
  AuthInterceptor(this._storage);

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    final token = await _storage.read(key: 'access_token');
    if (token != null) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) async {
    if (err.response?.statusCode == 401) {
      // Try to refresh token
      final refreshToken = await _storage.read(key: 'refresh_token');
      if (refreshToken != null) {
        try {
          final response = await Dio().post(
            '${err.requestOptions.baseUrl}/auth/refresh',
            data: {'refresh_token': refreshToken},
          );
          
          // Store new tokens
          await _storage.write(key: 'access_token', value: response.data['access_token']);
          await _storage.write(key: 'refresh_token', value: response.data['refresh_token']);
          
          // Retry original request
          err.requestOptions.headers['Authorization'] = 'Bearer ${response.data['access_token']}';
          final clonedRequest = await Dio().request(
            err.requestOptions.path,
            options: Options(
              method: err.requestOptions.method,
              headers: err.requestOptions.headers,
            ),
            data: err.requestOptions.data,
            queryParameters: err.requestOptions.queryParameters,
          );
          
          return handler.resolve(clonedRequest);
        } catch (e) {
          // Refresh failed, sign out user
          await _storage.deleteAll();
          // Navigate to login
        }
      }
    }
    handler.next(err);
  }
}
```

### 3. Save Onboarding Preferences
```dart
Future<void> saveOnboardingPreferences({
  required String gender,
  required String ageGroup,
  required String skinType,
}) async {
  final dio = Dio();
  dio.interceptors.add(AuthInterceptor(_secureStorage));
  
  try {
    final response = await dio.post(
      '$baseUrl/users/preferences',
      data: {
        'gender': gender,
        'age_group': ageGroup,
        'skin_type': skinType,
      },
    );
    
    if (response.statusCode == 200) {
      // Onboarding completed successfully
      // Navigate to main app
    }
  } catch (e) {
    // Handle error
  }
}
```

## Error Handling

The API returns standard HTTP status codes:
- `200` - Success
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid credentials or token)
- `403` - Forbidden (account deactivated)
- `404` - Not Found
- `500` - Internal Server Error

Error response format:
```json
{
  "detail": "Email already registered"
}
```

## Security Notes

1. **Token Storage**: Always use `flutter_secure_storage` for storing tokens
2. **Token Expiry**: Access tokens expire in 30 minutes, use refresh token to get new ones
3. **HTTPS**: Always use HTTPS in production
4. **Token Refresh**: Implement automatic token refresh using Dio interceptors
5. **Sign Out**: Clear all stored tokens and Google/Apple session when signing out

## Testing

For local development:
1. Make sure backend is running: `uvicorn app.main:app --reload`
2. Use `http://localhost:8000` as base URL
3. For Google Sign In testing, you'll need to set up OAuth credentials
4. For Apple Sign In, you'll need an Apple Developer account

## Next Steps

1. Set up Google OAuth:
   - Create project in Google Cloud Console
   - Enable Google Sign-In API
   - Add OAuth 2.0 Client ID
   - Download and add GoogleService-Info.plist to iOS

2. Set up Apple Sign In:
   - Enable Sign In with Apple in Apple Developer Portal
   - Add capability in Xcode
   - Configure provisioning profiles

3. Update Flutter app with real API endpoints
4. Implement proper error handling and loading states
5. Add analytics to track authentication events