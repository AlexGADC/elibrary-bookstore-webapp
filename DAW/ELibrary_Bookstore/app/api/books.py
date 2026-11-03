from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_current_user
from app.models.database_models import User

# Importăm ce am construit până acum
from app.core.database import get_db
from app.schemas.schemas import BookCreate, BookResponse
from app.services.repository import book_repo

# Creăm un router special doar pentru secțiunea de cărți
router = APIRouter(
    prefix="/books",
    tags=["Books Catalog"]
)

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_new_book(
    book_in: BookCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # <--- MAGIA: Aici am pus lacătul!
):
    """
    Creează o carte nouă (DOAR pentru utilizatorii logați).
    """
    existing_book = book_repo.get_by_title(db=db, title=book_in.title)
    if existing_book:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="A book with this title already exists."
        )
    
    new_book = book_repo.create(db=db, obj_in=book_in)
    return new_book


@router.get("/", response_model=List[BookResponse])
def get_all_books(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Returnează lista cu toate cărțile din catalog.
    """
    books = book_repo.get_all(db=db, skip=skip, limit=limit)
    return books


@router.get("/{book_id}", response_model=BookResponse)
def get_single_book(book_id: int, db: Session = Depends(get_db)):
    """
    Returnează detaliile unei singure cărți pe baza ID-ului.
    """
    book = book_repo.get_by_id(db=db, id=book_id)
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Book not found."
        )
    return book