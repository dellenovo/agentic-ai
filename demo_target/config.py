# ⚠️ 演示用假密钥（非真实凭据）—— 已改为环境变量读取
import os

MYAPP_API_KEY = os.environ.get("MYAPP_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_client():
    return {"api_key": MYAPP_API_KEY, "db": DATABASE_URL}
