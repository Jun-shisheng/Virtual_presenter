from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base, get_db
import models
import schemas
import random

# 启动时自动创建全新规范数据表
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI数字人聊天系统")

# 全局跨域配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"code": 200, "msg": "✅ AI数字人后端运行正常"}


# 注册接口：生成唯一8位UID + 严格大小写用户名
@app.post("/register")
def register(user: schemas.UserRequest, db=Depends(get_db)):
    all_users = db.query(models.User).all()

    # 原生Python严格区分大小写校验
    for u in all_users:
        if u.username == user.username:
            raise HTTPException(status_code=400, detail="该用户名已被注册")

    # 循环生成不重复的8位数字UID
    while True:
        random_num = random.randint(10000000, 99999999)
        new_uid = str(random_num)
        exist_uid = db.query(models.User).filter(models.User.uid == new_uid).first()
        if not exist_uid:
            break

    # 创建新用户
    new_user = models.User(
        uid = new_uid,
        username = user.username,
        password = user.password
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {
        "code": 200,
        "msg": "注册成功",
        "uid": new_user.uid,
        "username": new_user.username
    }


# 登录接口：返回UID，全程UID做用户唯一标识
@app.post("/login")
def login(user: schemas.UserRequest, db=Depends(get_db)):
    all_users = db.query(models.User).all()
    target_user = None

    for u in all_users:
        if u.username == user.username:
            target_user = u
            break

    if not target_user:
        raise HTTPException(status_code=400, detail="用户名不存在，请检查大小写")
    if target_user.password != user.password:
        raise HTTPException(status_code=400, detail="密码错误")

    return {
        "code": 200,
        "msg": "登录成功",
        "uid": target_user.uid,
        "username": target_user.username
    }


# 私聊聊天接口 + UID绑定入库
@app.post("/chat")
def chat(chat: schemas.ChatRequest, db=Depends(get_db)):
    # UID校验，防止伪造越权
    current_user = db.query(models.User).filter(models.User.uid == chat.user_uid).first()
    if not current_user:
        raise HTTPException(status_code=400, detail="用户身份无效，请重新登录")

    # AI默认回复，后续可接入大模型
    ai_reply_text = f"收到你的消息：{chat.message} 😊"

    # 写入聊天记录，绑定用户唯一UID
    new_record = models.ChatRecord(
        user_uid = chat.user_uid,
        user_content = chat.message,
        ai_reply = ai_reply_text,
        chat_type = 0, # 标记为私人私聊
        room_id = 0
    )

    db.add(new_record)
    db.commit()
    db.refresh(new_record)

    return {
        "code": 200,
        "user_content": new_record.user_content,
        "ai_reply": new_record.ai_reply,
        "create_time": str(new_record.create_time)
    }


# 获取当前用户专属私聊历史（UID精准隔离，绝对看不到他人数据）
@app.get("/my_chat_history")
def get_private_history(user_uid: str, db=Depends(get_db)):
    my_records = db.query(models.ChatRecord)\
        .filter(
            models.ChatRecord.user_uid == user_uid,
            models.ChatRecord.chat_type == 0
        )\
        .order_by(models.ChatRecord.create_time.asc())\
        .all()

    return {"code": 200, "data": my_records}