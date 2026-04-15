"""Generate local development JWT tokens and persist them to `.env`.

This utility issues one user token and one admin token using ``AppJwtService`` with a
mocked user backend. Generated values are written to:

- ``LOCAL_DEV_USER_TOKEN``
- ``LOCAL_DEV_ADMIN_TOKEN``

Token lifetime follows ``APP_JWT_EXP_DELTA_MINUTES`` from current environment.
Intended for local development and integration testing only.
"""

import sys

import dotenv

sys.path.append(".")  # Ensure the root directory is in the path to import app modules
dotenv.load_dotenv()

from app.services.jwt import AppJwtService


class MockUserClient:
    def get_user_by_email(self, email):
        users = {
            "user@example.com": {"role": "user"},
            "admin@example.com": {
                "role": "admin"
            },  # Local admin identity used by integration tests.
        }
        return users.get(email)


mock_client = MockUserClient()
jwt_service = AppJwtService(mock_client)

user_token, user_role = jwt_service.authenticate("user@example.com")
admin_token, admin_role = jwt_service.authenticate("admin@example.com")

# Check if .env file exists and read existing content
try:
    with open(".env") as f:
        existing_content = f.read()
except FileNotFoundError:
    existing_content = ""

# Update or append tokens
lines = existing_content.split("\n")
updated_lines = []
user_token_found = False
admin_token_found = False

for line in lines:
    if line.startswith("LOCAL_DEV_USER_TOKEN="):
        updated_lines.append(f"LOCAL_DEV_USER_TOKEN={user_token}")
        user_token_found = True
    elif line.startswith("LOCAL_DEV_ADMIN_TOKEN="):
        updated_lines.append(f"LOCAL_DEV_ADMIN_TOKEN={admin_token}")
        admin_token_found = True
    else:
        updated_lines.append(line)

# Append missing tokens
if not user_token_found or not admin_token_found:
    if updated_lines and updated_lines[-1] != "":
        updated_lines.append("")
    if not user_token_found:
        updated_lines.append(f"LOCAL_DEV_USER_TOKEN={user_token}")
    if not admin_token_found:
        updated_lines.append(f"LOCAL_DEV_ADMIN_TOKEN={admin_token}")

with open(".env", "w") as f:
    f.write("\n".join(updated_lines))

print("Tokens written to .env file")
