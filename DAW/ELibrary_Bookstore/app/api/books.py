from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List   
from app.api.deps import get_current_user
from app.models.database_models import User, Book
from app.core.database import get_db
from app.schemas.schemas import BookCreate, BookResponse, TransactionResponse, BookUpdate
from app.services.repository import book_repo, transaction_repo
import stripe
import os
import stripe
from dotenv import load_dotenv
import shutil
from app.core.security import get_current_admin_user
from app.core.logger import logger

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

if not stripe.api_key:
    raise ValueError("STRIPE_SECRET_KEY lipsește din fișierul .env!")

FILES_DIR = "uploads/files"
os.makedirs(FILES_DIR, exist_ok=True)

MAX_FILE_SIZE_MB = 12
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

router = APIRouter(
    prefix="/books",
    tags=["Books Catalog"]
)

@router.get("/payment-success")
def payment_success_endpoint(
    session_id: str, 
    transaction_id: int, 
    db: Session = Depends(get_db)
):
    """
    Ruta unde este redirecționat utilizatorul după ce plătește pe Stripe.
    Aici verificăm la Stripe dacă plata a fost reală și actualizăm baza de date.
    """
    
    try:
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        if checkout_session.payment_status == "paid":
            transaction = transaction_repo.complete_transaction(db=db, transaction_id=transaction_id)
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Tranzacția nu a fost găsită.")

            user = db.query(User).filter(User.id == transaction.user_id).first()
            user_email = user.email if user else f"ID necunoscut ({transaction.user_id})"
            
            amount_paid = (checkout_session.amount_total / 100.0) if checkout_session.amount_total else 0

            logger.info(f"PAYMENT SUCCESS: Payment confirmed for user {user_email} (Amount: {amount_paid} RON, Transaction ID: {transaction_id}).")
            
            return {
                "message": "Plata a fost realizată cu succes! Cartea este acum a ta.", 
                "transaction_id": transaction_id, 
                "status": transaction.status
            }
        else:
            return {"message": f"Plata încă nu a fost finalizată. Status curent: {checkout_session.payment_status}"}
            
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Eroare de la Stripe: {str(e)}")


@router.post("/{book_id}/upload-cover")
def upload_book_cover(
    book_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user) 
):
    """
    Ruta pentru a încărca o copertă (imagine) pentru o carte specifică.
    Permis doar administratorilor. Dimensiune maximă: 12MB.
    """

    if not current_user.role_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces interzis! Doar administratorii pot încărca coperți."
        )

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartea nu a fost găsită.")
        
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fișierul trebuie să fie o imagine (.jpg, .png, etc.)")
    
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fișierului îi lipsește numele.")
    
    if file.size and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fișierul este prea mare! Limita este de {MAX_FILE_SIZE_MB} MB."
        )
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    file_name = f"cover_{book_id}{file_extension}"
    file_path = f"uploads/covers/{file_name}"
    
    os.makedirs("uploads/covers", exist_ok=True)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    book.cover_image_url = f"/{file_path}"
    db.commit()

    logger.info(f"COVER UPLOADED: Admin {current_user.email} uploaded a new cover image for book ID: {book_id}.")
    
    return {
        "message": "Coperta a fost încărcată cu succes!", 
        "cover_url": book.cover_image_url
    }

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_new_book(
    book_in: BookCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  
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

    logger.info(f"BOOK CREATED: Admin {current_user.email} created a new book titled '{new_book.title}'.")
    return new_book

@router.patch("/{book_id}")
def update_book(
    book_id: int, 
    book_update: BookUpdate, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Actualizează detaliile unei cărți existente.
    """

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Cartea nu a fost găsită.")
    
    update_data = book_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(book, key, value) 
        
    db.commit()
    db.refresh(book)

    logger.info(f"BOOK UPDATED: Admin {current_admin.email} updated the details for book ID: {book_id}.")
    
    return {"message": "Cartea a fost actualizată cu succes!", "book": book}

@router.delete("/{book_id}", status_code=status.HTTP_200_OK)
def delete_book(
    book_id: int, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Șterge o carte din baza de date. 
    Acțiune permisă doar Administratorilor.
    """
    # 1. Căutăm cartea
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Cartea nu a fost găsită."
        )
    
    db.delete(book)
    
    db.commit()

    logger.info(f"BOOK DELETED: Admin {current_admin.email} permanently deleted book '{book.title}' (ID: {book_id}).")
    
    return {"message": f"Cartea '{book.title}' a fost ștearsă cu succes!"}

@router.post("/{book_id}/upload-file")
def upload_digital_file(
    book_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Încarcă fișierul digital (ex: PDF) pentru o carte hibridă sau e-book.
    Permis doar administratorilor.
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Fișierul încărcat nu are un nume valid."
        )
    
    allowed_extensions = [".pdf", ".epub"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sunt permise doar fișiere .pdf sau .epub!"
        )

    book = db.query(Book).filter(Book.id == book_id).first()

    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Cartea nu a fost găsită."
        )

    file_path = f"{FILES_DIR}/book_{book_id}{file_ext}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    book.digital_file_url = f"/{file_path}"
    
    book.is_digital = True
    
    db.commit()

    logger.info(f"FILE UPLOADED: Admin {current_admin.email} uploaded a digital file ({file_ext}) for book ID: {book_id}.")
    
    return {
        "message": "Fișierul a fost încărcat cu succes!", 
        "file_url": book.digital_file_url
    }

