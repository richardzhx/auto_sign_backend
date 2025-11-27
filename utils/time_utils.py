# auto_sign_backend/utils/time_utils.py
from datetime import datetime

def parse_time(s: str) -> datetime:
    # 兼容原脚本的时间格式 "%Y-%m-%d %H:%M:%S"
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
