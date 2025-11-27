# auto_sign_backend/utils/http_retry.py
import time
import logging
import requests

logger = logging.getLogger(__name__)

def request_with_retries(session: requests.Session, method: str, url: str, max_retries: int = 3, backoff: int = 2, **kwargs):
    """
    封装 requests 的重试逻辑，session 可以是 requests.Session()。
    kwargs 会传给 session.request，如 data/json/headers/timeout/verify 等
    """
    attempt = 0
    while attempt < max_retries:
        try:
            resp = session.request(method, url, **kwargs)
            # 如果希望查看原始返回以便调试，可以在这里打印 resp.status_code / resp.text 的前段
            resp.raise_for_status()
            return resp
        except Exception as e:
            attempt += 1
            logger.warning("请求失败: %s %s 错误: %s 尝试 %d/%d", method, url, e, attempt, max_retries)
            time.sleep(backoff * attempt)
    # 最终失败，抛出异常并把最后一次异常信息返回
    raise RuntimeError(f"请求多次失败: {method} {url}")
