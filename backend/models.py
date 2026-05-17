from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime
from database import Base

class User(Base):
    __tablename__ = "users"

    # 内部主键（仅系统内部用）
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    # 对外全局唯一8位UID，用户唯一标识
    uid = Column(String(8), unique=True, nullable=False, index=True)
    username = Column(String(20), nullable=False)
    password = Column(String(20), nullable=False)
    create_time = Column(DateTime, default=datetime.now)


class ChatRecord(Base):
    __tablename__ = "chat_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 绑定用户全局UID，永久不变
    user_uid = Column(String(8), nullable=False, index=True)
    user_content = Column(Text, nullable=False)
    ai_reply = Column(Text, nullable=False)

    # 预留直播间/公私聊扩展字段
    chat_type = Column(Integer, default=0, comment="0=私人私聊 1=公共聊天室")
    room_id = Column(Integer, default=0, comment="公共房间ID，私聊为0")
    is_allow_train = Column(Integer, default=1, comment="是否允许用于AI训练 0否1是")

    create_time = Column(DateTime, default=datetime.now)