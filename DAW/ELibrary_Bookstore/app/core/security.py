import jwt
import bcrypt  # Importăm bcrypt direct, nu mai folosim passlib
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.models.database_models import User, Role

# ==========================================
# CONFIGURĂRI JWT (JSON Web Token)
# ==========================================
SECRET_KEY = "my-super-secret-jwt-key-for-elibrary" 
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# ==========================================
# FUNCȚII DE SECURITATE (Criptare nativă bcrypt)
# ==========================================

def get_password_hash(password: str) -> str:
    """Transformă parola din text clar într-un hash ireversibil."""
    # Trebuie să convertim string-ul în bytes înainte de hash
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Returnăm un string curat pe care să-l salvăm în PostgreSQL
    return hashed_password.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifică dacă parola introdusă se potrivește cu hash-ul din baza de date."""
    password_byte_enc = plain_password.encode('utf-8')
    hashed_password_byte_enc = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Creează token-ul JWT (biletul de acces) pentru utilizator."""
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# ==========================================
# GARDIENII (DEPENDENCIES PENTRU RUTE)
# ==========================================

# Asta îi spune lui FastAPI unde e ruta de login (pentru a genera butonul de Authorize în Swagger)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Bodyguard-ul de bază:
    Ia Token-ul, îl decriptează, vede a cui e adresa de email și aduce User-ul din DB.
    Orice utilizator logat trece de acest gardian.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token invalid sau expirat. Te rugăm să te loghezi din nou.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decriptăm token-ul cu cheia noastră secretă
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except Exception:
        # Prindem orice eroare (ex: token expirat)
        raise credentials_exception
        
    # Căutăm utilizatorul în baza de date
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception
        
    return user


def get_current_admin_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Gardianul de nivel 2 (Doar pentru Admini):
    Trece mai întâi prin bodyguard-ul de bază, apoi verifică dacă are rolul 'admin'.
    """
    if not current_user.role_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nu ai suficiente privilegii pentru această acțiune."
        )
        
    # Căutăm rolul în baza de date
    user_role = db.query(Role).filter(Role.id == current_user.role_id).first()
    
    if not user_role or user_role.name.lower() != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Atenție! Această acțiune este rezervată exclusiv administratorilor."
        )
        
    return current_user