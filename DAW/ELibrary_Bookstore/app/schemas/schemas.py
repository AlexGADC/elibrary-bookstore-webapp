from pydantic import BaseModel, EmailStr, ConfigDict, Field
from typing import Optional
from datetime import datetime

class CategoryBase(BaseModel):
    name: str
    slug: str

class CategoryResponse(CategoryBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class BookBase(BaseModel):
    title: str
    author_name: str
    description: Optional[str] = None
    price: float
    stock: Optional[int] = 0
    is_digital: Optional[bool] = False
    is_physical: Optional[bool] = True


class BookCreate(BookBase):
    category_id: int


class BookResponse(BookBase):
    id: int
    category_id: Optional[int]
    cover_image_url: Optional[str] = None
    digital_file_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author_name: Optional[str] = None
    description: Optional[str] = None   
    price: Optional[float] = None
    stock: Optional[int] = None
    is_digital: Optional[bool] = None
    is_physical: Optional[bool] = None
    category_id: Optional[int] = None


class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str


class UserRegister(UserCreate):
    """What the register form sends: the account data plus the CAPTCHA answer."""
    username: str = Field(min_length=2, max_length=100)
    password: str = Field(min_length=8, max_length=64)
    captcha: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[str] = None


class TransactionCreate(BaseModel):
    """
    Ce trimite utilizatorul când vrea să facă o tranzacție.
    Nu îi cerem user_id pentru că îl luăm automat din token (Bodyguard).
    """
    transaction_type: str = Field(..., description="'borrow' sau 'purchase'")
    

class MyTransactionResponse(BaseModel):
    """One loan or purchase of the logged-in user, together with the book it is about."""
    id: int
    book_id: int
    book_title: str
    book_author: str
    cover_image_url: Optional[str] = None
    has_digital_file: bool
    type: str
    status: str
    borrowed_at: datetime
    due_date: Optional[datetime] = None


class TransactionResponse(BaseModel):
    """Ce returnăm înapoi ca bon/chitanță."""
    id: int
    user_id: int
    book_id: int
    type: str    
    status: str                          
    borrowed_at: datetime                   
    due_date: Optional[datetime] = None  
    payment_url: Optional[str] = None   

    model_config = ConfigDict(from_attributes=True)