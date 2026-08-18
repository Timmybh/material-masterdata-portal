import argparse
import getpass
import sys

from sqlalchemy import func, select

from .db import SessionLocal
from .models import Role, User, UserAudit
from .passwords import hash_password


def read_password() -> str:
    password = getpass.getpass("Mật khẩu Admin mới: ")
    confirmation = getpass.getpass("Nhập lại mật khẩu: ")
    if password != confirmation:
        raise ValueError("Mật khẩu xác nhận không khớp")
    if len(password) < 8:
        raise ValueError("Mật khẩu phải có ít nhất 8 ký tự")
    return password


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Reset tài khoản Admin an toàn, không đưa mật khẩu vào command line."
    )
    parser.add_argument(
        "--username",
        default="admin",
        help="Tên tài khoản Admin sau khi reset (mặc định: admin)",
    )
    parser.add_argument(
        "--identifier",
        help="Email hoặc tên tài khoản hiện tại; dùng khi hệ thống có nhiều Admin",
    )
    args = parser.parse_args()
    username = args.username.strip().lower()
    if not username:
        print("Tên tài khoản không được để trống.", file=sys.stderr)
        return 1

    try:
        password = read_password()
    except (EOFError, KeyboardInterrupt):
        print("\nĐã hủy.", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    with SessionLocal() as db:
        user = None
        if args.identifier:
            identifier = args.identifier.strip().lower()
            user = db.scalar(
                select(User).where(
                    (func.lower(User.email) == identifier)
                    | (func.lower(User.username) == identifier)
                )
            )
            if not user:
                print("Không tìm thấy tài khoản theo identifier.", file=sys.stderr)
                return 1
        else:
            user = db.scalar(select(User).where(func.lower(User.username) == username))
            if not user:
                admins = db.scalars(
                    select(User).where(User.role == Role.ADMIN.value).order_by(User.created_at)
                ).all()
                if len(admins) == 1:
                    user = admins[0]
                elif not admins:
                    print("Không tìm thấy tài khoản Admin hiện có.", file=sys.stderr)
                    return 1
                else:
                    print(
                        "Có nhiều tài khoản Admin. Chạy lại với --identifier EMAIL_HOẶC_USERNAME.",
                        file=sys.stderr,
                    )
                    return 1

        duplicate = db.scalar(
            select(User).where(func.lower(User.username) == username, User.id != user.id)
        )
        if duplicate:
            print(f"Tên tài khoản {username!r} đã được sử dụng.", file=sys.stderr)
            return 1

        user.username = username
        user.password_hash = hash_password(password)
        user.role = Role.ADMIN.value
        user.is_active = True
        user.token_version += 1
        db.add(
            UserAudit(
                user_id=user.id,
                actor_id=user.id,
                action="ADMIN_CREDENTIAL_RESET_CLI",
            )
        )
        db.commit()
        print(f"Đã reset Admin thành công: {username}")
        print("Tất cả phiên đăng nhập cũ của tài khoản đã bị thu hồi.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
