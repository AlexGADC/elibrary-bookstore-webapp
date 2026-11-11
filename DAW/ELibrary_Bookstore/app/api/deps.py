from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt

from app.core.database import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.services.repository import user_repo

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
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise credentials_exception
    except jwt.PyJWTError: 
        raise credentials_exception
        
    user = user_repo.get_by_email(db, email=email)
    if user is None:
        raise credentials_exception
        
    return user