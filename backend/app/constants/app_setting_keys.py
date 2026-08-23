"""app_setting.key の定数化。

複数ファイルでキー文字列を直書きすると片方だけ修正漏れが起きるため、
コード上で参照するキーはここに集約する（値の初期投入は init/seed_data.py）。
"""

SERVER_PORT = "server.port"
THRESHOLD_WARNING_RATIO = "threshold.warning_ratio"
THRESHOLD_REPLAN_OVERRUN_DAYS = "threshold.replan_overrun_days"
CALENDAR_DAY_BOUNDARY_HOUR = "calendar.day_boundary_hour"
HOLIDAY_TREAT_AS_BUFFER = "holiday.treat_as_buffer"
