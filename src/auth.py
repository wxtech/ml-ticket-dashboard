"""JWT 鉴权模块"""
import time
import json
import hashlib
import secrets
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import jwt
from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from logging_config import get_logger

log = get_logger("auth")

# ===== 配置 =====

SECRET_KEY = "ticket-analysis-secret-key-change-in-production-2025"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24小时
USERS_FILE = Path("data/users.json")

security = HTTPBearer()


# ===== 数据模型 =====

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"  # admin / user


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    username: str
    role: str


# ===== 用户存储 =====

def _load_users() -> dict:
    """加载用户数据"""
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text(encoding="utf-8"))
    return {}


def _save_users(users: dict):
    """保存用户数据"""
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


def _hash_password(password: str) -> str:
    """密码哈希（SHA256 + salt）"""
    salt = secrets.token_hex(16)
    hashed = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{hashed}"


def _verify_password(plain: str, hashed: str) -> bool:
    """验证密码"""
    salt, expected_hash = hashed.split(":", 1)
    actual_hash = hashlib.sha256(f"{salt}:{plain}".encode()).hexdigest()
    return actual_hash == expected_hash


# ===== 用户管理 =====

def create_user(username: str, password: str, role: str = "user") -> dict:
    """创建用户"""
    users = _load_users()
    if username in users:
        raise HTTPException(status_code=400, detail=f"用户 {username} 已存在")

    users[username] = {
        "username": username,
        "hashed_password": _hash_password(password),
        "role": role,
        "created_at": datetime.now().isoformat(),
    }
    _save_users(users)
    log.info(f"用户创建成功 | {username} | role={role}")
    return {"username": username, "role": role}


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """验证用户凭据"""
    users = _load_users()
    user = users.get(username)
    if not user:
        log.warning(f"用户不存在 | {username}")
        return None
    if not _verify_password(password, user["hashed_password"]):
        log.warning(f"密码错误 | {username}")
        return None
    return user


def create_access_token(username: str, role: str) -> str:
    """生成 JWT Token"""
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
        "iat": datetime.utcnow(),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    log.info(f"Token 生成 | {username} | role={role} | 过期={ACCESS_TOKEN_EXPIRE_MINUTES}min")
    return token


def decode_token(token: str) -> dict:
    """解码并验证 JWT Token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        log.warning("Token 已过期")
        raise HTTPException(status_code=401, detail="Token 已过期")
    except jwt.InvalidTokenError:
        log.warning("Token 无效")
        raise HTTPException(status_code=401, detail="Token 无效")


# ===== FastAPI 依赖 =====

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """获取当前认证用户（FastAPI 依赖注入）"""
    token = credentials.credentials
    payload = decode_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    if not username:
        raise HTTPException(status_code=401, detail="Token 无效")
    return {"username": username, "role": role}


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """要求管理员权限"""
    if user["role"] != "admin":
        log.warning(f"权限不足 | {user['username']} | role={user['role']}")
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


# ===== 初始化默认用户 =====

def init_default_users():
    """初始化默认管理员账户"""
    users = _load_users()
    if "admin" not in users:
        create_user("admin", "admin123", role="admin")
        log.info("已创建默认管理员账户: admin / admin123")
    if "demo" not in users:
        create_user("demo", "demo123", role="user")
        log.info("已创建默认演示账户: demo / demo123")
