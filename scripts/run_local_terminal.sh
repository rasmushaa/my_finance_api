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

# Run the FastAPI application using Uvicorn
echo "Starting FastAPI application with Uvicorn..."
uv run uvicorn app.main:app --host 0.0.0.0 --port 8081 --reload
