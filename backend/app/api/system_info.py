"""システム情報のAPI（仕様書6.14 SC-15）。"""

from fastapi import APIRouter

from app.config import REPO_ROOT
from app.schemas.system_info import LibraryInfoRead, SystemInfoRead
from app.services import system_info_service

router = APIRouter(tags=["system-info"])


def _serialize(build_info: system_info_service.BuildInfo) -> SystemInfoRead:
    return SystemInfoRead(
        app_version=build_info.app_version,
        python_version=build_info.python_version,
        built_at=build_info.built_at,
        backend_libraries=[LibraryInfoRead(**vars(lib)) for lib in build_info.backend_libraries],
        frontend_libraries=[
            LibraryInfoRead(**vars(lib)) for lib in build_info.frontend_libraries
        ],
    )


@router.get("/system-info", response_model=SystemInfoRead)
def get_system_info() -> SystemInfoRead:
    """`GET /api/v1/system-info`: システム情報（SC-15）を`SystemInfoRead`で返す。"""
    return _serialize(system_info_service.get_system_info(REPO_ROOT))
