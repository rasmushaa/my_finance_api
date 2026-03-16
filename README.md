

# My Finance API

A modern FastAPI-based REST API for financial data management with integrated ML model serving capabilities. Built with clean architecture principles, comprehensive authentication.

## Architecture

### Clean Architecture Design
- **Layered Architecture**: Clear separation between API, business logic, and data layers
- **Dependency Injection**: Container-based DI system for loose coupling and testability
- **Protocol-based Design**: Type-safe interfaces for service contracts
- **Exception Handling**: Comprehensive error management with structured responses

### Core Components
- **API Layer** (`app/api/`): FastAPI routers, dependencies, and request/response handling
- **Business Logic** (`app/services/`): Domain services for categories, authentication, ML models, and users
- **Core Infrastructure** (`app/core/`): Security, error handling, database clients, and DI container
- **Data Contracts** (`app/schemas/`): Pydantic models for API requests, responses, and data validation

## Project Structure

```
app/
├── main.py                   # FastAPI application entry point
├── api/                      # API layer
│   ├── routers/              # Route handlers by feature
│   └── dependencies/         # FastAPI dependency providers
├── core/                     # Core infrastructure
│   └── exceptions/           # Structured exception hierarchy
├── services/                 # Business logic services
└── schemas/                  # Data contracts and validation
tests/                        # Comprehensive test suite
scripts/                      # Development and deployment scripts
```

## Key Features

### Authentication & Authorization
- **Google OAuth 2.0**: Secure authentication via Google accounts
- **JWT Tokens**: Stateless authentication with configurable expiration
- **Role-based Access Control**: Admin and user role enforcement
- **Security Middleware**: Bearer token validation with custom error handling

### ML Model Integration
- **Async Model Loading**: Non-blocking model initialization with MLflow integration
- **Model Versioning**: Complete metadata tracking and version management
- **Feature Validation**: Input validation against canonical feature sets
- **Health Monitoring**: Model status and readiness checks
- **Prediction API**: High-performance inference endpoints

### Error Handling & Observability
- **Structured Errors**: Consistent error response format across all endpoints
- **Error Codes**: Machine-readable error categorization
- **Comprehensive Logging**: Detailed request/response logging
- **Health Checks**: Application and dependency health monitoring

### Data Management
- **BigQuery Integration**: Cloud-native data storage and querying
- **Category Management**: Financial transaction categorization
- **User Management**: Profile and preference handling

## Development Setup

### Prerequisites
- Python 3.11+
- uv package manager
- Google Cloud CLI (for private packages and authentication)

### Installation
```bash
# Install dependencies with private registry access
./scripts/uv_sync.sh

# Or manually with authentication
TOKEN="$(gcloud auth print-access-token)"
uv sync --extra-index-url "https://oauth2accesstoken:${TOKEN}@europe-north1-python.pkg.dev/rasmus-prod/python-packages/simple/"
```

### Environment Configuration
```bash
# Required environment variables
export APP_JWT_SECRET="your-jwt-secret"
export APP_JWT_EXP_DELTA_MINUTES="60"
export GOOGLE_OAUTH_CLIENT_ID="your-oauth-client-id"
export GOOGLE_OAUTH_CLIENT_SECRET="your-oauth-client-secret"
```

### Running the API

#### Development Server
```bash
# Using provided script
./scripts/run_local_terminal.sh

# Or directly with uvicorn
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Docker Deployment
```bash
# Local containerized deployment
./scripts/run_local_docker.sh

# Or build and run manually
docker build -t my-finance-api .
docker run -p 8000:8000 my-finance-api
```

### Testing Strategy

#### Running Tests
```bash
# Run all tests
pytest

# Unit tests for business logic
pytest tests/test_*.py -v

# API integration tests
pytest tests/test_api_*.py -v

# With coverage
pytest --cov=app tests/
```

#### Test Architecture
- **Unit Tests**: Service-level testing with dependency mocking
- **Integration Tests**: End-to-end API testing with TestClient
- **Dependency Injection**: Container-based mocking for isolated testing
- **Authentication Testing**: Mock auth providers for secure endpoint testing

## API Documentation

### Interactive Documentation
- **Swagger UI**: Available at `http://localhost:8000/docs`
- **ReDoc**: Available at `http://localhost:8000/redoc`

### Main Endpoints
- `POST /auth/google/code` - Google OAuth code exchange
- `GET /data/categories/{type}` - Financial category retrieval
- `POST /model/predict` - ML model predictions
- `GET /model/status` - Model health and readiness
- `GET /model/metadata` - Model version and information
- `GET /health` - Application health check

## Deployment Considerations

### Production Configuration
- Environment-based configuration management
- Structured logging with appropriate levels
- Health check endpoints for load balancer integration
- Graceful shutdown handling for ML model cleanup

### Scalability Features
- Async request handling
- Singleton pattern for heavy resources (ML models, DB connections)
- Lazy loading of dependencies
- Background task support for model loading