@router.get("/", response_model=List[BookResponse]) 
def get_books(
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    category_id: Optional[int] = None,
    is_physical: Optional[bool] = None,
    is_digital: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """
    Returnează lista de cărți.
    Include filtrare opțională după titlu/autor, categorie și format (fizic/digital).
    """

    query = db.query(Book)
    
    if search:
        query = query.filter(
            or_(
                Book.title.ilike(f"%{search}%"),
                Book.author_name.ilike(f"%{search}%")
            )
        )
        
    if category_id is not None:
        query = query.filter(Book.category_id == category_id)
        
    if is_physical is not None:
        query = query.filter(Book.is_physical == is_physical)
        
    if is_digital is not None:
        query = query.filter(Book.is_digital == is_digital)
        
    books = query.offset(skip).limit(limit).all()

    logger.info(f"BOOKS RETRIEVED: List of books accessed (Search: '{search}', Category: {category_id}, Digital: {is_digital}).")
    
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

    logger.info(f"BOOK ACCESSED: Details for book ID: {book_id} were viewed.")
    
    return book

@router.post("/{book_id}/buy", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def buy_book_endpoint(
    book_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Cumpără o carte. Generează un link de plată Stripe securizat.
    """
    from app.models.database_models import Book
    
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartea nu a fost găsită.")
        
    transaction = transaction_repo.buy_book(db=db, user_id=current_user.id, book_id=book_id)

    price_in_bani = int(book.price * 100)

    checkout_session = stripe.checkout.Session.create(
        line_items=[{
            'price_data': {
                'currency': 'ron',
                'product_data': {
                    'name': book.title,
                    'description': f"Autor: {book.author_name}"
                },
                'unit_amount': price_in_bani,
            },
            'quantity': 1,
        }],
        mode='payment',
        
        success_url=f"http://localhost:8000/books/payment-success?session_id={{CHECKOUT_SESSION_ID}}&transaction_id={transaction.id}",
        
        cancel_url="http://localhost:8000/docs"
    )

    logger.info(f"CHECKOUT INITIATED: User {current_user.email} started the purchase process for book ID: {book_id} (Transaction ID: {transaction.id}).")

    return {
        "id": transaction.id,
        "user_id": transaction.user_id,
        "book_id": transaction.book_id,
        "type": transaction.type,
        "status": transaction.status,
        "borrowed_at": transaction.borrowed_at,
        "due_date": transaction.due_date,
        "payment_url": checkout_session.url  
    }

@router.post("/{book_id}/borrow", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def borrow_book_endpoint(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Împrumută o carte pe o perioadă de 14 zile. 
    Generează automat o dată de returnare (due_date).
    """

    logger.info(f"BOOK BORROWED: User {current_user.email} borrowed book ID: {book_id}.")

    return transaction_repo.borrow_book(db=db, user_id=current_user.id, book_id=book_id)

@router.post("/{book_id}/return", response_model=TransactionResponse, status_code=status.HTTP_200_OK)
def return_book_endpoint(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Returnează o carte împrumutată.
    Statusul tranzacției devine 'returned' și stocul cărții crește cu 1.
    """

    logger.info(f"BOOK RETURNED: User {current_user.email} returned book ID: {book_id}.")

    return transaction_repo.return_book(db=db, user_id=current_user.id, book_id=book_id)