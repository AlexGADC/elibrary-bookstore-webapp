from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional, List   
from app.api.deps import get_current_user
from app.models.database_models import User
from app.core.database import get_db
from app.schemas.schemas import BookCreate, BookResponse, TransactionCreate, TransactionResponse, BookUpdate
from app.services.repository import book_repo, transaction_repo
from datetime import datetime, timedelta
import stripe
import os
import stripe
from dotenv import load_dotenv
import shutil
from app.models.database_models import Book
from app.core.security import get_current_admin_user
from app.core.logger import logger

# Încărcăm variabilele din fișierul .env în memorie
load_dotenv()

# Citim cheia direct din mediul de rulare, în loc să o scriem în clar
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Dacă cheia nu e găsită, oprim aplicația preventiv ca să nu crape la plată
if not stripe.api_key:
    raise ValueError("STRIPE_SECRET_KEY lipsește din fișierul .env!")

FILES_DIR = "uploads/files"
os.makedirs(FILES_DIR, exist_ok=True)

MAX_FILE_SIZE_MB = 12
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Creăm un router special doar pentru secțiunea de cărți
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
        # 1. Îl întrebăm pe Stripe care este statusul oficial al acestei sesiuni
        checkout_session = stripe.checkout.Session.retrieve(session_id)
        
        # 2. Dacă a plătit cu succes
        if checkout_session.payment_status == "paid":
            # Actualizăm bonul în "completed"
            transaction = transaction_repo.complete_transaction(db=db, transaction_id=transaction_id)
            
            if not transaction:
                raise HTTPException(status_code=404, detail="Tranzacția nu a fost găsită.")

            # 3. Găsim user-ul din baza de date folosind ID-ul salvat pe tranzacție
            user = db.query(User).filter(User.id == transaction.user_id).first()
            user_email = user.email if user else f"ID necunoscut ({transaction.user_id})"
            
            # 4. Suma din Stripe vine în cenți/bani, o împărțim la 100 pentru a afla suma în RON
            amount_paid = (checkout_session.amount_total / 100.0) if checkout_session.amount_total else 0

            # 5. Log-ul corect cu variabilele extrase
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
    current_user: User = Depends(get_current_user)  # 1. Adăugăm gardianul
):
    """
    Ruta pentru a încărca o copertă (imagine) pentru o carte specifică.
    Permis doar administratorilor. Dimensiune maximă: 12MB.
    """
    # 2. Verificăm drepturile de administrator
    if not current_user.role_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces interzis! Doar administratorii pot încărca coperți."
        )

    # 3. Căutăm cartea în baza de date
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartea nu a fost găsită.")
        
    # 4. Validăm că e o imagine
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fișierul trebuie să fie o imagine (.jpg, .png, etc.)")
    
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fișierului îi lipsește numele.")
    
    # 5. VERIFICARE DIMENSIUNE (Barem 9.04 - max 12 MB)
    # UploadFile în FastAPI expune .size, pe care îl putem folosi direct
    if file.size and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Fișierul este prea mare! Limita este de {MAX_FILE_SIZE_MB} MB."
        )
    
    # 6. Extragem extensia în siguranță (Pylance-friendly) și pregătim calea
    file_extension = os.path.splitext(file.filename)[1].lower()
    file_name = f"cover_{book_id}{file_extension}"
    file_path = f"uploads/covers/{file_name}"
    
    # Asigură-te că folderul există
    os.makedirs("uploads/covers", exist_ok=True)
    
    # 7. Salvăm fizic fișierul pe disk-ul serverului
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # 8. Salvăm link-ul copertii în baza de date
    book.cover_image_url = f"/{file_path}"
    db.commit()

    # 9. Jurnalizarea acțiunii cu email-ul corect al utilizatorului care face acțiunea
    logger.info(f"COVER UPLOADED: Admin {current_user.email} uploaded a new cover image for book ID: {book_id}.")
    
    return {
        "message": "Coperta a fost încărcată cu succes!", 
        "cover_url": book.cover_image_url
    }

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
    # 1. Căutăm cartea în baza de date
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Cartea nu a fost găsită.")
    
    # 2. Extragem DOAR câmpurile care au fost trimise efectiv (ignorăm ce e None)
    # exclude_unset=True este magia Pydantic care ne dă doar ce a tastat userul
    update_data = book_update.dict(exclude_unset=True)
    
    # 3. Aplicăm modificările pe obiectul book
    for key, value in update_data.items():
        setattr(book, key, value) # Schimbă valoarea curentă cu cea nouă
        
    # 4. Salvăm modificările
    db.commit()
    db.refresh(book) # Ne asigurăm că avem ultimele date

    logger.info(f"BOOK UPDATED: Admin {current_admin.email} updated the details for book ID: {book_id}.")
    
    return {"message": "Cartea a fost actualizată cu succes!", "book": book}

