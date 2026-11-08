from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.logger import logger
from app.core.database import get_db
from app.schemas.schemas import CategoryBase, CategoryResponse
from app.services.repository import category_repo
from app.models.database_models import User
from app.api.deps import get_current_user

router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryBase, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # 1. Aducem utilizatorul curent
):
    """
    Creează o categorie nouă pentru cărți.
    """
    # 2. Verificăm bool-ul de admin (ajustează numele 'is_admin' dacă la tine în model se numește altfel)
    if not current_user.role_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access interzis! Doar administratorii pot crea categorii."
        )

    # 3. Creăm categoria folosind repository-ul și o salvăm în variabila 'new_category'
    new_category = category_repo.create(db=db, obj_in=category_in)

    # 4. Acum putem loga fără erori, pentru că 'new_category' și 'current_user' există
    logger.info(f"CATEGORY CREATED: Admin {current_user.email} created a new category named '{new_category.name}'.")

    # 5. Returnăm categoria creată
    return new_category

@router.get("/", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    """
    Returnează lista cu toate categoriile.
    """
    logger.info("CATEGORIES RETRIEVED: The list of book categories was accessed.")

    return category_repo.get_all(db=db)