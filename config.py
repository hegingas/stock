import os
import sys

# 修复 Windows 终端中文乱码
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(DATA_DIR, "stock.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Email / SMTP 配置（全部从环境变量读取）──
SMTP_HOST = os.getenv("STOCK_SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("STOCK_SMTP_PORT", "587"))
SMTP_USER = os.getenv("STOCK_SMTP_USER", "")
SMTP_PASS = os.getenv("STOCK_SMTP_PASS", "")
SMTP_FROM = os.getenv("STOCK_SMTP_FROM", "")
SMTP_TO = os.getenv("STOCK_SMTP_TO", "")
SMTP_USE_TLS = os.getenv("STOCK_SMTP_TLS", "1") == "1"
