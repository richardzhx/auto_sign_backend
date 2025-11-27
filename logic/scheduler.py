# auto_sign_backend/logic/scheduler.py
from datetime import datetime
from datetime import timedelta
from auto_sign_backend.utils.time_utils import parse_time

def build_sign_windows(courses: list, before_min: int, after_min: int):
    """
    将课程列表每条加入 sign_begin/sign_end 字段（datetime 对象）
    courses: 期望每项含 classBeginTime/classEndTime 格式 "%Y-%m-%d %H:%M:%S"
    """
    out = []
    for c in courses:
        class_begin_str = c.get("classBeginTime")
        class_end_str = c.get("classEndTime")
        if not class_begin_str or not class_end_str:
            continue
        try:
            begin = parse_time(class_begin_str)
            end = parse_time(class_end_str)
        except Exception:
            continue
        c["sign_begin"] = begin - timedelta(minutes=before_min)
        c["sign_end"] = end + timedelta(minutes=after_min)
        out.append(c)
    return out
