from pydantic import BaseModel, Field


class UserStats(BaseModel):
    """Aggregate statistics for user accounts."""

    total: int = Field(..., ge=0, description="Total registered users")
    civilians: int = Field(..., ge=0, description="Total civilian accounts")
    area_officers: int = Field(..., ge=0, description="Total area officers")
    super_admins: int = Field(..., ge=0, description="Total super administrators")
    active: int = Field(..., ge=0, description="Total active accounts")
    inactive: int = Field(..., ge=0, description="Total deactivated accounts")


class AreaStats(BaseModel):
    """Aggregate statistics for geographical areas."""

    total: int = Field(..., ge=0, description="Total registered areas")
    active: int = Field(..., ge=0, description="Total active areas")
    inactive: int = Field(..., ge=0, description="Total deactivated areas")


class OfficerStats(BaseModel):
    """Aggregate statistics for area officer assignments."""

    assigned: int = Field(..., ge=0, description="Officers with at least one assigned area")
    unassigned: int = Field(..., ge=0, description="Officers without any assigned area")


class AdminSummaryResponse(BaseModel):
    """Overall system administrative metrics summary."""

    users: UserStats = Field(..., description="User account breakdown")
    areas: AreaStats = Field(..., description="Geographical area breakdown")
    officers: OfficerStats = Field(..., description="Officer assignment breakdown")
