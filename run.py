# auto_sign_backend/run.py
# 最终版：极简美观 + 连堂课永不漏签 + 你最爱的日志风格

import os
import time
import logging
from datetime import datetime

from auto_sign_backend.client.iclass_client import IClassClient
from auto_sign_backend.utils.coords import parse_coord
from auto_sign_backend.logic.scheduler import build_sign_windows

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ====================== 配置 ======================
DEFAULT_CONFIG = {
    "base_url": "https://iclass.buaa.edu.cn:8181",
    "ve_base_url": "http://iclass.buaa.edu.cn:88",
    "phone": os.getenv("ICLASS_PHONE", "25375093"),
    "password_env_var": "SIGN_PASS",
    "password": None,
    "sign_url": "https://iclass.buaa.edu.cn:8181/app/course/stu_auto_sign.action",
    "dry_run": False,
    "verify_ssl": False,
    "timeout_sec": 10,
    "before_minute_default": 5,
    "after_minute_default": 30,
    "fake_longitude": 116.397451,
    "fake_latitude": 39.909187,
    "manual_mac": "A0:EE:1A:E0:A2:0E",
    "log_file": "auto_sign.log",
}

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("auto_sign")

def load_config():
    cfg = DEFAULT_CONFIG.copy()
    cfg["password"] = cfg["password"] or os.environ.get(cfg["password_env_var"])
    if not cfg["password"]:
        logger.warning("未找到密码，请检查环境变量 SIGN_PASS")
    return cfg

def run_auto_sign(cfg: dict):
    # 日志同时写文件
    if cfg["log_file"]:
        fh = logging.FileHandler(cfg["log_file"], encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)

    client = IClassClient(cfg["base_url"], cfg["ve_base_url"],
                          verify_ssl=cfg["verify_ssl"], timeout=cfg["timeout_sec"])

    # 登录
    try:
        client.login(cfg["phone"], cfg["password"])
    except Exception as e:
        logger.exception("登录失败: %s", e)
        return

    # 取今日课程
    today = datetime.now().strftime("%Y%m%d")
    try:
        sched = client.get_course_sched(today)
    except Exception as e:
        logger.exception("获取课程表失败: %s", e)
        return

    courses = sched.get("result", []) if isinstance(sched, dict) else []
    if not courses:
        logger.info("今天没有课程")
        return

    # 你最爱的三条日志
    logger.info("今天课程列表（含教室经纬度）:")
    for i, c in enumerate(courses, 1):
        lon = parse_coord(c.get("classroomLongitude"), cfg["fake_longitude"])
        lat = parse_coord(c.get("classroomLongitude"), cfg["fake_latitude"])
        logger.info("%d. %s (教室: %s) 经度: %.6f, 纬度: %.6f, 开始: %s, 结束: %s, id=%s",
                    i, c.get("courseName", "未知"), c.get("classroomName", "未知"),
                    lon, lat,
                    c.get("classBeginTime", "未知"), c.get("classEndTime", "未知"),
                    c.get("courseSchedId", c.get("id", "未知")))

    # 构建签到窗口并打印
    try:
        qxkt = client.get_qxkt_sign_time()
        before_min = int(qxkt.get("result", [{}])[0].get("before_minute", cfg["before_minute_default"])) if qxkt.get("result") else cfg["before_minute_default"]
        after_min  = int(qxkt.get("result", [{}])[0].get("after_minute", cfg["after_minute_default"])) if qxkt.get("result") else cfg["after_minute_default"]
    except:
        before_min = cfg["before_minute_default"]
        after_min  = cfg["after_minute_default"]

    courses = build_sign_windows(courses, before_min, after_min)

    for c in courses:
        logger.info("课程 %s 签到窗口: %s ~ %s",
                    c.get("courseName"),
                    c["sign_begin"].strftime("%Y-%m-%d %H:%M:%S"),
                    c["sign_end"].strftime("%Y-%m-%d %H:%M:%S"))

    logger.info("自动选择全部课程，共 %d 门。", len(courses))
    logger.info("进入自动签到检测循环（每分钟检测一次，直到所有课程签到完成）")

    # ========== 核心循环（已完美解决连堂课）==========
    signed = set()

    while True:
        now = datetime.now()
        all_done = True

        for c in courses:
            sched_id = c.get("courseSchedId") or c.get("id")
            if sched_id in signed:
                continue

            if now >= c["sign_begin"]:                     # 只要到了开始时间就签
                all_done = False
                logger.info("检测到课程 [%s] 进入签到窗口，准备签到...", c.get("courseName"))

                # 位置
                try:
                    r = client.get_socket_info().get("result", {})
                except:
                    r = {}
                mac = cfg["manual_mac"] or "00:db:6e:66:8a:d8"
                lon = parse_coord(r.get("classroomLongitude"), parse_coord(c.get("classroomLongitude"), cfg["fake_longitude"]))
                lat = parse_coord(r.get("classroomLatitude"), parse_coord(c.get("classroomLatitude"), cfg["fake_latitude"]))

                payload = {
                    "id": client.user_id,
                    "courseSchedId": sched_id,
                    "routerInfo": mac,
                    "longitude": lon,
                    "latitude": lat,
                    "machineInfo": "Android",
                    "signTime": now.strftime("%Y-%m-%d %H:%M:%S")
                }

                if cfg["dry_run"]:
                    logger.info("dry_run 模式，跳过实际请求")
                else:
                    try:
                        resp = client.send_sign(cfg["sign_url"], payload)
                        logger.info("签到返回 JSON: %s", resp)          # 你最想要的这一行
                    except Exception as e:
                        logger.error("签到异常: %s", e)

                signed.add(sched_id)
                logger.info("课程 [%s] 签到完成。", c.get("courseName"))
                time.sleep(3)          # 防风控

            elif now < c["sign_begin"]:
                all_done = False

        if all_done:
            logger.info("所有课程均已签到完成，程序退出。")
            break

        time.sleep(60)

def main():
    cfg = load_config()
    if not cfg.get("ve_base_url"):
        cfg["ve_base_url"] = cfg["base_url"].replace(":8181", ":88") if ":8181" in cfg["base_url"] else cfg["base_url"]

    try:
        run_auto_sign(cfg)
    except KeyboardInterrupt:
        print("\n签到程序已手动停止，祝你好运~")
        logger.info("程序被手动终止")

if __name__ == "__main__":
    main()