@router.delete("/{book_id}", status_code=status.HTTP_200_OK)
def delete_book(
    book_id: int, 
    db: Session = Depends(get_db),
    # Uite gardianul nostru de Admin stând de pază:
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
    
    # 2. O ștergem din baza de date
    db.delete(book)
    
    # 3. Salvăm modificarea (fără commit, nu se șterge de pe disc)
    db.commit()

    # Înregistrăm acțiunea de ștergere
    logger.info(f"BOOK DELETED: Admin {current_admin.email} permanently deleted book '{book.title}' (ID: {book_id}).")
    
    return {"message": f"Cartea '{book.title}' a fost ștearsă cu succes!"}

@router.post("/{book_id}/upload-file")
def upload_digital_file(
    book_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    # Păzim și acest endpoint cu gardianul nostru:
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
    
    # 1. Verificăm extensia (acceptăm doar PDF sau EPUB)
    allowed_extensions = [".pdf", ".epub"]
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sunt permise doar fișiere .pdf sau .epub!"
        )

    # 2. Căutăm cartea în baza de date
    book = db.query(Book).filter(Book.id == book_id).first()

    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Cartea nu a fost găsită."
        )

    # 3. Generăm o cale unică și salvăm fișierul pe disc
    # Ex: uploads/files/book_3.pdf
    file_path = f"{FILES_DIR}/book_{book_id}{file_ext}"
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 4. Actualizăm URL-ul în baza de date
    # Când vom servi fișierele, URL-ul va fi ceva de genul "/uploads/files/book_3.pdf"
    book.digital_file_url = f"/{file_path}"
    
    # 5. Marcăm automat cartea ca fiind și digitală
    book.is_digital = True
    
    db.commit()

    logger.info(f"FILE UPLOADED: Admin {current_admin.email} uploaded a digital file ({file_ext}) for book ID: {book_id}.")
    
    return {
        "message": "Fișierul a fost încărcat cu succes!", 
        "file_url": book.digital_file_url
    }

@router.get("/", response_model=List[BookResponse]) # Asigură-te că folosești numele schemei tale (ex: BookResponse)
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
    # 1. Începem cu o interogare de bază (care ar aduce tot)
    query = db.query(Book)
    
    # 2. Dacă utilizatorul a scris ceva în bara de căutare
    if search:
        # Folosim ilike() pentru căutare case-insensitive (nu contează literele mari/mici)
        # Căutăm fie în titlu, fie în numele autorului
        query = query.filter(
            or_(
                Book.title.ilike(f"%{search}%"),
                Book.author_name.ilike(f"%{search}%")
            )
        )
        
    # 3. Dacă utilizatorul a selectat o categorie
    if category_id is not None:
        query = query.filter(Book.category_id == category_id)
        
    # 4. Dacă vrea doar cărți fizice sau doar digitale
    if is_physical is not None:
        query = query.filter(Book.is_physical == is_physical)
        
    if is_digital is not None:
        query = query.filter(Book.is_digital == is_digital)
        
    # 5. La final, aplicăm paginarea și executăm interogarea (.all())
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
    
    # 1. Luăm cartea din baza de date ca să îi aflăm prețul și numele
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cartea nu a fost găsită.")
        
    # 2. Creăm bonul în baza de date (status: 'pending')
    transaction = transaction_repo.buy_book(db=db, user_id=current_user.id, book_id=book_id)

    # 3. Stripe lucrează doar cu subdiviziuni (cenți / bani). 15 RON = 1500 bani.
    price_in_bani = int(book.price * 100)

    # 4. Creăm Sesiunea de Checkout pe serverele Stripe
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
        
        # AICI E MODIFICAREA MAGICA: 
        # Îi zicem lui Stripe să pună ID-ul sesiunii lui și ID-ul tranzacției noastre în noul link
        success_url=f"http://localhost:8000/books/payment-success?session_id={{CHECKOUT_SESSION_ID}}&transaction_id={transaction.id}",
        
        cancel_url="http://localhost:8000/docs"
    )

    # LOG CORECTAT ȘI MUTAT AICI:
    logger.info(f"CHECKOUT INITIATED: User {current_user.email} started the purchase process for book ID: {book_id} (Transaction ID: {transaction.id}).")

    # 5. Returnăm bonul la care atașăm magicul link de plată
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