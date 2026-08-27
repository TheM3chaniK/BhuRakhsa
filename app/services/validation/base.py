from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from app.models.property_profile import PropertyProfile
    from app.models.validation_result import ValidationResult


class Validator(ABC):
    """Abstract interface for external validation services (Government Database, GIS/Cadastral)."""

    @abstractmethod
    async def validate(self, profile: "PropertyProfile") -> List["ValidationResult"]:
        """Execute validation against external reference sources."""
        pass
