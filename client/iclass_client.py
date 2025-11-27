# auto_sign_backend/client/iclass_client.py
import json
import logging
from typing import Dict, Any
import requests

from auto_sign_backend.utils.http_retry import request_with_retries

logger = logging.getLogger(__name__)

class IClassClient:
    def __init__(self, base_url: str, ve_base_url: str, verify_ssl: bool = True, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.ve_base_url = ve_base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "student_5.0.1.2_android_9_20__110000"})
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self.session_id = None
        self.user_id = None

    def login(self, phone: str, password: str) -> Dict[str, Any]:
        url = f"{self.base_url}/app/user/login.action"
        data = {
            "phone": phone,
            "password": password,
            "verificationType": "1",
            "verificationUrl": "http://iclass.buaa.edu.cn:88/ve/webservices/mobileCheck.shtml?method=mobileLogin&username=${0}&password=${1}&lx=${2}",
            "userLevel": "1"
        }
        # 这里保留 verify=self.verify_ssl，若你在 dev 环境 SSL 问题可把 verify=False
        resp = request_with_retries(self.session, "POST", url, data=data, timeout=self.timeout, verify=self.verify_ssl)
        # 尝试解析 json；若失败记录文本以便调试
        try:
            js = resp.json()
        except Exception:
            logger.warning("登录接口返回非 JSON，响应前1000字符：%s", resp.text[:1000])
            raise RuntimeError(f"登录接口未返回 JSON, HTTP {resp.status_code}")
        if js.get("STATUS") != "0":
            # 登录失败，记录返回内容完整以便定位
            logger.error("登录返回 STATUS != 0: %s", js)
            raise RuntimeError("登录失败: " + str(js))
        res = js["result"]
        self.session_id = res.get("sessionId")
        self.user_id = res.get("id")
        if self.session_id:
            # 有些接口需要 sessionId 放在 headers 或 Cookie
            self.session.headers.update({"sessionId": self.session_id})
            self.session.headers.update({"Cookie": f"JSESSIONID={self.session_id}"})
        logger.info("登录成功: sessionId=%s, userId=%s", self.session_id, self.user_id)
        return js

    def get_course_sched(self, date_str: str) -> Dict[str, Any]:
        url = f"{self.base_url}/app/course/get_stu_course_sched.action?id={self.user_id}&dateStr={date_str}"
        resp = request_with_retries(self.session, "GET", url, timeout=self.timeout, verify=self.verify_ssl)
        try:
            return resp.json()
        except Exception:
            logger.warning("get_course_sched 返回非 JSON，文本前500字符：%s", resp.text[:500])
            raise

    def get_stu_sign_time(self, date_str: str) -> Dict[str, Any]:
        url = f"{self.base_url}/app/common/get_stu_sign_time.action?id={self.user_id}&dateStr={date_str}"
        resp = request_with_retries(self.session, "GET", url, timeout=self.timeout, verify=self.verify_ssl)
        try:
            return resp.json()
        except Exception:
            logger.warning("get_stu_sign_time 返回非 JSON，文本前500字符：%s", resp.text[:500])
            raise

    def get_qxkt_sign_time(self) -> Dict[str, Any]:
        url = f"{self.ve_base_url}/ve/webservices/app_qxkt.shtml?method=getQxktSignTime"
        resp = request_with_retries(self.session, "GET", url, timeout=self.timeout, verify=False)
        try:
            return resp.json()
        except Exception:
            try:
                return json.loads(resp.text)
            except Exception:
                logger.warning("get_qxkt_sign_time 解析失败，返回空 result")
                return {"result": []}

    def get_socket_info(self) -> Dict[str, Any]:
        url = f"{self.base_url}/app/service/get_socket_info.action?id={self.user_id}"
        resp = request_with_retries(self.session, "GET", url, timeout=self.timeout, verify=self.verify_ssl)
        try:
            return resp.json()
        except Exception:
            logger.warning("get_socket_info 返回非 JSON，文本前500字符：%s", resp.text[:500])
            raise

    def send_sign(self, sign_url: str, payload: dict) -> Dict[str, Any]:
        """
        修正版签到请求：强制使用表单提交 + 携带 sessionId/Cookie
        """
        logger.info("发送签到请求到 %s", sign_url)
        headers = {
            "User-Agent": "student_5.0.1.2_android_9_20__110000",
            "Content-Type": "application/x-www-form-urlencoded",
            "Connection": "Keep-Alive",
        }

        # 关键：手动加上 Cookie/SessionId
        if self.session_id:
            headers["sessionId"] = self.session_id
            headers["Cookie"] = f"JSESSIONID={self.session_id}"

        try:
            resp = request_with_retries(
                self.session,
                "POST",
                sign_url,
                data=payload,
                headers=headers,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
        except Exception as e:
            logger.error("签到请求异常: %s", e)
            return {"error": str(e)}

        logger.info("签到响应 HTTP %s", resp.status_code)
        snippet = resp.text[:500]

        try:
            js = resp.json()
            logger.info("签到返回 JSON: %s", js)
            return js
        except Exception:
            logger.warning("签到接口返回非 JSON，原始内容前500字符：%s", snippet)
            return {"_raw_text": snippet, "_status_code": resp.status_code}
