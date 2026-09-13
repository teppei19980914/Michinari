"""バックエンドが参照するロケールキーの定数化（CODING_RULES.md「コード上の名前」）。

文言そのものは`frontend/src/locales/ja.json`にあり、ここにあるのは**キー名だけ**である。
トレイ・通知・起動失敗ダイアログの3箇所から同じキーを書くと綴り間違いが片方だけ残るため、
参照するキーはここへ集約する（`app/locales.py`のdocstringも参照）。

キーの実在は`tests/test_desktop_locales.py`が`ja.json`と突き合わせて検証する。
"""

# システムトレイ（実装スコープA）。
TRAY_TOOLTIP = "desktop.tray.tooltip"
TRAY_OPEN = "desktop.tray.open"
TRAY_QUIT = "desktop.tray.quit"

# 記録リマインド通知（実装スコープC）。日種別ごとに文面を変える
# （PLAN=通常の督促、BUFFER=休みの日向けに軽くする。OFF=除外日は通知しない）。
NOTIFICATION_SOURCE_NAME = "desktop.notification.sourceName"
NOTIFICATION_PLAN_TITLE = "desktop.notification.plan.title"
NOTIFICATION_PLAN_BODY = "desktop.notification.plan.body"
NOTIFICATION_BUFFER_TITLE = "desktop.notification.buffer.title"
NOTIFICATION_BUFFER_BODY = "desktop.notification.buffer.body"

# 起動失敗の通知（コンソールを出さなくなったため、従来`Michinari.bat`の`pause`が
# 担っていた「何が起きたか利用者に伝える」役割をダイアログが引き継ぐ）。
# `*_BODY`は枠であり、原因を表す下2つが`{{detail}}`へ差し込まれて画面に出る。
STARTUP_ERROR_TITLE = "desktop.startupError.title"
STARTUP_ERROR_BODY = "desktop.startupError.body"
STARTUP_ERROR_SERVER_START_FAILED = "desktop.startupError.serverStartFailed"
STARTUP_ERROR_SERVER_NOT_RESPONDING = "desktop.startupError.serverNotResponding"
