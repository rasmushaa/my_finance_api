"""User lookup service for authentication and authorization flows."""

import logging
import re
from typing import Dict

logger = logging.getLogger(__name__)


class UsersService:
    """Service for managing user operations.

    This service provides an abstraction layer over database operations for users,
    making it easier to test and mock.
    """

    def __init__(self, db_client=None):
        """Initialize the users service.

        Parameters
        ----------
        db_client :
            Database client instance used for credential lookups.
        """
        self.db_client = db_client

    def _validate_email(self, email: str) -> bool:
        """Validate email format and reject obvious injection patterns.

        Parameters
        ----------
        email : str
            Candidate email address from external auth provider.

        Returns
        -------
        bool
            ``True`` when input looks like a safe email string.
        """
        # Handle None and non-string inputs
        if email is None:
            return False

        # Convert to string if not already
        if not isinstance(email, str):
            return False

        # Check for empty or whitespace-only strings
        if not email.strip():
            return False

        # Basic email regex pattern - more restrictive for security
        email_pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

        # Check basic email format
        if not re.match(email_pattern, email):
            return False

        # Additional security checks for SQL injection attempts
        dangerous_chars = ["'", '"', ";", "--", "/*", "*/", "xp_", "sp_"]
        if any(char in email for char in dangerous_chars):
            return False

        # Check for common SQL injection patterns
        sql_injection_patterns = [
            r"(\s|^)(or|and)\s+['\"]?1['\"]?\s*=\s*['\"]?1['\"]?",
            r"union\s+select",
            r"drop\s+table",
            r"insert\s+into",
            r"update\s+set",
            r"delete\s+from",
        ]

        email_lower = email.lower()
        for pattern in sql_injection_patterns:
            if re.search(pattern, email_lower, re.IGNORECASE):
                return False

        return True

    def _sanitize_email(self, email: str) -> str:
        """Sanitize email by escaping single quotes.

        Parameters
        ----------
        email : str
            Email string to sanitize.

        Returns
        -------
        str
            Sanitized email string.
        """
        # Escape single quotes by doubling them (SQL standard)
        return email.replace("'", "''")

    def get_user_by_email(self, email: str) -> Dict[str, str]:
        """Fetch user identity and role by email.

        Parameters
        ----------
        email : str
            User email to resolve.

        Returns
        -------
        Dict[str, str]
            Mapping containing user information (for example ``email`` and ``role``),
            or empty dict for invalid/non-existent users.
        """
        # Validate input for security and format
        if not self._validate_email(email):
            logger.warning(
                f"Invalid email format or potential security threat: {email}"
            )
            return {}

        normalized_email = email.strip()

        # Client handles database errors.
        sql = f"""
        SELECT
            UserEmail as email,
            UserRole as role
        FROM
            `{self.db_client.dataset}.d_credentials`
        WHERE
            UserEmail = @email
            AND _RowStatus != @deleted_status
        """  # nosec B608
        df = self.db_client.sql_to_pandas(
            sql,
            params={"email": normalized_email, "deleted_status": "d"},
        )
        logger.debug(f"Fetched user information from BigQuery:\n{df}")

        # Return the result as dict or empty dict if no results
        info = df.to_dict(orient="records")
        return info[0] if info else {}
