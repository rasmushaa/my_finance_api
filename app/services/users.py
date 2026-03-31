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
            db_client:
                Database client instance to handle database operations.
        """
        self.db_client = db_client

    def _validate_email(self, email: str) -> bool:
        """Validate email format and security.

        Parameters
        ----------
            email: Input to validate as email

        Returns
        -------
            bool: True if email is valid and safe, False otherwise
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
        """Sanitize email by escaping dangerous characters.

        Parameters
        ----------
            email: Email string to sanitize

        Returns
        -------
            str: Sanitized email string
        """
        # Escape single quotes by doubling them (SQL standard)
        return email.replace("'", "''")

    def get_user_by_email(self, email: str) -> Dict[str, str]:
        """Get all user information.

        Parameters
        ----------
            email:
                The email of the user to fetch information for.
        Returns
        -------
            Dict[str, str]:
                Contains user information such as email, and role.
                Returns empty dict if user not found or invalid input.
        """
        # Validate input for security and format
        if not self._validate_email(email):
            logger.warning(
                f"Invalid email format or potential security threat: {email}"
            )
            return {}

        # Sanitize the email for SQL safety
        sanitized_email = self._sanitize_email(email.strip())

        # Client handles errors
        sql = f"""
        SELECT
            UserName as email,
            Role as role
        FROM
            {self.db_client.dataset}.d_credentials
        WHERE
            UserName = '{sanitized_email}'
            AND _RowStatus != 'd'
        """  # nosec B608
        df = self.db_client.sql_to_pandas(sql)
        logger.debug(f"Fetched user information from BigQuery:\n{df}")

        # Return the result as dict or empty dict if no results
        info = df.to_dict(orient="records")
        return info[0] if info else {}
