from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.schemas.schemas import CategoryBase, CategoryResponse
from app.services.repository import category_repo

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(category_in: CategoryBase, db: Session = Depends(get_db)):
    """
    Creează o categorie nouă pentru cărți.
    """
    return category_repo.create(db=db, obj_in=category_in)

@router.get("/", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    """
    Returnează lista cu toate categoriile.
    """
    return category_repo.get_all(db=db)