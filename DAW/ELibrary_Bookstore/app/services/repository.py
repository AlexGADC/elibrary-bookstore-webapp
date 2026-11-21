from abc import ABC, abstractmethod
from typing import TypeVar, Generic, Type, Optional, List
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.models.database_models import Category, LoanPurchase, Role
from app.schemas.schemas import CategoryBase
from fastapi import HTTPException, status
from app.schemas.schemas import TransactionCreate
from datetime import datetime, timedelta

from app.core.database import Base 

ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)

class IBaseRepository(Generic[ModelType, CreateSchemaType], ABC):
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



class BaseRepository(IBaseRepository[ModelType, CreateSchemaType]):
    """
    O clasă generică ce implementează metodele standard de bază.
    Din ea vor moșteni clasele specifice (Book, User etc.).
    """
    
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get_by_id(self, db: Session, id: int) -> Optional[ModelType]:
        return db.get(self.model, id)

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        return db.query(self.model).offset(skip).limit(limit).all()

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        obj_in_data = obj_in.model_dump()
        db_obj = self.model(**obj_in_data)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj



from app.models.database_models import Book, User
from app.schemas.schemas import BookCreate, UserCreate

class BookRepository(BaseRepository[Book, BookCreate]):
    """
    Clasa specifică pentru manipularea Cărților. 
    Moștenește din BaseRepository și primește toate metodele (get_by_id, get_all, create) automat.
    """
    def __init__(self):
        super().__init__(Book)
    
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


    def create(self, db: Session, obj_in: UserCreate, role_id: Optional[int] = None) -> User:
        obj_in_data = obj_in.model_dump()
        
        password_value = obj_in_data.pop("password")
        obj_in_data["password_hash"] = password_value
        obj_in_data["role_id"] = role_id
        
        db_obj = self.model(**obj_in_data)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    

DEFAULT_ROLES = ("admin", "user")


class RoleRepository(BaseRepository[Role, BaseModel]):
    """
    Clasa specifică pentru manipularea Rolurilor.
    """
    def __init__(self):
        super().__init__(Role)

    def get_by_name(self, db: Session, name: str) -> Optional[Role]:
        return db.query(Role).filter(Role.name == name).first()

    def get_or_create(self, db: Session, name: str) -> Role:
        role = self.get_by_name(db, name)
        if role is None:
            role = Role(name=name)
            db.add(role)
            db.commit()
            db.refresh(role)
        return role

    def ensure_default_roles(self, db: Session) -> None:
        """
        Creates the "admin" and "user" roles if they are missing (for example on a new, empty database).
        "admin" comes first so it gets ID 1 there, because some routes check role_id == 1.
        """
        for name in DEFAULT_ROLES:
            self.get_or_create(db, name)


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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found.")
        if book.stock <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This book is out of stock.")
            
        book.stock -= 1
        
        new_transaction = LoanPurchase(
            user_id=user_id,
            book_id=book_id,
            type="buy",
            status="pending"  
        )
        
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        return new_transaction

    def buy_ebook(self, db: Session, user_id: int, book_id: int):
        """
        Starts the purchase of the e-book edition of a book.
        The stock is not touched: it counts printed copies only, and an e-book never runs out.
        """
        from app.models.database_models import Book
        book = db.query(Book).filter(Book.id == book_id).first()

        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found.")
        if not book.digital_file_url:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This book has no e-book edition.")

        already_owned = db.query(LoanPurchase).filter(
            LoanPurchase.user_id == user_id,
            LoanPurchase.book_id == book_id,
            LoanPurchase.type == "buy_ebook",
            LoanPurchase.status == "completed"
        ).first()
        if already_owned:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already own this e-book.")

        new_transaction = LoanPurchase(
            user_id=user_id,
            book_id=book_id,
            type="buy_ebook",
            status="pending"
        )

        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        return new_transaction

    def borrow_book(self, db: Session, user_id: int, book_id: int, borrow_days: int = 14):
        from app.models.database_models import Book
        book = db.query(Book).filter(Book.id == book_id).first()
        
        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found.")
        if book.stock <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="All copies are currently borrowed.")
            
        book.stock -= 1
        
        due_date = datetime.now() + timedelta(days=borrow_days)
        
        new_transaction = LoanPurchase(
            user_id=user_id,
            book_id=book_id,
            type="loan",
            status="active", 
            due_date=due_date
        )
        
        db.add(new_transaction)
        db.commit()
        db.refresh(new_transaction)
        return new_transaction
    

    def return_book(self, db: Session, user_id: int, book_id: int):
        from app.models.database_models import Book
        
        transaction = db.query(self.model).filter(
            self.model.user_id == user_id,
            self.model.book_id == book_id,
            self.model.type == "loan",
            self.model.status == "active"
        ).first()
        
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="You do not have an active loan for this book."
            )
            
        book = db.query(Book).filter(Book.id == book_id).first()
        if book:
            book.stock += 1
            
        transaction.status = "returned"
        
        db.commit()
        db.refresh(transaction)
        
        return transaction

    def complete_transaction(self, db: Session, transaction_id: int):
        """Marchează tranzacția ca fiind plătită (completed)."""
        from app.models.database_models import LoanPurchase
        
        transaction = db.query(LoanPurchase).filter(LoanPurchase.id == transaction_id).first()
        
        if transaction and transaction.status == "pending":
            transaction.status = "completed"
            db.commit()
            db.refresh(transaction)
            
        return transaction


transaction_repo = TransactionRepository()
category_repo = CategoryRepository()
book_repo = BookRepository()
user_repo = UserRepository()
role_repo = RoleRepository()
