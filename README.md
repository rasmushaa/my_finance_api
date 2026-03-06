

# Finance API

A FastAPI-based REST API for financial data management with ML model predictions. Built with dependency injection, containerized services, and comprehensive testing.

## Architecture

### Service Layer Design
- **Dependency Injection Container**: Clean separation of concerns using `app/services/container.py`
- **Service Classes**: Business logic isolated in dedicated service classes (`CategoriesService`, `ModelStore`)
- **Cloud Integration**: Google Cloud Platform integration for data storage and ML models

### API Design
- **Request/Response Schemas**: All API contracts defined in `app/schemas/`
- **Authentication**: JWT-based user and admin authentication
- **Error Handling**: Structured error responses with specific error codes
- **Health Checks**: Built-in health monitoring endpoints

## Project Structure

```
app/
├── main.py               # FastAPI application entry point
├── schemas/              # Request/response models
└── services/             # Business logic layer
    └─── container.py     # Dependency injection container
tests/                    # Comprehensive test suite
├── test_*.py             # Unit tests for services
└── test_api_*.py         # Integration tests for endpoints
```

## Key Features

### ML Model Integration
- Async model loading with MLflow
- Model versioning and metadata management
- Feature validation and prediction endpoints
- Model health monitoring

### Testing Strategy
- **Unit Tests**: Service-level testing with mocked dependencies
- **Integration Tests**: End-to-end API testing using FastAPI TestClient
- **Dependency Mocking**: Container-based dependency overrides for isolated testing

## Development Setup

### Prerequisites
- Python 3.11+
- uv package manager
- Google Cloud CLI (for private packages)

### Installation
```bash
# Authenticate for private packages
TOKEN="$(gcloud auth print-access-token)"
uv sync \
  --extra-index-url "https://oauth2accesstoken:${TOKEN}@{LOCATION}-python.pkg.dev/{PROJECT}/{REPO}/simple/"
```

### Running Tests
```bash
# Run all tests
pytest

# Run service unit tests
pytest tests/test_*.py

# Run API integration tests
pytest tests/test_api_*.py
```

### Running the API
```bash
# Development server
uvicorn app.main:app --reload

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
