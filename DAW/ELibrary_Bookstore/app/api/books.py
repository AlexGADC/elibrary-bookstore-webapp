from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.api.deps import get_current_user
from app.models.database_models import User
from app.core.database import get_db
from app.schemas.schemas import BookCreate, BookResponse
from app.services.repository import book_repo
from app.services.repository import transaction_repo
from app.schemas.schemas import TransactionCreate, TransactionResponse
from datetime import datetime, timedelta
import stripe
import os
import stripe
from dotenv import load_dotenv

# Încărcăm variabilele din fișierul .env în memorie
load_dotenv()

# Citim cheia direct din mediul de rulare, în loc să o scriem în clar
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

# Dacă cheia nu e găsită, oprim aplicația preventiv ca să nu crape la plată
if not stripe.api_key:
    raise ValueError("STRIPE_SECRET_KEY lipsește din fișierul .env!")

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
            
            return {
                "message": "Plata a fost realizată cu succes! Cartea este acum a ta.", 
                "transaction_id": transaction_id, 
                "status": transaction.status
            }
        else:
            return {"message": f"Plata încă nu a fost finalizată. Status curent: {checkout_session.payment_status}"}
            
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=f"Eroare de la Stripe: {str(e)}")


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

@router.post("/{book_id}/buy", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def buy_book_endpoint(
    book_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cumpără o carte. Generează un link de plată Stripe securizat.
    """
    from app.models.database_models import Book
    
    # 1. Luăm cartea din baza de date ca să îi aflăm prețul și numele
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(status_code=404, detail="Cartea nu a fost găsită.")
        
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
        
        cancel_url="http://localhost:8000/docs",
    )

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
    return transaction_repo.return_book(db=db, user_id=current_user.id, book_id=book_id)