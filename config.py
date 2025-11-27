# auto_sign_backend/config.py

import os

class Config:
    USERNAME = os.getenv("ICLASS_USERNAME")
    PASSWORD = os.getenv("ICLASS_PASSWORD")

    # 经纬度
    LATITUDE = os.getenv("LATITUDE")
    LONGITUDE = os.getenv("LONGITUDE")

    # API 基本地址
    BASE_URL = "https://iclass.sunnu.edu.cn"   # 你原脚本里用的固定域名

    # 通知（可选）
    PUSH_KEY = os.getenv("PUSH_KEY")

config = Config()
