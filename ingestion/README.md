# FIP Operator - Production Ready

## Overview
FIP Operator is a FastAPI service that handles odds tracking, predictions collection, and fixtures management for the FIP platform. It's designed to run on Railway with PostgreSQL database.

## Production Configuration

### Environment Variables (Railway)
```
DATABASE_URL=postgresql://postgres:REDACTED@example.invalid:5432/railway
FOOTBALL_API_KEY=REDACTED
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Service Configuration
- **Port**: 8080 (Railway requirement)
- **Database**: PostgreSQL (Railway shared instance)
- **API Base**: `/api/v1`
- **CORS**: Configured for production domains

## API Endpoints

### Core Endpoints
- `GET /` - Health check
- `GET /api/v1/fixtures/today` - Today's fixtures
- `GET /api/v1/fixtures/range` - Fixtures by date range
- `GET /api/v1/odds/best/{fixture_id}` - Best odds for fixture
- `GET /api/v1/predictions/today` - Today's predictions
- `GET /api/v1/assets/logo` - Logo proxy service

### Admin Endpoints
- `GET /api/v1/admin/status` - Service status
- `POST /api/v1/admin/cleanup` - Manual cleanup
- `GET /api/v1/admin/database-status` - Database status

## Deployment

### Railway Deployment
1. Push to `firechair/ingestion` repository
2. Railway auto-deploys from repository
3. Environment variables are set in Railway dashboard
4. Service runs on port 8080

### Local Development
```bash
cd ingestion
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## Database Schema
- **Odds Tracking**: Historical odds data with bookmaker information
- **Predictions**: Match predictions and analysis
- **Fixtures**: Match information and tracking status

## Rate Limiting
- **Odds Collection**: 2 requests/second
- **Predictions**: 1 request every 2 seconds
- **Total API Limit**: 4 requests/second (coordinated with main backend)

## Monitoring
- Automatic odds collection every 4 hours
- Daily fixtures sync every 2 hours
- Predictions collection every 12 hours
- Data cleanup every 24 hours
