import stripe
import os
import stripe
import io
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from typing import Optional, List
from app.api.deps import get_current_user
from app.models.database_models import User, Book, Role, LoanPurchase
from app.core.database import get_db
from app.schemas.schemas import BookCreate, BookResponse, TransactionResponse, BookUpdate
from app.services.repository import book_repo, transaction_repo
from PIL import Image
from dotenv import load_dotenv
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


def get_site_url(request: Request) -> str:
    """
    The public address of the site, used for the links Stripe sends the buyer back to.
    If APP_BASE_URL is set in .env it is used as it is (recommended when the app is hosted).
    Otherwise the address is taken from the request itself, so it works on localhost,
    through a tunnel or behind a proxy without any configuration.
    """
    configured_url = os.getenv("APP_BASE_URL")
    if configured_url:
        return configured_url.rstrip("/")

    scheme = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    return f"{scheme}://{host}"


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
                raise HTTPException(status_code=404, detail="Transaction not found.")

            user = db.query(User).filter(User.id == transaction.user_id).first()
            user_email = user.email if user else f"ID necunoscut ({transaction.user_id})"
            
            amount_paid = (checkout_session.amount_total / 100.0) if checkout_session.amount_total else 0

            logger.info(f"PAYMENT SUCCESS: Payment confirmed for user {user_email} (Amount: {amount_paid} RON, Transaction ID: {transaction_id}).")
            
            return {
                "message": "Payment successful! The book is now yours.", 
                "transaction_id": transaction_id, 
                "status": transaction.status
            }
        else:
            return {"message": f"The payment has not been completed yet. Current status: {checkout_session.payment_status}"}
            
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


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
    Include protecție anti-steganografie (eliminare metadate EXIF).
    """

    if not current_user.role_id == 1:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied! Only administrators can upload covers."
        )

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found.")
        
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file must be an image (.jpg, .png, etc.)")
    
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="The file has no name.")
    
    if file.size and file.size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The file is too large! The limit is {MAX_FILE_SIZE_MB} MB."
        )
    
    file_extension = os.path.splitext(file.filename)[1].lower()
    file_name = f"cover_{book_id}{file_extension}"
    file_path = f"uploads/covers/{file_name}"
    
    os.makedirs("uploads/covers", exist_ok=True)
    
    try:
        file_bytes = file.file.read()
        
        img = Image.open(io.BytesIO(file_bytes))
        
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
        elif img.mode != "RGB":
            img = img.convert("RGB")
            
        clean_image = img.copy()
        
        clean_image.save(file_path)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The image is corrupted or contains hidden malicious content (steganography attempt blocked)."
        )
        
    book.cover_image_url = f"/{file_path}"
    db.commit()

    logger.info(f"COVER UPLOADED & SECURED: Admin {current_user.email} uploaded a secure cover image for book ID: {book_id}.")
    
    return {
        "message": "The cover was uploaded and cleaned of metadata successfully!", 
        "cover_url": book.cover_image_url
    }

@router.post("/", response_model=BookResponse, status_code=status.HTTP_201_CREATED)
def create_new_book(
    book_in: BookCreate, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_user)
):
    """
    Creează o carte nouă. Acțiune permisă doar Administratorilor.
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
        raise HTTPException(status_code=404, detail="Book not found.")
    
    update_data = book_update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        setattr(book, key, value) 
        
    db.commit()
    db.refresh(book)

    logger.info(f"BOOK UPDATED: Admin {current_admin.email} updated the details for book ID: {book_id}.")
    
    return {"message": "The book was updated successfully!", "book": book}

