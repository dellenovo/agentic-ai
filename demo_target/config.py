# ⚠️ 演示用 —— 从环境变量读取凭据（不再硬编码，符合安全最佳实践）
import os

MYAPP_API_KEY = os.environ.get("MYAPP_API_KEY", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")


def get_client():
    return {"api_key": MYAPP_API_KEY, "db": DATABASE_URL}