from datetime import timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.logger import logger
from app.core.captcha import verify_captcha, is_docs_request
from app.core.database import get_db
from app.schemas.schemas import UserCreate, UserRegister, UserResponse, Token
from app.services.repository import user_repo, role_repo
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(request: Request, user_in: UserRegister, db: Session = Depends(get_db)):
    """
    Înregistrează un utilizator nou.
    Verifică CAPTCHA-ul, dacă email-ul există deja și criptează parola înainte de salvare.
    """

    is_swagger = is_docs_request(request)

    if not is_swagger:
        await verify_captcha(user_in.captcha)

    existing_user = user_repo.get_by_email(db=db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )

    hashed_password = get_password_hash(user_in.password)

    new_account = UserCreate(username=user_in.username, email=user_in.email, password=hashed_password)

    user_role = role_repo.get_or_create(db=db, name="user")

    new_user = user_repo.create(db=db, obj_in=new_account, role_id=user_role.id)

    logger.info(f"USER REGISTERED: New account created for {new_user.email} (Role ID: {new_user.role_id}, Swagger: {is_swagger}).")

    return new_user


@router.post("/login", response_model=Token)
async def login_for_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    captcha: Optional[str] = Form(None)
):
    """
    Endpoint pentru autentificare.
    Cere CAPTCHA, cu excepția cererilor din Swagger atunci când ALLOW_DOCS_LOGIN este activat.
    """

    is_swagger = is_docs_request(request)

    if not is_swagger:
        await verify_captcha(captcha)

    user = user_repo.get_by_email(db=db, email=form_data.username)

    if not user or not verify_password(form_data.password, str(user.password_hash)):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    logger.info(f"LOGIN SUCCESS: User {user.email} successfully logged in (Swagger: {is_swagger}).")

    return {"access_token": access_token, "token_type": "bearer"}
