from pydantic import BaseModel, ConfigDict, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ApplicationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = ""
    environment: str = "demo"
    health_url: str | None = None


class IncidentCreate(BaseModel):
    title: str
    description: str = ""
    severity: str = "warning"
    application_id: int | None = None


class ApprovalRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    comment: str = ""


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
