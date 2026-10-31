from sqlalchemy import Column, Integer, String, Boolean, Numeric, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from app.core.database import Base

# ==========================================
# USER & ROLES MODELS
# ==========================================

class Role(Base):
    # Numele tabelului în baza de date
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)

    # Relația către utilizatori (un rol poate avea mai mulți utilizatori)
    users = relationship("User", back_populates="role")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="SET NULL"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relațiile către celelalte entități
    role = relationship("Role", back_populates="users")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    loans_and_purchases = relationship("LoanPurchase", back_populates="user", cascade="all, delete-orphan")
    logs = relationship("AuditLog", back_populates="user")


# ==========================================
# BOOK CATALOG MODELS
# ==========================================

class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, index=True, nullable=False)

    # Relația către cărți (o categorie are mai multe cărți)
    books = relationship("Book", back_populates="category")


class Book(Base):
    __tablename__ = "books"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    author_name = Column(String(150), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id", ondelete="SET NULL"))
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, default=0)
    
    # Căile către fișierele încărcate
    cover_image_url = Column(String(255), nullable=True)  # .jpg / .png
    digital_file_url = Column(String(255), nullable=True) # .pdf (max 12 MB)
    is_digital = Column(Boolean, default=False)

    # Relații
    category = relationship("Category", back_populates="books")
    loans_and_purchases = relationship("LoanPurchase", back_populates="book", cascade="all, delete-orphan")


# ==========================================
# TRANSACTIONS & LOGGING MODELS
# ==========================================

class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    stripe_subscription_id = Column(String(255), unique=True, nullable=False)
    status = Column(String(50), nullable=False)  # ex: active, canceled
    start_date = Column(DateTime(timezone=True), server_default=func.now())
    end_date = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="subscriptions")


class LoanPurchase(Base):
    # Tabelul pentru împrumuturi și achiziții
    __tablename__ = "loans_and_purchases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    book_id = Column(Integer, ForeignKey("books.id", ondelete="CASCADE"))
    type = Column(String(50), nullable=False)    # 'loan' sau 'purchase'
    status = Column(String(50), nullable=False)  # 'active', 'returned', 'completed'
    borrowed_at = Column(DateTime(timezone=True), server_default=func.now())
    due_date = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="loans_and_purchases")
    book = relationship("Book", back_populates="loans_and_purchases")


class AuditLog(Base):
    # Tabelul pentru jurnalizare (cerința Nota 7)
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False) # ex: LOGIN_SUCCESS, BOOK_BORROWED
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="logs")