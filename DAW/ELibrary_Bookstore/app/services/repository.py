from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from app.models.database_models import Category
from app.schemas.schemas import CategoryBase
from fastapi import HTTPException, status
from app.models.database_models import LoanPurchase
from app.schemas.schemas import TransactionCreate
from datetime import datetime, timedelta

# Importăm clasa de bază a bazei noastre de date
from app.core.database import Base 

# 1. Definim tipurile generice CONSTRÂNSE (Bound)
# Îi spunem editorului că ModelType este obligatoriu un model din baza de date
# și CreateSchemaType este obligatoriu o schemă Pydantic.
ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)

# ==========================================
# 1. INTERFAȚA DE BAZĂ (Abstract Class)
# Bifează cerința de OOP: "Interfețe"
# ==========================================
class IBaseRepository(Generic[ModelType, CreateSchemaType], ABC):
# ... Restul codului rămâne exact la fel cum era! ...
    """
    Interfața de bază care forțează orice repository care o moștenește 
    să implementeze aceste metode obligatorii (Contractul OOP).
    """
    
    @abstractmethod
    def get_by_id(self, db: Session, id: int) -> Optional[ModelType]:
        pass

    @abstractmethod
    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        pass

    @abstractmethod
    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        pass


# ==========================================
# 2. CLASA PĂRINTE (Base Repository)
# Bifează cerința de OOP: "Clase și metode generice"
# ==========================================

class BaseRepository(IBaseRepository[ModelType, CreateSchemaType]):
    """
    O clasă generică ce implementează metodele standard de bază.
    Din ea vor moșteni clasele specifice (Book, User etc.).
    """
    
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get_by_id(self, db: Session, id: int) -> Optional[ModelType]:
        # Folosim metoda modernă db.get() care caută direct după Primary Key (ID)
        # Este mult mai rapidă și elimină complet eroarea Pylance legată de atributul "id"
        return db.get(self.model, id)

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        # Returnează o listă de înregistrări, cu posibilitate de paginare (skip, limit)
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        # Preia datele din Pydantic, le transformă în dicționar și creează obiectul SQLAlchemy
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj


# ==========================================
# 3. CLASELE COPII (Moștenire OOP)
# Bifează cerința de OOP: "Moștenire" și "Minim 3 clase"
# ==========================================

# Importăm modelele și schemele necesare
from app.models.database_models import Book, User
from app.schemas.schemas import BookCreate, UserCreate

class BookRepository(BaseRepository[Book, BookCreate]):
    """
    Clasa specifică pentru manipularea Cărților. 
    Moștenește din BaseRepository și primește toate metodele (get_by_id, get_all, create) automat.
    """
    def __init__(self):
        super().__init__(Book)
    
    # Aici putem adăuga metode specifice DOAR pentru cărți
    def get_by_title(self, db: Session, title: str) -> Optional[Book]:
        return db.query(Book).filter(Book.title == title).first()


class UserRepository(BaseRepository[User, UserCreate]):
    """
    Clasa specifică pentru manipularea Utilizatorilor.
    """
    def __init__(self):
        super().__init__(User)

    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        return db.query(User).filter(User.email == email).first()

    # ==========================================
    # POLIMORFISM OOP: Suprascriem metoda create
    # ==========================================
    def create(self, db: Session, obj_in: UserCreate) -> User:
        # 1. Extragem datele din Pydantic sub formă de dicționar
        obj_in_data = obj_in.model_dump()
        
        # 2. Scoatem cheia 'password' (care conține parola deja criptată din auth.py)
        # și o salvăm într-o cheie nouă numită exact ca în baza de date: 'password_hash'
        password_value = obj_in_data.pop("password")
        obj_in_data["password_hash"] = password_value
        
        # 3. Salvăm în baza de date (acum SQLAlchemy va recunoaște coloana)
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

class CategoryRepository(BaseRepository[Category, CategoryBase]):
    """
    Clasa specifică pentru manipularea Categoriilor.
    """
    def __init__(self):
        super().__init__(Category)

class TransactionRepository(BaseRepository[LoanPurchase, TransactionCreate]):
    
    def __init__(self):
        super().__init__(LoanPurchase)
        
    def buy_book(self, db: Session, user_id: int, book_id: int):
        from app.models.database_models import Book
        book = db.query(Book).filter(Book.id == book_id).first()
        
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartea nu a fost găsită.")
        if book.stock <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cartea nu mai este în stoc pentru cumpărare!")
            
        book.stock -= 1
        
        # Cumpărarea este definitivă, nu are dată de returnare
        new_transaction = LoanPurchase(
            user_id=user_id,
            book_id=book_id,
            type="buy",
            status="completed" # O cumpărare e gata din prima
        )
        
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        return new_transaction

    def borrow_book(self, db: Session, user_id: int, book_id: int, borrow_days: int = 14):
        from app.models.database_models import Book
        book = db.query(Book).filter(Book.id == book_id).first()
        
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartea nu a fost găsită.")
        if book.stock <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Toate exemplarele sunt deja împrumutate!")
            
        book.stock -= 1
        
        # Calculăm data de returnare (astăzi + 14 zile)
        due_date = datetime.now() + timedelta(days=borrow_days)
        
        new_transaction = LoanPurchase(
            user_id=user_id,
            book_id=book_id,
            type="loan",
            status="active", # Este activ până când user-ul o returnează
            due_date=due_date
        )
        
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        return new_transaction


transaction_repo = TransactionRepository()
category_repo = CategoryRepository()
book_repo = BookRepository()
user_repo = UserRepository()