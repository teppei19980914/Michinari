"""システム情報のAPI（仕様書6.14 SC-15）。"""

import datetime as dt

from fastapi import APIRouter, Response

from app.config import REPO_ROOT
from app.schemas.system_info import LibraryInfoRead, SystemInfoRead
from app.services import system_info_service, system_log_export_service

router = APIRouter(tags=["system-info"])


def _serialize(build_info: system_info_service.BuildInfo) -> SystemInfoRead:
    return SystemInfoRead(
        app_version=build_info.app_version,
        python_version=build_info.python_version,
        built_at=build_info.built_at,
        backend_libraries=[LibraryInfoRead(**vars(lib)) for lib in build_info.backend_libraries],
        frontend_libraries=[LibraryInfoRead(**vars(lib)) for lib in build_info.frontend_libraries],
    )


@router.get("/system-info", response_model=SystemInfoRead)
def get_system_info() -> SystemInfoRead:
    """`GET /api/v1/system-info`: システム情報（SC-15）を`SystemInfoRead`で返す。"""
    return _serialize(system_info_service.get_system_info(REPO_ROOT))


@router.get("/system-info/logs/export")
def export_logs(date_from: dt.date, date_to: dt.date) -> Response:
    """`GET /api/v1/system-info/logs/export`: 期間を指定して診断ログをダウンロードする
    （SC-15、Phase40 診断ログ出力・トレース強化）。"""
    content = system_log_export_service.export_logs(date_from, date_to)
    filename = f"michinari-logs_{date_from}_{date_to}.log"
    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
