import os, time
import bcrypt, jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me")
TOKEN_MINUTES = int(os.getenv("TOKEN_MINUTES", "60"))
oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    payload = {"sub": user.username, "role": user.role, "exp": int(time.time()) + TOKEN_MINUTES * 60}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"])


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        data = decode_token(token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid or expired token")
    user = db.query(User).filter(User.username == data["sub"]).first()
    if not user:
        raise HTTPException(401, "Unknown user")
    return user


def require_role(*roles: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Your role cannot perform this action")
        return user
    return dep
