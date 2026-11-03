from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.core.database import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.services.repository import user_repo

# Această linie îi spune Swagger-ului unde se află formularul de login
# pentru butonul verde de "Authorize"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """
    Acesta este 'bodyguard-ul'. Se uită la Token-ul trimis de utilizator,
    îl decriptează, vede a cui este adresa de email și verifică dacă
    acel utilizator chiar există în baza de date.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials / Token invalid or expired",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Încercăm să decriptăm biletul de acces (Token-ul)
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError: # Prinde orice eroare (token modificat, expirat, etc.)
        raise credentials_exception
        
    # Căutăm utilizatorul în baza de date
    user = user_repo.get_by_email(db, email=email)
    if user is None:
        raise credentials_exception
        
    return user