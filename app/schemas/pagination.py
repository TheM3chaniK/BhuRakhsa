import math
from typing import Generic, Sequence, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard generic paginated response container."""

    items: Sequence[T] = Field(..., description="List of paginated items")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, le=100, description="Number of items per page")
    total: int = Field(..., ge=0, description="Total count of items matching filters")
    total_pages: int = Field(..., ge=0, description="Total number of pages")

    @classmethod
    def create(
        cls, items: Sequence[T], total: int, page: int, page_size: int
    ) -> "PaginatedResponse[T]":
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return cls(
            items=items,
            page=page,
            page_size=page_size,
            total=total,
            total_pages=total_pages,
        )
