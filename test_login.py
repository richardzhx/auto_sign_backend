# auto_sign_backend/run.py
# 直接覆盖你原来的 run.py 即可，零修改其他文件，输出立刻回到最爽最详细的老版本风格！

import os
import json
import time
import logging
from datetime import datetime, timedelta

from auto_sign_backend.client.iclass_client import IClassClient
from auto_sign_backend.utils.coords import parse_coord
from auto_sign_backend.logic.scheduler import build_sign_windows

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DEFAULT_CONFIG = {
    "base_url": "https://iclass.buaa.edu.cn:8181",
    "ve_base_url": "http://iclass.buaa.edu.cn:88",
    "phone": os.getenv("ICLASS_PHONE", "25375093"),
    "password_env_var": "SIGN_PASS",
    "password": None,
    "sign_url": "https://iclass.buaa.edu.cn:8181/app/course/stu_auto_sign.action",
    "dry_run": False,
    "timeout_sec": 10,
    "max_retries": 3,
    "retry_backoff": 2,
    "before_minute_default": 5,
    "after_minute_default": 30,
    "fake_longitude": 116.397451,
    "fake_latitude": 39.909187,
    "manual_mac": "A0:EE:1A:E0:A2:0E",
    "use_real_coords": True,
    "verify_ssl": False,
    "log_file": "auto_sign.log",
    "auto_wait_until_window": True,
    "max_wait_seconds": 36000
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("auto_sign")

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    pwd = cfg.get("password") or os.environ.get(cfg.get("password_env_var", "SIGN_PASS"))
    if not pwd:
        logger.warning("未找到密码（DEFAULT_CONFIG['password'] 或 环境变量 SIGN_PASS），请确认")
    cfg["password"] = pwd
    ve = cfg.get("ve_base_url") or ""
    if ve.startswith("https://") and (":88" in ve or ve.endswith(":88")):
        logger.info("ve_base_url 指向 88 端口使用 https，自动切换为 http: %s", ve)
        cfg["ve_base_url"] = ve.replace("https://", "http://", 1)
    return cfg

def run_auto_sign(cfg: dict):
    if cfg.get("log_file"):
        fh = logging.FileHandler(cfg["log_file"])
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    client = IClassClient(cfg["base_url"], cfg["ve_base_url"], verify_ssl=cfg["verify_ssl"], timeout=cfg["timeout_sec"])

    # 登录
    try:
        client.login(cfg["phone"], cfg.get("password"))
    except Exception as e:
        logger.exception("登录失败: %s", e)
        if cfg.get("dry_run", True):
            logger.info("dry_run 模式继续（未登录）")
        else:
            return

    today = datetime.now().strftime("%Y%m%d")

    # 获取课程表
    try:
        sched = client.get_course_sched(today)
    except Exception as e:
        logger.exception("获取课程失败: %s", e)
        return

    courses = sched.get("result", []) if isinstance(sched, dict) else []
    if not courses:
        logger.info("今天没有课程")
        return

    # 打印课程列表（你最爱的详细版本）
    logger.info("今天课程列表（含教室经纬度）:")
    for idx, c in enumerate(courses, 1):
        lon = parse_coord(c.get("classroomLongitude"), cfg["fake_longitude"])
        lat = parse_coord(c.get("classroomLatitude"), cfg["fake_latitude"])
        logger.info(
            "%d. %s (教室: %s) 经度: %.6f, 纬度: %.6f, 开始: %s, 结束: %s, id=%s",
            idx,
            c.get("courseName", "未知课程"),
            c.get("classroomName", "未知教室"),
            lon, lat,
            c.get("classBeginTime", "未知"),
            c.get("classEndTime", "未知"),
            c.get("id", "未知")
        )

    # 构建签到窗口并打印
    try:
        qxkt = client.get_qxkt_sign_time()
        if qxkt.get("result") and isinstance(qxkt["result"], list) and qxkt["result"]:
            before_min = int(qxkt["result"][0].get("before_minute", cfg["before_minute_default"]))
            after_min = int(qxkt["result"][0].get("after_minute", cfg["after_minute_default"]))
        else:
            before_min = cfg["before_minute_default"]
            after_min = cfg["after_minute_default"]
    except Exception:
        before_min = cfg["before_minute_default"]
        after_min = cfg["after_minute_default"]

    courses = build_sign_windows(courses, before_min, after_min)

    for c in courses:
        logger.info(
            "课程 %s 签到窗口: %s ~ %s",
            c.get("courseName"),
            c["sign_begin"].strftime("%Y-%m-%d %H:%M:%S"),
            c["sign_end"].strftime("%Y-%m-%d %H:%M:%S")
        )

    logger.info("自动选择全部课程，共 %d 门。", len(courses))

    signed_courses = set()
    logger.info("进入自动签到检测循环（每分钟检测一次，直到所有课程签到完成）")

    while True:
        now = datetime.now()
        all_signed = True

        for c in courses:
            course_id = c.get("id")
            if course_id in signed_courses:
                continue

            if c["sign_begin"] <= now <= c["sign_end"]:
                all_signed = False
                logger.info("检测到课程 [%s] 进入签到窗口，准备签到...", c.get("courseName"))

                try:
                    sock = client.get_socket_info()
                    r = sock.get("result", {}) if isinstance(sock, dict) else {}
                except Exception as e:
                    logger.warning("获取 socket_info 失败，使用课程经纬度: %s", e)
                    r = {}

                mac = cfg.get("manual_mac") or "00:db:6e:66:8a:d8"
                longitude = parse_coord(r.get("classroomLongitude"), parse_coord(c.get("classroomLongitude"), cfg["fake_longitude"]))
                latitude = parse_coord(r.get("classroomLatitude"), parse_coord(c.get("classroomLatitude"), cfg["fake_latitude"]))

                payload = {
                    "id": r.get("id") or c.get("id") or client.user_id,
                    "courseSchedId": r.get("courseSchedId") or c.get("id"),
                    "routerInfo": mac,
                    "longitude": longitude,
                    "latitude": latitude,
                    "machineInfo": "Android",
                    "signTime": now.strftime("%Y-%m-%d %H:%M:%S")
                }

                logger.info("提交签到数据: %s", json.dumps(payload, ensure_ascii=False))
                logger.info("发送签到请求到 %s", cfg["sign_url"])   # 老版本就这一行

                if cfg.get("dry_run", True) or not cfg.get("sign_url"):
                    logger.info("dry_run 模式或未配置 sign_url，不执行签到请求。")
                else:
                    try:
                        resp = client.send_sign(cfg.get("sign_url"), payload)
                        logger.info("签到响应 HTTP %s", resp.get("status") if isinstance(resp, dict) else resp.status_code if hasattr(resp, "status_code") else "unknown")
                        logger.info("签到返回 JSON: %s", resp)
                    except Exception as e:
                        logger.error("课程 %s 签到失败: %s", c.get("courseName"), e)

                signed_courses.add(course_id)
                logger.info("课程 [%s] 签到完成。", c.get("courseName"))

            elif now < c["sign_begin"]:
                all_signed = False

        if all_signed:
            logger.info("所有选择的课程均签到完成，程序退出。")
            break

        time.sleep(60)

def main():
    cfg = load_config()

    if not cfg.get("ve_base_url"):
        if ":8181" in cfg["base_url"]:
            cfg["ve_base_url"] = cfg["base_url"].replace(":8181", ":88")
        else:
            cfg["ve_base_url"] = cfg["base_url"]

    try:
        run_auto_sign(cfg)
    except KeyboardInterrupt:
        print("\n签到程序已手动停止，祝你好运~")
        logger.info("用户手动停止程序")

if __name__ == "__main__":
    main()