@router.delete("/{book_id}", status_code=status.HTTP_200_OK)
def delete_book(
    book_id: int, 
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Șterge o carte din baza de date și fișierele fizice asociate (copertă, fișier digital). 
    Acțiune permisă doar Administratorilor.
    """

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Book not found."
        )
    
    if book.cover_image_url and os.path.exists(book.cover_image_url):
        try:
            os.remove(book.cover_image_url)
            logger.info(f"FILE DELETED: Cover image '{book.cover_image_url}' removed.")
        except Exception as e:
            logger.warning(f"Could not delete cover image on disk: {e}")

    if book.digital_file_url and os.path.exists(book.digital_file_url):
        try:
            os.remove(book.digital_file_url)
            logger.info(f"FILE DELETED: Digital file '{book.digital_file_url}' removed.")
        except Exception as e:
            logger.warning(f"Could not delete digital file on disk: {e}")
    
    db.delete(book)
    db.commit()

    logger.info(f"BOOK DELETED: Admin {current_admin.email} permanently deleted book '{book.title}' (ID: {book_id}).")
    
    return {"message": f"The book '{book.title}' and its files were deleted successfully!"}


@router.post("/{book_id}/upload-file")
def upload_digital_file(
    book_id: int, 
    file: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Încarcă fișierul digital (ex: PDF) pentru o carte hibridă sau e-book.
    Permis doar administratorilor. Include limită de dimensiune (12 MB).
    """

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file has no valid name."
        )

    allowed_extensions = [".pdf", ".epub"]
    file_ext = os.path.splitext(file.filename)[1].lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only .pdf or .epub files are allowed!"
        )

    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(0)

    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"The file is too large ({file_size / (1024 * 1024):.1f} MB). The maximum allowed size is {MAX_FILE_SIZE_MB} MB."
        )

    book = db.query(Book).filter(Book.id == book_id).first()

    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Book not found."
        )

    file_path = f"{FILES_DIR}/book_{book_id}{file_ext}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    book.digital_file_url = f"/{file_path}"
    book.is_digital = True

    db.commit()

    logger.info(f"FILE UPLOADED: Admin {current_admin.email} uploaded a digital file ({file_ext}) for book ID: {book_id}. Size: {file_size / (1024*1024):.2f} MB.")

    return {
        "message": "The file was uploaded successfully!",
        "file_url": book.digital_file_url
    }

@router.get("/{book_id}/download")
def download_digital_file(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Descarcă fișierul digital (PDF / EPUB) al unei cărți.
    Permis doar administratorilor și utilizatorilor care au cumpărat cartea
    sau au un împrumut activ pentru ea.
    """

    book = db.query(Book).filter(Book.id == book_id).first()
    if not book or not book.digital_file_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This book has no digital file."
        )

    # The files in uploads/files are not public, so this is the only way to get one.
    user_role = db.query(Role).filter(Role.id == current_user.role_id).first()
    is_admin = user_role is not None and user_role.name.lower() == "admin"

    has_bought_or_borrowed = db.query(LoanPurchase).filter(
        LoanPurchase.user_id == current_user.id,
        LoanPurchase.book_id == book_id,
        or_(
            and_(LoanPurchase.type == "buy", LoanPurchase.status == "completed"),
            and_(LoanPurchase.type == "loan", LoanPurchase.status == "active")
        )
    ).first() is not None

    if not is_admin and not has_bought_or_borrowed:
        logger.warning(f"DOWNLOAD DENIED: User {current_user.email} tried to download book ID: {book_id} without owning or borrowing it.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied! You need to buy or borrow this book to download it."
        )

    file_path = book.digital_file_url.lstrip("/")
    if not os.path.isfile(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The digital file was not found on the server."
        )

    logger.info(f"FILE DOWNLOADED: User {current_user.email} downloaded the digital file for book ID: {book_id}.")

    return FileResponse(file_path, filename=os.path.basename(file_path))

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
    request: Request,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Cumpără o carte. Generează un link de plată Stripe securizat.
    """
    from app.models.database_models import Book
    
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found.")
        
    transaction = transaction_repo.buy_book(db=db, user_id=current_user.id, book_id=book_id)

    price_in_bani = int(book.price * 100)
    site_url = get_site_url(request)

    checkout_session = stripe.checkout.Session.create(
        line_items=[{
            'price_data': {
                'currency': 'ron',
                'product_data': {
                    'name': book.title,
                    'description': f"Author: {book.author_name}"
                },
                'unit_amount': price_in_bani,
            },
            'quantity': 1,
        }],
        mode='payment',
        
        success_url=f"{site_url}/books/payment-success?session_id={{CHECKOUT_SESSION_ID}}&transaction_id={transaction.id}",
        
        cancel_url=f"{site_url}/docs"
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