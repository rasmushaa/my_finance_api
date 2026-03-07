#!/bin/bash

# Function to load environment variables from .env file
load_env() {
    echo "Loading environment variables from .env..."
    if [ -f .env ]; then
        # Read the .env.dev file line by line
        while IFS= read -r line; do
            # Skip comments and empty lines
            [[ "$line" =~ ^#.*$ || -z "$line" ]] && continue
            # Export the variable
            export "$line"
            echo "$line" | sed 's/=.*/=***/'
        done < .env
    else
        echo ".env file not found."
        exit 1
    fi
}

# Load environment variables
load_env

# Load model artifacts if MLflow is configured
if [[ -n "$MLFLOW_TRACKING_URI" ]]; then
    echo ""
    echo "=== Loading Model Artifacts ==="
    echo "Loading model artifacts for local development..."
    ENV=${ENV:-"dev"} uv run --group dev python scripts/load_model_artifacts.py
    echo "Model artifacts loaded successfully!"
else
    echo ""
    echo "⚠️  MLflow not configured - skipping model loading"
    echo "Set MLFLOW_TRACKING_URI and credentials in .env to enable model loading"
fi

# Generate auth tokens for testing
echo ""
echo "=== Generated Auth Tokens ==="

# Generate user token
echo ""
echo "User Token (role: user):"
uv run python -c "
import sys
sys.path.append('.')
from app.auth import issue_app_jwt
user_token = issue_app_jwt('user@example.com', 'user')
print(user_token)
"

# Generate admin token
echo ""
echo "Admin Token (role: admin):"
uv run python -c "
import sys
sys.path.append('.')
from app.auth import issue_app_jwt
admin_token = issue_app_jwt('admin@example.com', 'admin')
print(admin_token)
"

echo ""
echo "=== Tokens generated successfully! ==="
echo "Copy the tokens above to use in your API requests."
echo "Add them to your request headers as: Authorization: Bearer <token>"
echo ""

# Run the FastAPI application using Uvicorn
echo "Starting FastAPI application with Uvicorn..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
