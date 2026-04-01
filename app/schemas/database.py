from typing import List

from pydantic import BaseModel, Field


class Category(BaseModel):
    name: str
    comment: str


class CategoriesResponse(BaseModel):
    """A Pydantic model for the categories response payload."""

    categories: List[Category] = Field(
        ...,
        description="A list of category names, and their corresponding comments.",
    )
