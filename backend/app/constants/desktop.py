"""デスクトップ常駐（トレイ・通知・自動起動）の基盤定数（Phase37）。

Windowsへ登録する識別子やレジストリの位置であり、利用者が設定画面から変えるものではない
ため`app_setting`ではなくここに置く（`constants/domain.py`と同じ整理）。トレイ・通知・
自動起動の3モジュールから同じ値を書くと片方だけ直す事故が起きるため集約する。
"""

#: Windowsがアプリを識別する名前（AppUserModelID）。Microsoftの規約は
#: `CompanyName.ProductName.SubProduct.VersionInformation` で、空白不可・128文字以内・
#: 各節はパスカルケース（https://learn.microsoft.com/en-us/windows/win32/shell/appids ）。
#: バージョンを含めないのは、更新版が旧版と同じ識別子を引き継ぐようにするため（同ページ
#: 「If an application is not intended to be used in that way, the VersionInformation
#: should be omitted」）。通知の送信元表示・通知設定画面での並びがこの識別子で決まるため、
#: **一度配布したら変更しない**（変えると利用者が設定した通知のオン/オフが引き継がれない）。
APP_USER_MODEL_ID = "Michinari.DesktopApp"

#: 通知の送信元としてAppUserModelIDを登録するレジストリキー（HKEY_CURRENT_USER配下）。
#: デスクトップアプリがトーストを出すにはAppUserModelIDの登録が要る（Microsoft公式
#: 「How to enable desktop toast notifications through an AppUserModelID」を参照）。
#: 公式文書はスタートメニューのショートカットへ`System.AppUserModel.ID`を付ける方式を
#: 案内しているが、それにはCOM（IShellLink+IPropertyStore）が必要で依存が増える。ここでは
#: 同じ登録をレジストリで行う方式を採る（windows-toastsが公式に同梱する
#: `register_hkey_aumid.py` と同じ方式。2026-09-13にWindows 11 Pro 26200で、通知が
#: 受理され`Notifications\Settings`配下へ記録されることを確認済み）。
#: HKEY_CURRENT_USER配下のため管理者権限を必要としない。
AUMID_REGISTRY_KEY_TEMPLATE = r"SOFTWARE\Classes\AppUserModelId\{app_user_model_id}"
AUMID_REGISTRY_KEY = AUMID_REGISTRY_KEY_TEMPLATE.format(app_user_model_id=APP_USER_MODEL_ID)
AUMID_DISPLAY_NAME_VALUE = "DisplayName"
AUMID_ICON_URI_VALUE = "IconUri"

#: Windowsサインイン時の自動起動を登録するレジストリキーと値名（HKEY_CURRENT_USER配下）。
#: スタートアップフォルダへのショートカット方式ではなくこちらを採るのは、`.lnk`の生成に
#: COMが必要で依存が増えるのに対し、こちらは標準ライブラリ`winreg`だけで登録・解除・
#: 状態確認が完結し、テストも書けるため。利用者からはタスクマネージャーの
#: 「スタートアップ アプリ」に見え、そこから無効化もできる。
LAUNCH_AT_LOGIN_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
LAUNCH_AT_LOGIN_VALUE_NAME = "Michinari"

#: サーバが待ち受けるホスト。
BIND_HOST = "0.0.0.0"
#: ブラウザで画面を開くときの宛先ホスト。サーバは全インタフェースで待ち受けるが、
#: 開くのは常にループバックにする（利用者自身の端末の画面を開くため）。
LOCAL_HOST = "127.0.0.1"

#: 記録画面（日次報告 SC-06）のパス。フロントエンドの
#: `frontend/src/constants/routes.ts` の `ROUTES.dailyReport` と対になる値である。
#: 言語が違うため機械的に共有できないが、片方だけ変えると通知から開いた先が404になる。
#: `tests/test_desktop_urls.py` が両ファイルの整合を検証する。
DAILY_REPORT_PATH_TEMPLATE = "/records/{date}/report"

#: ログの出力先フォルダ名・ファイル名（`%LOCALAPPDATA%\Michinari\logs\`配下）。
#: コンソールを出さなくなったため、起動時の失敗や通知の記録はここだけに残る。
LOG_DIR_NAME = "logs"
LOG_FILE_NAME = "michinari.log"
#: ログの世代管理（1ファイルあたりの上限バイト数と保持世代数）。常駐して動き続けるため、
#: 上限を設けないとログが際限なく増える。
LOG_MAX_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
