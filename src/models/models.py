from sqlalchemy import create_engine, Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime

Base = declarative_base()


class PaymentStatus(enum.Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"


class OrderStatus(enum.Enum):
    PENDING_PAYMENT = "pending_payment"
    PAYMENT_CONFIRMED = "payment_confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class TicketStatus(enum.Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    phone_number = Column(String(20))
    email = Column(String(150))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    orders = relationship("Order", back_populates="user")
    payments = relationship("Payment", back_populates="user")
    support_tickets = relationship("SupportTicket", back_populates="user")


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True)
    order_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='USD')
    description = Column(Text)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PAYMENT)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="orders")
    payments = relationship("Payment", back_populates="order")


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True)
    payment_id = Column(String(100), unique=True, nullable=False)
    order_id = Column(Integer, ForeignKey('orders.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(10), default='USD')
    payment_method = Column(String(50))  # paypal, stripe, crypto, mobile_money
    gateway_transaction_id = Column(String(200))
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    gateway_response = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="payments")
    order = relationship("Order", back_populates="payments")


class SupportTicket(Base):
    __tablename__ = 'support_tickets'

    id = Column(Integer, primary_key=True)
    ticket_id = Column(String(50), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    subject = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(TicketStatus), default=TicketStatus.OPEN)
    priority = Column(String(20), default='medium')  # low, medium, high, urgent
    assigned_agent = Column(String(100))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="support_tickets")
    messages = relationship("SupportMessage", back_populates="ticket")


class SupportMessage(Base):
    __tablename__ = 'support_messages'

    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey('support_tickets.id'), nullable=False)
    sender_type = Column(String(20), nullable=False)  # user, agent, system
    sender_name = Column(String(100))
    message = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    ticket = relationship("SupportTicket", back_populates="messages")


class FAQ(Base):
    """FAQ model for storing frequently asked questions"""
    __tablename__ = 'faqs'

    id = Column(Integer, primary_key=True)
    question = Column(Text, nullable=False)  # The question
    answer = Column(Text, nullable=False)  # The answer
    keywords = Column(Text)  # Comma-separated keywords for search
    category = Column(String(100))  # Category like 'payment', 'orders', 'support'
    priority = Column(Integer, default=0)  # Higher priority FAQs shown first
    is_active = Column(Boolean, default=True)  # Whether FAQ is active
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<FAQ {self.id}: {self.question[:50]}...>"
