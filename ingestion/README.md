> **Historical note, added for publication.** This is the service's original README, and parts of it overstate what the code does: requests are not retried after a failure, value bet detection was never implemented, and predictions come from the data provider, not from a model. For the current state and how to run it, see the [main README](../README.md).

# FIP Operator

## 🚀 Project Overview
**FIP Operator** is a high-performance, asynchronous microservice designed to power the FIP platform's data ingestion and processing layer. It serves as the intelligent backbone for collecting, analyzing, and serving real-time football data, odds, and predictions.

This service is engineered to handle complex data pipelines, ensuring that the frontend receives accurate, up-to-the-minute information while maintaining strict rate limits with external providers.

## 🛠️ Tech Stack & Methodologies

### Core Technologies
- **Language**: Python 3.10+
- **Framework**: **FastAPI** (High-performance async web framework)
- **Database**: **PostgreSQL** with **SQLAlchemy** (ORM) and **Alembic** (Migrations)
- **Asynchronous Processing**: `asyncio` for non-blocking I/O operations
- **HTTP Client**: `httpx` for efficient async API requests

### Architecture & Patterns
- **Microservices Architecture**: Designed as a specialized operator service decoupled from the main backend.
- **Repository Pattern**: Clean separation of data access logic.
- **Singleton Pattern**: Used for database connections and API clients to manage resources efficiently.
- **Rate Limiting**: Custom implementation using `asyncio.Semaphore` to respect external API constraints (e.g., API-Football).
- **Background Jobs**: Scheduled tasks for periodic data fetching (Odds, Fixtures, Predictions) without blocking the main event loop.

### DevOps & Deployment
- **Platform**: **Railway** (PaaS)
- **CI/CD**: Git-based automated deployments
- **Environment Management**: `python-dotenv` for secure configuration
- **Containerization**: Docker-ready structure

## 🔑 Key Features

### 1. Intelligent Data Collection
- **Smart Rate Limiting**: Sophisticated throttling mechanism to maximize data throughput within strict API limits (5 req/sec).
- **Resilient Fetching**: Automatic retries and error handling for external API calls.
- **Historical Data Analysis**: Capabilities to fetch and process historical match data for accuracy verification.

### 2. Odds Tracking System
- **Real-time Odds**: Fetches and stores live odds from multiple bookmakers.
- **Odds History**: Tracks odds movement over time to identify value bets.
- **Best Odds Calculation**: Automatically identifies the best available odds for specific markets.

### 3. Prediction Accuracy Engine
- **Automated Verification**: Systematically compares predictions against actual match results.
- **Performance Metrics**: Calculates accuracy scores for different prediction types (Winner, Goals, etc.).
- **Self-Correction**: Data-driven feedback loop to monitor prediction model performance.

## 🔧 Configuration

### Environment Variables
The application requires the following environment variables (never commit these to version control):
```bash
DATABASE_URL=postgresql://user:password@host:port/dbname
FOOTBALL_API_KEY=your_api_key_here
LOG_LEVEL=INFO
ENVIRONMENT=production
```

### Local Development
1. **Clone the repository**
   ```bash
   git clone https://github.com/firechair/football-intelligence-platform.git
   cd football-intelligence-platform/ingestion
   ```

2. **Install dependencies**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Run the service**
   ```bash
   cd ingestion
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

## 📊 API Documentation
Once running, full interactive documentation (Swagger UI) is available at:
- **Local**: `http://localhost:8000/docs`
- **Production**: `https://example.invalid/docs`

## 🛡️ Security & Best Practices
- **Sensitive Data Protection**: All API keys and database credentials are managed via environment variables.
- **Input Validation**: Pydantic models ensure data integrity for all incoming requests.
- **Error Handling**: Comprehensive global exception handling to prevent information leakage.

---
*Built with ❤️ for the FIP Platform*
