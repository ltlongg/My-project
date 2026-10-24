"""Đăng nhập bằng tài khoản duy nhất. Phiên đăng nhập là một mã ngẫu nhiên trong cookie; cơ sở dữ
liệu chỉ giữ dạng băm của nó, nên đăng xuất là xoá dòng ấy."""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import timedelta

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete, select

from siftly.admin.deps import Clock, Db
from siftly.models import AdminSession

COOKIE = "siftly_session"
SESSION_LIFETIME = timedelta(days=30)


@dataclass(frozen=True)
class Account:
    """Tài khoản duy nhất của trang quản lí, lấy từ cấu hình môi trường."""

    username: str
    password: str


class Credentials(BaseModel):
    username: str
    password: str


class Me(BaseModel):
    username: str


# Những đường dẫn duy nhất gọi được khi chưa đăng nhập.
public = APIRouter()
router = APIRouter()


@public.post("/login", status_code=204)
def login(
    credentials: Credentials, request: Request, response: Response, db: Db, clock: Clock
) -> None:
    account: Account = request.app.state.account
    # So cả hai, mỗi thứ một lần trong thời gian không đổi, để không lộ phần nào sai.
    username_ok = hmac.compare_digest(credentials.username.encode(), account.username.encode())
    password_ok = hmac.compare_digest(credentials.password.encode(), account.password.encode())
    if not (username_ok and password_ok):
        raise HTTPException(401, "Sai tên đăng nhập hoặc mật khẩu")
    now = clock()
    token = secrets.token_urlsafe(32)
    db.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
    db.add(AdminSession(token_hash=_hash(token), created_at=now, expires_at=now + SESSION_LIFETIME))
    db.commit()
    response.set_cookie(
        COOKIE,
        token,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        # Trình duyệt không gửi cookie kèm lời gọi từ trang khác, nên không cần mã chống CSRF.
        samesite="strict",
        # Sau proxy HTTPS, uvicorn lấy scheme từ X-Forwarded-Proto.
        secure=request.url.scheme == "https",
    )


@public.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: Db) -> None:
    token = request.cookies.get(COOKIE)
    if token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == _hash(token)))
        db.commit()
    response.delete_cookie(COOKIE, httponly=True, samesite="strict")


@router.get("/session")
def current_session(request: Request) -> Me:
    """Đang đăng nhập với tài khoản nào; ứng dụng React gọi khi mở để biết có cần đăng nhập."""
    account: Account = request.app.state.account
    return Me(username=account.username)


def require_login(request: Request, db: Db, clock: Clock) -> None:
    """Chặn mọi lời gọi không kèm một phiên đăng nhập còn hạn."""
    token = request.cookies.get(COOKIE)
    found = token is not None and db.scalar(
        select(AdminSession.token_hash).where(
            AdminSession.token_hash == _hash(token), AdminSession.expires_at > clock()
        )
    )
    if not found:
        raise HTTPException(401, "Chưa đăng nhập")


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
