from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    COOKIE,
    create_token,
    current_user,
    dummy_hash,
    password_hash,
    revoke_sessions,
    set_session_cookie,
    throttle,
)
from app.models import LoginSession, User
from app.schemas import Register, UserOut


def same_origin(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site" or (
        origin and urlsplit(origin).netloc != request.url.netloc
    ):
        raise HTTPException(403, "Запрос с другого сайта отклонён")


router = APIRouter(prefix="/api/auth", tags=["Аккаунт"], dependencies=[Depends(same_origin)])


class ProfileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=2, max_length=100)


class PasswordInput(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


@router.post("/register", response_model=UserOut, status_code=201)
def register(data: Register, request: Request, db: Session = Depends(get_db)):
    throttle(db, "register:" + request.client.host, limit=20)
    user = User(
        email=str(data.email).lower(),
        name=data.name,
        password_hash=password_hash.hash(data.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Этот email уже зарегистрирован") from None
    return user


@router.post("/token")
def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    if len(form.password) > 128 or len(form.username) > 254:
        raise HTTPException(401, "Неверный email или пароль")
    throttle(db, "login-ip:" + request.client.host, limit=60)
    throttle(db, "login-account:" + form.username.strip().lower())
    user = db.scalar(select(User).where(User.email == form.username.strip().lower()))
    valid = password_hash.verify(form.password, user.password_hash if user else dummy_hash)
    if not user or not valid:
        raise HTTPException(401, "Неверный email или пароль")
    # Serialize session issuance with password changes: a previously verified
    # password must still be current when the session is committed.
    result = db.execute(
        update(User)
        .where(User.id == user.id, User.password_hash == user.password_hash)
        .values(password_hash=user.password_hash)
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(401, "Пароль изменился. Войдите снова")
    token = create_token(user.id, db)
    set_session_cookie(response, token)
    response.headers["Cache-Control"] = "no-store"
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(current_user)):
    return user


@router.patch("/me", response_model=UserOut)
def profile(data: ProfileInput, user: User = Depends(current_user), db: Session = Depends(get_db)):
    user.name = data.name
    db.commit()
    return user


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    db.execute(delete(LoginSession).where(LoginSession.id == request.state.session_id))
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"detail": "Вы вышли из аккаунта"}


@router.post("/password")
def change_password(
    data: PasswordInput,
    response: Response,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
):
    throttle(db, f"password:{user.id}")
    old_hash = user.password_hash
    if not password_hash.verify(data.current_password, old_hash):
        raise HTTPException(400, "Текущий пароль неверен")
    if data.current_password == data.new_password:
        raise HTTPException(400, "Новый пароль должен отличаться от текущего")
    result = db.execute(
        update(User)
        .where(User.id == user.id, User.password_hash == old_hash)
        .values(password_hash=password_hash.hash(data.new_password))
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Пароль уже изменён. Войдите снова")
    revoke_sessions(db, user.id)
    db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"detail": "Пароль изменён. Войдите снова на всех устройствах"}
