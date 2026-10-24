"""API trang quản lí: thiết lập, theo dõi, cải tiến. Mọi đường dẫn dưới /api, trừ đăng nhập, cần
một phiên đăng nhập của tài khoản duy nhất."""

from siftly.admin.app import create_app

__all__ = ["create_app"]
