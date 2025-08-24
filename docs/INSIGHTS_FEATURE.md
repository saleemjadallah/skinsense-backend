# AI-Powered Personalized Insights Feature

## Overview
The Insights feature provides users with 3 daily personalized skincare insights based on their skin analysis data, user preferences, routine completion patterns, and environmental factors. The system uses OpenAI GPT-4 to generate contextually relevant insights that avoid overlapping with existing features like goals and routines.

## Architecture

### Backend Components

1. **Models** (`app/models/insights.py`)
   - `DailyInsights`: Main model for storing user's daily insights
   - `InsightContent`: Individual insight with title, description, category, and priority
   - `PersonalizationFactors`: Context used to generate insights
   - `InsightTemplate`: Reusable templates for common scenarios

2. **Service** (`app/services/insights_service.py`)
   - Gathers user context from multiple collections
   - Generates AI-powered insights using OpenAI
   - Implements caching and fallback mechanisms
   - Tracks user interactions with insights

3. **API Endpoints** (`app/api/v1/insights.py`)
   - `GET /api/v1/insights/daily` - Get today's insights
   - `POST /api/v1/insights/generate` - Force generate new insights
   - `POST /api/v1/insights/{id}/interact` - Track interactions
   - `GET /api/v1/insights/history` - Get historical insights
   - `GET /api/v1/insights/preferences` - Get user preferences
   - `PUT /api/v1/insights/preferences` - Update preferences

4. **Cron Job** (`app/scripts/generate_daily_insights.py`)
   - Runs daily at 6 AM to generate insights for all users
   - Cleans up old insights after 7 days
   - Supports manual execution for testing

### Frontend Components

1. **Models** (`lib/data/models/insights.dart`)
   - Freezed models matching backend structure
   - Type-safe category enum

2. **Service** (`lib/data/services/insights_service.dart`)
   - API integration with caching
   - Automatic retry with cached data
   - Interaction tracking

3. **Provider** (`lib/presentation/providers/insights_provider.dart`)
   - State management with Riverpod
   - Smart caching (6-hour refresh interval)
   - Error handling with fallback

4. **UI Widget** (Updated in `home_page.dart`)
   - Displays 3 insights with priority indicators
   - Loading shimmer effects
   - Fallback to static tips on error
   - Refresh button for manual updates
   - Interactive cards with navigation

## Insight Categories

The system generates insights in these non-overlapping categories:

1. **skin_trend** - Trends in user's skin metrics over time
2. **environmental** - Weather and seasonal skincare advice
3. **ingredient_focus** - Education about specific ingredients
4. **prevention** - Preventive care tips
5. **product_tip** - How to use products more effectively
6. **habit_formation** - Building consistent skincare habits
7. **celebration** - Celebrating achievements (rare)
8. **recommendation** - Personalized suggestions (rare)

## Personalization Factors

The AI considers these factors when generating insights:

- User demographics (age, gender, skin type)
- Latest skin analysis scores (ORBO metrics)
- Areas needing improvement (scores < 70)
- Routine completion rate
- Current streak
- Active goals
- Recent achievements
- Current season and weather
- Product preferences and allergies

## Deployment

### Manual Cron Setup
```bash
# Install crontab on production server
crontab backend/cron/crontab

# Verify installation
crontab -l
```

### Docker Deployment
```bash
# Start cron container
docker-compose -f docker-compose.cron.yml up -d cron

# Or use Celery Beat for more robust scheduling
docker-compose -f docker-compose.cron.yml up -d celery-beat celery-worker
```

### Manual Testing
```bash
# Generate insights for specific user
python backend/app/scripts/generate_daily_insights.py --user-id USER_ID

# Generate for all users (dry run)
python backend/app/scripts/generate_daily_insights.py --dry-run
```

## Monitoring

### Check Generation Status
```bash
# View cron logs
tail -f /var/log/skinsense/insights_cron.log

# Check today's generation count
python -c "from app.database import db; from datetime import datetime; count = db.daily_insights.count_documents({'created_at': {'$gte': datetime.utcnow().replace(hour=0, minute=0, second=0)}}); print(f'Generated insights today: {count}')"
```

### Database Indexes
The following indexes should be created for optimal performance:
```javascript
db.daily_insights.createIndex({ "user_id": 1, "generated_for_date": -1 })
db.daily_insights.createIndex({ "expires_at": 1 }, { expireAfterSeconds: 0 })
db.daily_insights.createIndex({ "created_at": -1 })
```

## API Usage Examples

### Get Daily Insights
```bash
curl -X GET "https://api.skinsense.ai/api/v1/insights/daily" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### Track Interaction
```bash
curl -X POST "https://api.skinsense.ai/api/v1/insights/INSIGHTS_ID/interact" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "interaction_type": "clicked",
    "insight_index": 0
  }'
```

### Update Preferences
```bash
curl -X PUT "https://api.skinsense.ai/api/v1/insights/preferences" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "preferred_categories": ["ingredient_focus", "environmental"],
    "blocked_categories": ["celebration"],
    "insight_frequency": "daily"
  }'
```

## Flutter Integration

The HomePage automatically fetches and displays insights when loaded. The widget:

1. Checks cache (6-hour validity)
2. Fetches from API if needed
3. Falls back to cached data on error
4. Displays loading shimmer during fetch
5. Shows static tips if all else fails

Users can:
- Tap insights to navigate to relevant pages
- Refresh insights manually
- See priority indicators for important insights
- Track all interactions automatically

## Performance Optimization

1. **Caching Strategy**
   - 24-hour server-side cache per user
   - 6-hour client-side cache
   - Automatic fallback to cache on error

2. **Database Optimization**
   - Compound indexes for fast queries
   - TTL index for automatic cleanup
   - Aggregation pipeline for context gathering

3. **API Optimization**
   - Single endpoint for daily insights
   - Bulk generation in cron job
   - Minimal payload size

## Security Considerations

1. User insights are isolated by user_id
2. API requires authentication
3. Interaction tracking is anonymous
4. No PII in insight content
5. Opt-out preference respected

## Future Enhancements

1. **Machine Learning**
   - Learn from interaction patterns
   - Predict preferred insight types
   - Optimize timing based on usage

2. **Advanced Personalization**
   - Location-based insights
   - Product-specific tips
   - Brand preferences

3. **Social Features**
   - Share insights with friends
   - Community insight voting
   - Expert-curated insights

4. **Analytics**
   - Insight effectiveness tracking
   - A/B testing different formats
   - Engagement metrics dashboard