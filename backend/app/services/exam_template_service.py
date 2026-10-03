"""資格試験テンプレートの読込（仕様書「資格モードのテンプレート」、実装フェーズ分割計画書Phase38）。

テンプレートは`app_setting`/`prompt_template`のような起動時シード（`app/init/seed_data.py`）
ではなく、`GET /exam-templates`呼び出しの都度`backend/app/templates/exams/`配下を
走査して読み込む。テンプレートJSONの追加・編集がアプリの再起動なしに選択肢へ反映される
という完了条件のためである。

ファイル読込・パースの例外処理は`calendar_service.import_holidays`（祝日CSV取込）と
同じ考え方に倣うが、複数ファイルを扱う都合上「1ファイルの不備で一覧全体を失敗させない」
方針を取る点が異なる。不正なテンプレートは警告ログを出して読み飛ばし、正常なテンプレート
だけを返す。
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from app.config import REPO_ROOT, resolve_bundled_path
from app.constants.bundle import EXAM_TEMPLATES_DIR_NAME
from app.schemas.exam_template import ExamTemplateRead

logger = logging.getLogger(__name__)

_SOURCE_DIR = REPO_ROOT / "backend" / "app" / "templates" / "exams"


def _templates_dir() -> Path:
    """テンプレートJSONの配置先を解決する（配布パッケージ対応、`app/locales.py`と同じ方式）。"""
    return resolve_bundled_path(EXAM_TEMPLATES_DIR_NAME, _SOURCE_DIR)


def list_exam_templates(directory: Path | None = None) -> list[ExamTemplateRead]:
    """テンプレート一覧を読み込む（`GET /exam-templates`の実体）。

    引数:
        directory: 読み込み対象ディレクトリ。省略時は配布パッケージ対応込みの既定パス
            （テストでは差し替えて任意のディレクトリを検証できるようにするため）。

    返り値:
        読込に成功したテンプレートの一覧（ファイル名の昇順）。ディレクトリが存在しない
        場合は空リスト。
    """
    target_dir = directory if directory is not None else _templates_dir()
    if not target_dir.is_dir():
        return []

    templates: list[ExamTemplateRead] = []
    for path in sorted(target_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            templates.append(ExamTemplateRead.model_validate(raw))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, PydanticValidationError) as exc:
            logger.warning("資格テンプレートの読込に失敗しました: %s (%s)", path.name, exc)
    return templates
