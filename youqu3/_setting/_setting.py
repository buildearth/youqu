import dataclasses
import enum
import os

from youqu3._setting._dynamic import _DynamicSetting


class _Setting(_DynamicSetting):
    """YouQu Config"""

    PASSWORD: str = os.environ.get("YOUQU_PASSWORD") or "1"

    TIMEOUT = os.environ.get("YOUQU_TIMEOUT") or 300
    LOG_LEVEL = os.environ.get("YOUQU_LOG_LEVEL") or "INFO"
    RERUNS = os.environ.get("YOUQU_RERUNS") or 1
    RECORD_FAILED_NUM = os.environ.get("YOUQU_RECORD_FAILED_NUM") or 1

    # REPORT SERVER
    REPORT_SERVER_IP = "127.0.0.1/127.0.0.2"
    REPORT_PORT = 5656
    REPORT_BASE_PATH = "~/report"

    # SLAVES
    SLAVES = os.environ.get("SLAVES")

    PYPI_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"



    @enum.unique
    class FixedCsvTitle(enum.Enum):
        case_id = "脚本ID"
        skip_reason = "跳过原因"
        fixed = "确认修复"
        removed = "废弃用例"

    @enum.unique
    class ConfStr(enum.Enum):
        SKIP = "skip"
        SKIPIF = "skipif"
        FIXED = "fixed"
        PASSED = "passed"
        FAILED = "failed"
        SKIPPED = "skipped"
        REMOVED = "removed"
        SKIP_INDEX = "skip_index"
        FIXED_INDEX = "fixed_index"
        REMOVED_INDEX = "removed_index"
        PMS_ID_INDEX = "pms_id_index"


setting = _Setting()
