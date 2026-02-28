#!/bin/bash

# This script loads the model artifacts for the specified model name 
# and alias from MLflow Model Registry, and saves them to a local directory,
# used for local development and testing. It also saves the model metadata for reference.
# The actual load_model_artifacts.py runs in CI/CD pipeline, but this script can be used locally to load the same artifacts.
# The .env should contain the necessary environment variables for MLflow tracking URI and credentials.
# Model name and alias can be overridden by setting MODEL_NAME and MODEL_ALIAS environment variables before running the script.

load_env() {
    echo "Loading environment variables from .env..."
    if [ -f .env ]; then
        # Read the .env file line by line
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
load_env
uv run scripts/load_model_artifacts.py