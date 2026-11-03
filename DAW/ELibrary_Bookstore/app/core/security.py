import jwt
import bcrypt  # Importăm bcrypt direct, nu mai folosim passlib
from datetime import datetime, timedelta, timezone

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