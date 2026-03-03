"""Schemas package initialization.

This module serves as the initializer for the schemas package, which contains Pydantic
models for request and response validation. It imports all the necessary schema models
from the submodules, making them available for use throughout the application, just by
importing from the schemas package itself.
"""

from .error import *
from .model import *
