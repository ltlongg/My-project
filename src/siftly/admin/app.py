"""Dựng ứng dụng HTTP của trang quản lí: API dưới /api và bản dựng của ứng dụng React."""

from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session, sessionmaker

from siftly.admin import auth, channels, sections, sources
from siftly.admin.auth import Account
from siftly.admin.deps import Invalid
from siftly.collectors import Collector
from siftly.models import ChannelKind, SourceKind
from siftly.publishers import Publisher


def create_app(
    session_factory: sessionmaker[Session],
    account: Account,
    *,
    collectors: Mapping[SourceKind, Collector] | None = None,
    publishers: Mapping[ChannelKind, Publisher] | None = None,
    web_dir: Path | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    """`collectors` và `publishers` dùng để bấm thử Nguồn và gửi tin nhắn thử tới Kênh đăng; loại
    nào vắng thì báo máy chủ chưa có. `web_dir` là bản dựng của ứng dụng React; None là chỉ có API.
    `clock` cho biết bây giờ là lúc nào, để tính hạn của phiên đăng nhập và tình trạng Nguồn."""
    app = FastAPI(title="Siftly", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.session_factory = session_factory
    app.state.account = account
    app.state.collectors = collectors or {}
    app.state.publishers = publishers or {}
    app.state.clock = clock
    app.add_exception_handler(RequestValidationError, _invalid)
    app.add_exception_handler(Invalid, _invalid)

    api = APIRouter(prefix="/api")
    api.include_router(auth.public)
    protected = APIRouter(dependencies=[Depends(auth.require_login)])
    protected.include_router(auth.router)
    protected.include_router(sections.router)
    protected.include_router(sources.router)
    protected.include_router(channels.router)
    api.include_router(protected)
    app.include_router(api)

    if web_dir is not None:
        _serve_web(app, web_dir.resolve())
    return app


def _serve_web(app: FastAPI, web_dir: Path) -> None:
    """Trả file của bản dựng; mọi đường dẫn khác là ứng dụng React, nó tự định tuyến phía trình
    duyệt. Ứng dụng không chứa dữ liệu nào: dữ liệu chỉ đi qua API."""
    index = web_dir / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def web(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Không có đường dẫn này")
        file = (web_dir / path).resolve()
        if path and file.is_file() and file.is_relative_to(web_dir):
            return FileResponse(file)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})


def _invalid(request: Request, error: Exception) -> JSONResponse:
    """Dữ liệu gửi lên chưa hợp lệ: một lời nhắn tiếng Việt cho mỗi trường."""
    if isinstance(error, Invalid):
        return JSONResponse({"detail": "Dữ liệu chưa hợp lệ", "fields": error.fields}, 422)
    assert isinstance(error, RequestValidationError)
    fields: dict[str, str] = {}
    for problem in error.errors():
        # Vị trí là ("body", trường, …): lỗi ở một phần tử của danh sách vẫn tính cho trường đó.
        field = str(problem["loc"][1]) if len(problem["loc"]) > 1 else ""
        if problem["type"] == "value_error":
            # Lời nhắn do validator của ta viết, Pydantic thêm "Value error, " ở đầu.
            message = str(problem["msg"]).removeprefix("Value error, ")
        elif problem["type"] == "missing":
            message = "Cần điền"
        else:
            message = "Giá trị không hợp lệ"
        fields.setdefault(field, message)
    return JSONResponse({"detail": "Dữ liệu chưa hợp lệ", "fields": fields}, status_code=422)
