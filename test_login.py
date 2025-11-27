# auto_sign_backend/test_login.py
import os
import logging
from auto_sign_backend.client.iclass_client import IClassClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test_login")

BASE = "https://iclass.buaa.edu.cn:8181"
VE = "http://iclass.buaa.edu.cn:88"

phone = os.getenv("ICLASS_PHONE") or "25375093"
pwd = os.getenv("SIGN_PASS") or "zhx20070327"
if not pwd:
    print("请先设置环境变量 SIGN_PASS（校园密码）")
    raise SystemExit(1)

client = IClassClient(BASE, VE, verify_ssl=False, timeout=10)
try:
    js = client.login(phone, pwd)
    print("LOGIN OK, return:")
    print(js)
except Exception as e:
    print("LOGIN FAILED:", e)
    # 最重要：如果失败，请把完整异常/输出贴给我（注意不要公开密码）
