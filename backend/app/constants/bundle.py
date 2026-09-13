"""配布パッケージ（PyInstaller）へ同梱するファイルの名前（CODING_RULES.md「コード上の名前」）。

同梱**先**の名前は、ビルド時（`scripts/build_package.py` の `--add-data`）と実行時
（`app/config.py` の `resolve_bundled_path` を呼ぶ各所）の**両方**が同じ文字列を必要とする。
片方だけ変えると「開発環境では動くが配布物だけが壊れる」という、実行するまで表面化しない
不具合になるため、ここを単一の情報源とする。

ビルドスクリプトがこのモジュールだけを取り込めば済むようにしてある（以前は `app/main.py` から
取り込んでおり、ビルドの副作用としてFastAPIアプリ全体が生成されていた）。
"""

#: フロントエンドのビルド済み静的ファイルの同梱先フォルダ名。
FRONTEND_DIST_DIR_NAME = "frontend_dist"

#: Alembicの設定ファイル（バンドル直下へ置く。`alembic/`本体もあわせて同梱する）。
ALEMBIC_INI_FILE_NAME = "alembic.ini"
ALEMBIC_DIR_NAME = "alembic"

#: アプリバージョン・使用ライブラリのスナップショット（起動画面「システム情報」SC-15が読む）。
BUILD_INFO_FILE_NAME = "build_info.json"

#: トレイ・通知の文言を解決するためのロケールファイルの同梱先フォルダ名
#: （原本はフロントエンドと共有する `frontend/src/locales/ja.json`。`app/locales.py`参照）。
LOCALES_DIR_NAME = "locales"

#: アプリアイコン（exe・トレイ・通知で共用）。`scripts/generate_icon.py`が生成する。
ASSETS_DIR_NAME = "assets"
ICON_FILE_NAME = "michinari.ico"
