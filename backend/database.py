import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DB_URL = os.getenv("DATABASE_URL", "mysql+pymysql://root:@127.0.0.1:3306/ai_digital_db")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 全局Base类
Base = declarative_base()

# 对外暴露get_db函数
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()