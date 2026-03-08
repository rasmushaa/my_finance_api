#!/bin/bash

# Helper to sync with private PyPI registry using gcloud auth token
# Note: the UV creds are in format UV_INDEX_<toml url name>_USERNAME and UV_INDEX_<toml url name>_PASSWORD
TOKEN="$(gcloud auth print-access-token)"
export UV_INDEX_PRIVATE_USERNAME="oauth2accesstoken"
export UV_INDEX_PRIVATE_PASSWORD="${TOKEN}"
uv sync --upgrade
