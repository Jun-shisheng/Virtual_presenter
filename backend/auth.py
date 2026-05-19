"""JWT 令牌鉴权 — 创建、校验、依赖注入"""
import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import SessionLocal
import models

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "anchor-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 72

security_scheme = HTTPBearer(auto_error=False)


def create_token(uid: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {"sub": uid, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    """校验 token，返回 uid；无效则抛 HTTPException"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        uid: str = payload.get("sub")
        if uid is None:
            raise HTTPException(status_code=401, detail="令牌无效")
        return uid
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="令牌已过期，请重新登录")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="令牌验证失败")


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security_scheme),
) -> models.User:
    """从 Header 或 Query 中提取 token，校验并返回 User 对象"""
    token = None
    if credentials:
        token = credentials.credentials

    if not token:
        raise HTTPException(status_code=401, detail="请先登录")

    uid = verify_token(token)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.uid == uid).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    finally:
        db.close()


def get_current_user_from_query(token: str | None = None) -> models.User:
    """SSE GET 接口用，从 Query 参数取 token"""
    if not token:
        raise HTTPException(status_code=401, detail="请先登录")
    uid = verify_token(token)
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.uid == uid).first()
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user
    finally:
        db.close()
