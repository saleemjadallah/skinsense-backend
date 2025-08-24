# SkinSense AI Monitoring Setup

This directory contains the monitoring configuration for SkinSense AI using Prometheus and Grafana.

## Quick Start

1. **Start the monitoring stack:**
   ```bash
   cd backend
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

2. **Access the dashboards:**
   - Prometheus: http://localhost:9090
   - Grafana: http://localhost:3001 (admin/skinsense123!)

3. **Verify metrics collection:**
   - FastAPI metrics: http://localhost:8000/metrics
   - Node metrics: http://localhost:9100/metrics

## Architecture

### Metrics Collection
- **FastAPI**: Custom metrics for API performance, AI services, and business KPIs
- **Node Exporter**: System metrics (CPU, memory, disk)
- **MongoDB Exporter**: Database performance metrics
- **Redis Exporter**: Cache performance metrics

### Key Metrics Tracked

#### API Performance
- Request rate by endpoint
- Response time percentiles (p95, p99)
- Error rates
- Active users
- Request/response sizes

#### AI Services
- Service request rates (ORBO, OpenAI, Perplexity)
- Response times per service
- Token usage tracking
- Error rates by service
- Cost estimation

#### Business Metrics
- Skin analyses per hour
- New vs returning users
- Skin health score distribution
- Routine completion rates
- Product recommendation cache hits

#### System Health
- CPU and memory usage
- Database connection pool
- Query performance
- Cache hit rates

## Alerts Configured

### Critical Alerts
- Backend service down
- High error rate (>5%)
- Database connection issues

### Warning Alerts
- High response time (>2s p95)
- High AI service latency (>10s)
- High resource usage (>85% memory, >80% CPU)
- High API spending (>$10/hour)

### Info Alerts
- Low analysis rate (<10/hour)
- No new users in 24 hours

## Grafana Dashboards

### SkinSense AI Overview
Main dashboard showing:
- Request rates and response times
- Error rates and active users
- AI service performance
- Skin analysis metrics
- Token usage and cost tracking

## Custom Metrics Reference

### API Metrics
```python
# Request tracking
fastapi_requests_total{method, handler, status}
fastapi_http_request_duration_seconds{method, handler}
http_errors_total{method, handler, status}
active_users_current
```

### AI Service Metrics
```python
ai_service_requests_total{service, endpoint, status}
ai_service_duration_seconds{service, endpoint}
ai_service_tokens_total{service, type}
api_revenue_cents{service}
```

### Business Metrics
```python
skin_analysis_total{user_type}
skin_analysis_score (histogram)
recommendations_generated_total{source}
recommendation_cache_hits_total
routine_completions_total{routine_type}
```

### Database Metrics
```python
mongodb_operations_total{operation, collection, status}
mongodb_operation_duration_seconds{operation, collection}
```

## Adding New Metrics

1. Define metric in `app/core/monitoring.py`
2. Instrument your code with the metric
3. Add visualization to Grafana dashboard
4. Configure alerts if needed

Example:
```python
from app.core.monitoring import skin_analysis_total

# In your endpoint
skin_analysis_total.labels(user_type="new").inc()
```

## Production Deployment

For production, consider:
1. Using external Prometheus storage (e.g., Thanos)
2. Setting up Alertmanager for notifications
3. Implementing Grafana authentication
4. Backing up dashboards and configurations
5. Setting appropriate retention policies

## Troubleshooting

### Metrics not appearing
1. Check FastAPI logs for errors
2. Verify /metrics endpoint is accessible
3. Check Prometheus targets page
4. Review scrape configuration

### High memory usage
1. Adjust Prometheus retention time
2. Reduce scrape frequency
3. Limit number of metrics collected

### Dashboard issues
1. Verify datasource configuration
2. Check query syntax in panels
3. Review Grafana logs