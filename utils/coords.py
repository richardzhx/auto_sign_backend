# auto_sign_backend/utils/coords.py
def parse_coord(value, default=None):
    """
    安全解析经纬度：将 None 或 "null" 视作缺失，返回 default
    """
    if value is None:
        return default
    if isinstance(value, str) and value.strip().lower() == "null":
        return default
    try:
        return float(value)
    except Exception:
        return default
