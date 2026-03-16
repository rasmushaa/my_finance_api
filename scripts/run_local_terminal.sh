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

# Generate auth tokens for testing
echo ""
echo "=== Generated Auth Tokens ==="

# Generate user token
echo ""
echo "User Token (role: user):"
uv run python -c "
import sys
sys.path.append('.')

# Mock user client for token generation
class MockUserClient:
    def get_user_by_email(self, email):
        users = {
            'user@example.com': {'role': 'user'},
            'admin@example.com': {'role': 'admin'}
        }
        return users.get(email)

from app.services.jwt import AppJwtService
import asyncio

mock_client = MockUserClient()
jwt_service = AppJwtService(mock_client)

async def generate_token():
    return await jwt_service.auth_with_delay('user@example.com')

user_token = asyncio.run(generate_token())
print(user_token)
"

# Generate admin token
echo ""
echo "Admin Token (role: admin):"
uv run python -c "
import sys
sys.path.append('.')

# Mock user client for token generation
class MockUserClient:
    def get_user_by_email(self, email):
        users = {
            'user@example.com': {'role': 'user'},
            'admin@example.com': {'role': 'admin'}
        }
        return users.get(email)

from app.services.jwt import AppJwtService
import asyncio

mock_client = MockUserClient()
jwt_service = AppJwtService(mock_client)

async def generate_token():
    return await jwt_service.auth_with_delay('admin@example.com')

admin_token = asyncio.run(generate_token())
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
