from fastapi import APIRouter, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from pymongo.database import Database
from typing import Dict, Any, List
from datetime import datetime, timedelta
from bson import ObjectId
from app.database import get_database
from app.api.deps import get_current_active_user, require_admin
from app.models.user import UserModel
from app.core.config import settings
from app.core.orbo_errors import OrboErrorType
import logging
import json

logger = logging.getLogger(__name__)

router = APIRouter()

# HTML template for monitoring dashboard with login
MONITORING_DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>SkinSense AI - Monitoring Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f5f5;
        }
        .login-container {
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            padding: 1rem;
        }
        .login-box {
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            padding: 2.5rem;
            width: 100%;
            max-width: 400px;
        }
        .logo {
            text-align: center;
            margin-bottom: 2rem;
        }
        .logo h1 {
            color: #E91E63;
            font-size: 2rem;
            margin: 0;
        }
        .logo p {
            color: #666;
            margin: 0.5rem 0 0 0;
        }
        .form-group {
            margin-bottom: 1.5rem;
        }
        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            color: #333;
            font-weight: 500;
        }
        .form-input {
            width: 100%;
            padding: 0.75rem;
            border: 2px solid #eee;
            border-radius: 8px;
            font-size: 1rem;
            transition: border-color 0.3s;
            box-sizing: border-box;
        }
        .form-input:focus {
            outline: none;
            border-color: #E91E63;
        }
        .btn-login {
            width: 100%;
            padding: 0.875rem;
            background: #E91E63;
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }
        .btn-login:hover {
            background: #AD1457;
        }
        .btn-login:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        .error-message {
            background: #fee;
            color: #c33;
            padding: 0.75rem;
            border-radius: 6px;
            margin-bottom: 1rem;
            display: none;
        }
        .loading {
            display: none;
            text-align: center;
            color: #666;
            margin-top: 1rem;
        }
        .dashboard-container {
            display: none;
            flex-direction: column;
            height: 100vh;
        }
        .header {
            background-color: #E91E63;
            color: white;
            padding: 1rem;
            text-align: center;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            position: relative;
        }
        .header h1 {
            margin: 0;
            font-size: 1.5rem;
        }
        .logout-btn {
            position: absolute;
            right: 1rem;
            top: 1rem;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            color: white;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .logout-btn:hover {
            background: rgba(255,255,255,0.3);
        }
        .metrics-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
            margin: 1rem;
        }
        .metric-card {
            background: white;
            border-radius: 8px;
            padding: 1.5rem;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }
        .metric-value {
            font-size: 2.5rem;
            font-weight: bold;
            color: #E91E63;
            margin: 0.5rem 0;
        }
        .metric-label {
            color: #666;
            font-size: 0.9rem;
        }
        .iframe-container {
            flex: 1;
            margin: 1rem;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        iframe {
            width: 100%;
            height: 100%;
            border: none;
        }
        .nav-tabs {
            display: flex;
            gap: 1rem;
            margin: 0 1rem;
            border-bottom: 2px solid #eee;
            padding-bottom: 0.5rem;
        }
        .nav-tab {
            padding: 0.5rem 1rem;
            background: none;
            border: none;
            cursor: pointer;
            font-size: 1rem;
            color: #666;
            transition: all 0.3s;
        }
        .nav-tab:hover {
            color: #E91E63;
        }
        .nav-tab.active {
            color: #E91E63;
            border-bottom: 2px solid #E91E63;
            margin-bottom: -0.5rem;
        }
    </style>
</head>
<body>
    <!-- Login Form -->
    <div class="login-container" id="loginContainer">
        <div class="login-box">
            <div class="logo">
                <h1>🎯 SkinSense AI</h1>
                <p>Monitoring Dashboard</p>
            </div>
            
            <div class="error-message" id="errorMessage"></div>
            
            <form id="loginForm" onsubmit="handleLogin(event)">
                <div class="form-group">
                    <label class="form-label" for="email">Email</label>
                    <input 
                        type="email" 
                        id="email" 
                        class="form-input" 
                        placeholder="admin@skinsense.app"
                        value="admin@skinsense.app"
                        required
                    >
                </div>
                
                <div class="form-group">
                    <label class="form-label" for="password">Password</label>
                    <input 
                        type="password" 
                        id="password" 
                        class="form-input" 
                        placeholder="Enter your password"
                        required
                    >
                </div>
                
                <button type="submit" class="btn-login" id="loginBtn">
                    Login to Dashboard
                </button>
            </form>
            
            <div class="loading" id="loading">
                Authenticating...
            </div>
        </div>
    </div>
    
    <!-- Dashboard (hidden initially) -->
    <div class="dashboard-container" id="dashboardContainer">
        <div class="header">
            <button class="logout-btn" onclick="logout()">Logout</button>
            <h1>🎯 SkinSense AI Monitoring Dashboard</h1>
        </div>
        
        <!-- Quick metrics summary -->
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-label">API Status</div>
                <div class="metric-value" id="api-status">🟢</div>
                <div class="metric-label">Healthy</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Active Users</div>
                <div class="metric-value" id="active-users">-</div>
                <div class="metric-label">Current</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Analyses Today</div>
                <div class="metric-value" id="analyses-today">-</div>
                <div class="metric-label">Total</div>
            </div>
            <div class="metric-card">
                <div class="metric-label">Avg Response Time</div>
                <div class="metric-value" id="response-time">-</div>
                <div class="metric-label">ms</div>
            </div>
        </div>
        
        <!-- Navigation tabs -->
        <div class="nav-tabs">
            <button class="nav-tab active" onclick="switchDashboard('overview')">Overview</button>
            <button class="nav-tab" onclick="switchDashboard('api-performance')">API Performance</button>
            <button class="nav-tab" onclick="switchDashboard('ai-services')">AI Services</button>
            <button class="nav-tab" onclick="switchDashboard('business-metrics')">Business Metrics</button>
        </div>
        
        <!-- Embedded Grafana dashboard -->
        <div class="iframe-container">
            <iframe 
                id="grafana-frame"
                src=""
                frameborder="0">
            </iframe>
        </div>
    </div>
    
    <script>
        let authToken = null;
        
        async function handleLogin(event) {
            event.preventDefault();
            
            const email = document.getElementById('email').value;
            const password = document.getElementById('password').value;
            const errorDiv = document.getElementById('errorMessage');
            const loginBtn = document.getElementById('loginBtn');
            const loading = document.getElementById('loading');
            
            // Reset error
            errorDiv.style.display = 'none';
            errorDiv.textContent = '';
            
            // Show loading
            loginBtn.disabled = true;
            loading.style.display = 'block';
            
            try {
                const response = await fetch('/api/v1/auth/login', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ email, password })
                });
                
                const data = await response.json();
                
                if (response.ok) {
                    authToken = data.access_token;
                    localStorage.setItem('skinsense_token', authToken);
                    showDashboard();
                } else {
                    throw new Error(data.detail || 'Invalid credentials');
                }
            } catch (error) {
                errorDiv.textContent = error.message;
                errorDiv.style.display = 'block';
            } finally {
                loginBtn.disabled = false;
                loading.style.display = 'none';
            }
        }
        
        function showDashboard() {
            document.getElementById('loginContainer').style.display = 'none';
            document.getElementById('dashboardContainer').style.display = 'flex';
            
            // Load Grafana dashboard
            const iframe = document.getElementById('grafana-frame');
            iframe.src = 'https://api.skinsense.app/monitoring/d/skinsense-overview/skinsense-ai-overview?orgId=1&refresh=5s&theme=light&kiosk';
            
            // Start fetching metrics
            fetchMetrics();
            setInterval(fetchMetrics, 5000);
        }
        
        async function fetchMetrics() {
            if (!authToken) return;
            
            try {
                // Fetch active users
                const activeUsersResponse = await fetch('/api/v1/monitoring/metrics/active-users', {
                    headers: { 'Authorization': 'Bearer ' + authToken }
                });
                if (activeUsersResponse.ok) {
                    const data = await activeUsersResponse.json();
                    document.getElementById('active-users').textContent = data.value;
                }
                
                // Fetch analyses today
                const analysesResponse = await fetch('/api/v1/monitoring/metrics/analyses-today', {
                    headers: { 'Authorization': 'Bearer ' + authToken }
                });
                if (analysesResponse.ok) {
                    const data = await analysesResponse.json();
                    document.getElementById('analyses-today').textContent = data.value;
                }
                
                // Fetch response time
                const responseTimeResponse = await fetch('/api/v1/monitoring/metrics/response-time', {
                    headers: { 'Authorization': 'Bearer ' + authToken }
                });
                if (responseTimeResponse.ok) {
                    const data = await responseTimeResponse.json();
                    document.getElementById('response-time').textContent = Math.round(data.value * 1000);
                }
            } catch (error) {
                console.error('Error fetching metrics:', error);
            }
        }
        
        function switchDashboard(dashboard) {
            const tabs = document.querySelectorAll('.nav-tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            event.target.classList.add('active');
            
            const iframe = document.getElementById('grafana-frame');
            const baseUrl = 'https://api.skinsense.app/monitoring';
            
            // Switch to the appropriate dashboard
            switch(dashboard) {
                case 'overview':
                    iframe.src = baseUrl + '/d/skinsense-overview/skinsense-ai-overview?orgId=1&refresh=5s&theme=light&kiosk';
                    break;
                case 'api-performance':
                    iframe.src = baseUrl + '/d/skinsense-api/api-performance?orgId=1&refresh=5s&theme=light&kiosk';
                    break;
                case 'ai-services':
                    iframe.src = baseUrl + '/d/skinsense-ai-services/ai-services?orgId=1&refresh=5s&theme=light&kiosk';
                    break;
                case 'business-metrics':
                    iframe.src = baseUrl + '/d/skinsense-business/business-metrics?orgId=1&refresh=5s&theme=light&kiosk';
                    break;
            }
        }
        
        function logout() {
            authToken = null;
            localStorage.removeItem('skinsense_token');
            document.getElementById('loginContainer').style.display = 'flex';
            document.getElementById('dashboardContainer').style.display = 'none';
            document.getElementById('email').value = 'admin@skinsense.app';
            document.getElementById('password').value = '';
        }
        
        // Check for existing token on load
        window.onload = function() {
            const savedToken = localStorage.getItem('skinsense_token');
            if (savedToken) {
                authToken = savedToken;
                showDashboard();
            }
        };
    </script>
</body>
</html>
"""

@router.get("/dashboard", response_class=HTMLResponse)
async def monitoring_dashboard():
    """
    Display monitoring dashboard with login form
    """
    return HTMLResponse(content=MONITORING_DASHBOARD_HTML)

@router.get("/metrics/active-users")
async def get_active_users_metric(
    current_user: UserModel = Depends(require_admin)
):
    """Get current active users count from Prometheus"""
    try:
        import httpx
        prometheus_url = settings.prometheus_url if hasattr(settings, 'prometheus_url') else "http://localhost:9090"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{prometheus_url}/api/v1/query",
                params={"query": "active_users_current"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    value = float(data["data"]["result"][0]["value"][1])
                    return {"value": int(value)}
        
        return {"value": 0}
    except Exception as e:
        return {"value": 0}

@router.get("/metrics/analyses-today")
async def get_analyses_today_metric(
    current_user: UserModel = Depends(require_admin)
):
    """Get total analyses today from Prometheus"""
    try:
        import httpx
        prometheus_url = settings.prometheus_url if hasattr(settings, 'prometheus_url') else "http://localhost:9090"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{prometheus_url}/api/v1/query",
                params={"query": "sum(increase(skin_analysis_total[24h]))"}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    value = float(data["data"]["result"][0]["value"][1])
                    return {"value": int(value)}
        
        return {"value": 0}
    except Exception as e:
        return {"value": 0}

@router.get("/metrics/response-time")
async def get_response_time_metric(
    current_user: UserModel = Depends(require_admin)
):
    """Get average response time from Prometheus"""
    try:
        import httpx
        prometheus_url = settings.prometheus_url if hasattr(settings, 'prometheus_url') else "http://localhost:9090"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{prometheus_url}/api/v1/query",
                params={
                    "query": "avg(rate(fastapi_http_request_duration_seconds_sum[5m]) / rate(fastapi_http_request_duration_seconds_count[5m]))"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and data["data"]["result"]:
                    value = float(data["data"]["result"][0]["value"][1])
                    return {"value": value}
        
        return {"value": 0}
    except Exception as e:
        return {"value": 0}

@router.get("/health/detailed")
async def detailed_health_check(
    current_user: UserModel = Depends(require_admin)
):
    """
    Detailed health check with component status (Admin only)
    """
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "components": {}
    }
    
    # Check database
    try:
        from app.database import get_database
        db = get_database()
        db.command("ping")
        health_status["components"]["database"] = {"status": "healthy", "type": "MongoDB"}
    except Exception as e:
        health_status["components"]["database"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        from app.core.redis import get_redis
        redis = get_redis()
        redis.ping()
        health_status["components"]["cache"] = {"status": "healthy", "type": "Redis"}
    except Exception as e:
        health_status["components"]["cache"] = {"status": "unhealthy", "error": str(e)}
        health_status["status"] = "degraded"
    
    # Check AI services
    health_status["components"]["ai_services"] = {
        "orbo": {"status": "healthy" if settings.orbo_ai_api_key else "not_configured"},
        "openai": {"status": "healthy" if settings.openai_api_key else "not_configured"},
        "perplexity": {"status": "healthy" if settings.perplexity_api_key else "not_configured"}
    }
    
    return health_status

# ORBO Error Monitoring Endpoints

@router.get("/orbo/errors/summary", response_model=Dict[str, Any])
async def get_orbo_error_summary(
    days: int = 7,
    current_user: UserModel = Depends(require_admin),
    db: Database = Depends(get_database)
):
    """
    Get ORBO error summary for monitoring dashboard (Admin only)
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {
            '$match': {
                'timestamp': {'$gte': start_date}
            }
        },
        {
            '$group': {
                '_id': '$error_type',
                'count': {'$sum': 1},
                'unique_users': {'$addToSet': '$user_id'},
                'latest': {'$max': '$timestamp'}
            }
        },
        {
            '$project': {
                'error_type': '$_id',
                'total_occurrences': '$count',
                'affected_users': {'$size': '$unique_users'},
                'latest_occurrence': '$latest',
                '_id': 0
            }
        },
        {
            '$sort': {'total_occurrences': -1}
        }
    ]
    
    errors = list(db.orbo_errors.aggregate(pipeline))
    
    # Calculate success rate
    total_analyses = db.skin_analyses.count_documents({
        'created_at': {'$gte': start_date}
    })
    
    total_errors = sum(e['total_occurrences'] for e in errors)
    success_rate = ((total_analyses - total_errors) / total_analyses * 100) if total_analyses > 0 else 0
    
    return {
        'period': {
            'days': days,
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        },
        'summary': {
            'total_analyses': total_analyses,
            'total_errors': total_errors,
            'success_rate': round(success_rate, 2),
            'unique_affected_users': len(set(
                uid for e in errors 
                for uid in db.orbo_errors.distinct('user_id', {'error_type': e['error_type']})
            ))
        },
        'errors_by_type': errors,
        'most_common_error': errors[0] if errors else None
    }

