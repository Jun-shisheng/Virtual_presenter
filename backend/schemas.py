from pydantic import BaseModel, Field

class UserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)

class ChatRequest(BaseModel):
    user_uid: str = Field(..., min_length=8, max_length=8)
    message: str = Field(..., min_length=1, max_length=500)