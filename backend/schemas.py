from pydantic import BaseModel

class UserRequest(BaseModel):
    username: str
    password: str

# 聊天请求改用UID传递
class ChatRequest(BaseModel):
    user_uid: str
    message: str