@router.get("/orbo/errors/trends", response_model=Dict[str, Any])
async def get_orbo_error_trends(
    days: int = 30,
    current_user: UserModel = Depends(require_admin),
    db: Database = Depends(get_database)
):
    """
    Get ORBO error trends over time (Admin only)
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    pipeline = [
        {
            '$match': {
                'timestamp': {'$gte': start_date}
            }
        },
        {
            '$group': {
                '_id': {
                    'date': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$timestamp'}},
                    'error_type': '$error_type'
                },
                'count': {'$sum': 1}
            }
        },
        {
            '$group': {
                '_id': '$_id.date',
                'errors': {
                    '$push': {
                        'type': '$_id.error_type',
                        'count': '$count'
                    }
                },
                'total': {'$sum': '$count'}
            }
        },
        {
            '$sort': {'_id': 1}
        }
    ]
    
    daily_errors = list(db.orbo_errors.aggregate(pipeline))
    
    # Also get daily success counts
    success_pipeline = [
        {
            '$match': {
                'created_at': {'$gte': start_date},
                'status': {'$ne': 'failed'}
            }
        },
        {
            '$group': {
                '_id': {'$dateToString': {'format': '%Y-%m-%d', 'date': '$created_at'}},
                'successful': {'$sum': 1}
            }
        }
    ]
    
    daily_success = {
        d['_id']: d['successful'] 
        for d in db.skin_analyses.aggregate(success_pipeline)
    }
    
    # Combine data
    trend_data = []
    for day_data in daily_errors:
        date = day_data['_id']
        trend_data.append({
            'date': date,
            'total_errors': day_data['total'],
            'successful_analyses': daily_success.get(date, 0),
            'error_breakdown': day_data['errors']
        })
    
    return {
        'period': {
            'days': days,
            'start': start_date.isoformat(),
            'end': datetime.utcnow().isoformat()
        },
        'trends': trend_data
    }

@router.get("/orbo/health", response_model=Dict[str, Any])
async def get_orbo_health_status(
    db: Database = Depends(get_database)
):
    """
    Get ORBO service health status (Public endpoint for monitoring)
    """
    try:
        # Check recent success rate (last hour)
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        recent_analyses = db.skin_analyses.count_documents({
            'created_at': {'$gte': one_hour_ago}
        })
        
        recent_failures = db.orbo_errors.count_documents({
            'timestamp': {'$gte': one_hour_ago}
        })
        
        if recent_analyses == 0:
            status = "idle"
            health_score = 100
        else:
            success_rate = ((recent_analyses - recent_failures) / recent_analyses) * 100
            health_score = success_rate
            
            if success_rate >= 95:
                status = "healthy"
            elif success_rate >= 80:
                status = "degraded"
            else:
                status = "unhealthy"
        
        # Get latest successful analysis
        latest_success = db.skin_analyses.find_one(
            {'status': 'completed'},
            sort=[('created_at', -1)]
        )
        
        # Get latest error
        latest_error = db.orbo_errors.find_one(
            {},
            sort=[('timestamp', -1)]
        )
        
        return {
            'status': status,
            'health_score': round(health_score, 2),
            'metrics': {
                'recent_analyses': recent_analyses,
                'recent_failures': recent_failures,
                'success_rate': round(health_score, 2) if recent_analyses > 0 else None
            },
            'latest_success': latest_success['created_at'].isoformat() if latest_success else None,
            'latest_error': {
                'type': latest_error.get('error_type'),
                'timestamp': latest_error['timestamp'].isoformat()
            } if latest_error else None,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            'status': 'error',
            'health_score': 0,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }