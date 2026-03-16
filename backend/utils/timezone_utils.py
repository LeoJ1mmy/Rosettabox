"""
時區工具模組 - 統一管理台北時區
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

# 台北時區 (UTC+8)
TAIPEI_TZ = timezone(timedelta(hours=8))

def now_taipei() -> datetime:
    """獲取台北時區的當前時間"""
    return datetime.now(TAIPEI_TZ)

def to_taipei_time(dt: datetime) -> datetime:
    """轉換時間到台北時區"""
    if dt.tzinfo is None:
        # 如果沒有時區信息，假設為UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TAIPEI_TZ)

def to_taipei_isoformat(dt: Optional[datetime] = None) -> str:
    """轉換為台北時區的ISO格式字符串"""
    if dt is None:
        dt = now_taipei()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc).astimezone(TAIPEI_TZ)
    else:
        dt = dt.astimezone(TAIPEI_TZ)
    return dt.isoformat()

def parse_taipei_time(time_str: str) -> datetime:
    """解析時間字符串為台北時區時間"""
    try:
        dt = datetime.fromisoformat(time_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TAIPEI_TZ)
        else:
            dt = dt.astimezone(TAIPEI_TZ)
        return dt
    except ValueError:
        # 降級處理
        dt = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
        return dt.replace(tzinfo=TAIPEI_TZ)

def format_taipei_time(dt: Optional[datetime] = None, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """格式化台北時區時間"""
    if dt is None:
        dt = now_taipei()
    elif dt.tzinfo is None:
        dt = dt.replace(tzinfo=TAIPEI_TZ)
    else:
        dt = dt.astimezone(TAIPEI_TZ)
    return dt.strftime(fmt)