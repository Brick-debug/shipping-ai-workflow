# config/settings.py
import os
import sys
from dotenv import load_dotenv

# Load local configuration when present. The public demo does not require it.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')

if os.path.exists(env_path):
    load_dotenv(env_path)

# 2. AI 配置 (对应你的 .env 变量名)
API_KEY = os.getenv("DEEPSEEK_API_KEY")
API_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
MODEL_NAME = os.getenv("AI_MODEL_NAME", "deepseek-chat") # 默认值防止报错

# 3. 邮箱配置 (对应你的 .env 变量名)
IMAP_SERVER = os.getenv("IMAP_SERVER")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# 4. 数据路径配置
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_EMAIL_DIR = os.path.join(DATA_DIR, "input_emails")
REFERENCE_DIR = os.path.join(DATA_DIR, "reference")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")

# 自动创建文件夹
for _dir in [RAW_EMAIL_DIR, REFERENCE_DIR, OUTPUT_DIR]:
    os.makedirs(_dir, exist_ok=True)

# 简单的自检逻辑 (当直接运行此文件时执行)
if __name__ == "__main__":
    print("-" * 30)
    print("配置检查:")
    print(f"API Key 存在: {'✅' if API_KEY else '❌'}")
    print(f"API Base URL: {API_BASE_URL}")
    print(f"邮箱账户: {EMAIL_ACCOUNT}")
    print(f"数据目录: {DATA_DIR}")
    print("-" * 30)
