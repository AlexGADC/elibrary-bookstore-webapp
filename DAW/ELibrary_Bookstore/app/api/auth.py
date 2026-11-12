from datetime import timedelta
import httpx   
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.logger import logger
from app.core.database import get_db
from app.schemas.schemas import UserCreate, UserResponse, Token
from app.services.repository import user_repo
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
def register_user(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    Înregistrează un utilizator nou.
    Verifică dacă email-ul există deja și criptează parola înainte de salvare.
    """

    existing_user = user_repo.get_by_email(db=db, email=user_in.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered."
        )
    
    hashed_password = get_password_hash(user_in.password)
    
    user_in.password = hashed_password
    
    new_user = user_repo.create(db=db, obj_in=user_in)

    logger.info(f"USER REGISTERED: New account created for {new_user.email} (Role ID: {new_user.role_id}).") 

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
    Verifică automat dacă cererea vine din Swagger sau din Frontend.
    """
    
    referer = request.headers.get("referer", "")
    is_swagger = "/docs" in referer or "/redoc" in referer

    if not is_swagger:
        if not captcha:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Câmpul CAPTCHA este obligatoriu!"
            )
            
        RECAPTCHA_SECRET_KEY = "6LeIxAcTAAAAAGG-vFI1TnRWxMZNFuojJ4WifJWe" 
        async with httpx.AsyncClient() as client:
            google_response = await client.post(
                "https://www.google.com/recaptcha/api/siteverify",
                data={
                    "secret": RECAPTCHA_SECRET_KEY,
                    "response": captcha
                }
            )
            result = google_response.json()
            
            if not result.get("success"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Validare CAPTCHA eșuată. Te rugăm să încerci din nou."
                )

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