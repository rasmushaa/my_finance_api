from typing import List

from pydantic import BaseModel, Field


class CategoriesResponse(BaseModel):
    """A Pydantic model for the categories response payload."""

    categories: List[str] = Field(
        ...,
        description="A list of category names.",
    )
