from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List
from app.core.logger import logger
from app.core.database import get_db
from app.schemas.schemas import CategoryBase, CategoryResponse
from app.services.repository import category_repo
from app.models.database_models import User, Book, Category
from app.api.deps import get_current_user


router = APIRouter(
    prefix="/categories",
    tags=["Categories"]
)

@router.post("/", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    category_in: CategoryBase, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  
):
    """
    Creează o categorie nouă pentru cărți.
    """

    if not current_user.role_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access interzis! Doar administratorii pot crea categorii."
        )

    new_category = category_repo.create(db=db, obj_in=category_in)

    logger.info(f"CATEGORY CREATED: Admin {current_user.email} created a new category named '{new_category.name}'.")

    return new_category

@router.get("/", response_model=List[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    """
    Returnează lista cu toate categoriile.
    """
    logger.info("CATEGORIES RETRIEVED: The list of book categories was accessed.")

    return category_repo.get_all(db=db)

@router.delete("/{category_id}", status_code=status.HTTP_200_OK)
def delete_category(
    category_id: int, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Șterge o categorie din baza de date. 
    Acțiune permisă doar Administratorilor.
    """

    if current_user.role_id != 1:
        logger.warning(f"UNAUTHORIZED DELETE ATTEMPT: User {current_user.email} tried to delete a category.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces interzis! Doar administratorii pot șterge categorii."

        )
    category = db.query(Category).filter(Category.id == category_id).first()
    
    if not category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Categoria nu a fost găsită."
        )
        
    books_in_category = db.query(Book).filter(Book.category_id == category_id).first()
    if books_in_category:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Nu poți șterge categoria '{category.name}' deoarece conține cărți. Șterge sau mută cărțile mai întâi."
        )

    category_name = category.name

    db.delete(category)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Eroare de integritate: Categoria nu poate fi ștearsă (posibil legată de alte înregistrări)."
        )

    logger.info(f"CATEGORY DELETED: Admin {current_user.email} deleted category '{category_name}' (ID: {category_id}).")
    
    return {"message": f"Categoria '{category_name}' a fost ștearsă cu succes!"}