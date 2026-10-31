from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime

# ==========================================
# CATEGORY SCHEMAS
# ==========================================

class CategoryBase(BaseModel):
    name: str
    slug: str

class CategoryResponse(CategoryBase):
    id: int

    # Această setare permite lui Pydantic să citească datele direct din obiectele SQLAlchemy
    model_config = ConfigDict(from_attributes=True)

# ==========================================
# BOOK SCHEMAS
# ==========================================

class BookBase(BaseModel):
    title: str
    author_name: str
    price: float
    stock: Optional[int] = 0
    is_digital: Optional[bool] = False

class BookCreate(BookBase):
    # Când adminul creează o carte, are nevoie și de un ID pentru categorie
    category_id: int

class BookResponse(BookBase):
    # Când returnăm o carte către utilizator, includem și ID-ul și linkurile fișierelor
    id: int
    category_id: Optional[int]
    cover_image_url: Optional[str] = None
    digital_file_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# USER SCHEMAS (Autentificare & Înregistrare)
# ==========================================

class UserCreate(BaseModel):
    # Ce trimite utilizatorul din frontend când se înregistrează
    username: str
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    # Ce îi returnăm noi (FĂRĂ parolă, din motive evidente de securitate)
    id: int
    username: str
    email: EmailStr
    role_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

# ==========================================
# TOKEN SCHEMAS (Pentru Login)
# ==========================================

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None