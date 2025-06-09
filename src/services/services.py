import uuid
import hashlib
from datetime import datetime, timedelta
from src.models.models import User, Order, Payment, SupportTicket, SupportMessage, PaymentStatus, OrderStatus, \
    TicketStatus, FAQ
from config.database import db
import logging
import re

logger = logging.getLogger(__name__)


class UserService:
    @staticmethod
    def get_or_create_user(telegram_id, username=None, first_name=None, last_name=None):
        """Get existing user or create new one"""
        session = db.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == str(telegram_id)).first()

            if not user:
                user = User(
                    telegram_id=str(telegram_id),
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                session.add(user)
                session.commit()
                logger.info(f"Created new user: {telegram_id}")

            return user
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating/getting user: {e}")
            raise
        finally:
            db.close_session(session)

    @staticmethod
    def update_user_profile(telegram_id, **kwargs):
        """Update user profile information"""
        session = db.get_session()
        try:
            user = session.query(User).filter(User.telegram_id == str(telegram_id)).first()
            if user:
                for key, value in kwargs.items():
                    if hasattr(user, key):
                        setattr(user, key, value)
                session.commit()
                return user
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating user profile: {e}")
            raise
        finally:
            db.close_session(session)

    @staticmethod
    def update_user_email(user_id, email):
        """Update user email address"""
        session = db.get_session()
        try:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user.email = email
                session.commit()
                logger.info(f"Updated email for user {user_id}")
                return user
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating user email: {e}")
            raise
        finally:
            db.close_session(session)


class OrderService:
    @staticmethod
    def generate_order_id():
        """Generate unique order ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = str(uuid.uuid4())[:8]
        return f"ORD-{timestamp}-{random_part}"

    @staticmethod
    def create_order(user_id, amount, currency="USD", description=None):
        """Create new order"""
        session = db.get_session()
        try:
            order = Order(
                order_id=OrderService.generate_order_id(),
                user_id=user_id,
                amount=amount,
                currency=currency,
                description=description,
                status=OrderStatus.PENDING_PAYMENT
            )
            session.add(order)
            session.commit()
            logger.info(f"Created order: {order.order_id}")
            return order
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating order: {e}")
            raise
        finally:
            db.close_session(session)

    @staticmethod
    def get_order_by_id(order_id):
        """Get order by order ID"""
        session = db.get_session()
        try:
            return session.query(Order).filter(Order.order_id == order_id).first()
        finally:
            db.close_session(session)

    @staticmethod
    def update_order_status(order_id, status):
        """Update order status"""
        session = db.get_session()
        try:
            order = session.query(Order).filter(Order.order_id == order_id).first()
            if order:
                order.status = status
                session.commit()
                logger.info(f"Updated order {order_id} status to {status}")
                return order
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating order status: {e}")
            raise
        finally:
            db.close_session(session)

    @staticmethod
    def get_user_orders(user_id, limit=10):
        """Get user's order history"""
        session = db.get_session()
        try:
            return session.query(Order).filter(Order.user_id == user_id).order_by(Order.created_at.desc()).limit(
                limit).all()
        finally:
            db.close_session(session)


class PaymentService:
    @staticmethod
    def generate_payment_id():
        """Generate unique payment ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = str(uuid.uuid4())[:8]
        return f"PAY-{timestamp}-{random_part}"

    @staticmethod
    def create_payment(order_id, user_id, amount, currency="USD", payment_method=None):
        """Create new payment record"""
        session = db.get_session()
        try:
            payment = Payment(
                payment_id=PaymentService.generate_payment_id(),
                order_id=order_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                payment_method=payment_method,
                status=PaymentStatus.PENDING
            )
            session.add(payment)
            session.commit()
            logger.info(f"Created payment: {payment.payment_id}")
            return payment
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating payment: {e}")
            raise
        finally:
            db.close_session(session)

    @staticmethod
    def update_payment_status(payment_id, status, gateway_transaction_id=None, gateway_response=None):
        """Update payment status"""
        session = db.get_session()
        try:
            payment = session.query(Payment).filter(Payment.payment_id == payment_id).first()
            if payment:
                payment.status = status
                if gateway_transaction_id:
                    payment.gateway_transaction_id = gateway_transaction_id
                if gateway_response:
                    payment.gateway_response = gateway_response
                session.commit()
                logger.info(f"Updated payment {payment_id} status to {status}")
                return payment
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating payment status: {e}")
            raise
        finally:
            db.close_session(session)


class SupportService:
    @staticmethod
    def generate_ticket_id():
        """Generate unique ticket ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = str(uuid.uuid4())[:6]
        return f"TKT-{timestamp}-{random_part}"

    @staticmethod
    def create_ticket(user_id, subject, description, priority="medium"):
        """Create new support ticket"""
        session = db.get_session()
        try:
            ticket = SupportTicket(
                ticket_id=SupportService.generate_ticket_id(),
                user_id=user_id,
                subject=subject,
                description=description,
                priority=priority,
                status=TicketStatus.OPEN
            )
            session.add(ticket)
            session.commit()
            logger.info(f"Created support ticket: {ticket.ticket_id}")
            return ticket
        except Exception as e:
            session.rollback()
            logger.error(f"Error creating support ticket: {e}")
            raise
        finally:
            db.close_session(session)

    @staticmethod
    def get_ticket_by_id(ticket_id):
        """Get ticket by ticket ID"""
        session = db.get_session()
        try:
            return session.query(SupportTicket).filter(SupportTicket.ticket_id == ticket_id).first()
        finally:
            db.close_session(session)

    @staticmethod
    def update_ticket_status(ticket_id, status):
        """Update ticket status"""
        session = db.get_session()
        try:
            ticket = session.query(SupportTicket).filter(SupportTicket.ticket_id == ticket_id).first()
            if ticket:
                ticket.status = status
                session.commit()
                logger.info(f"Updated ticket {ticket_id} status to {status}")
                return ticket
            return None
        except Exception as e:
            session.rollback()
            logger.error(f"Error updating ticket status: {e}")
            raise
        finally:
            db.close_session(session)


class FAQService:
    """Service for managing FAQ system"""

    @staticmethod
    def search_faqs(query, limit=5):
        """Search FAQs by keywords and question content"""
        try:
            session = db.get_session()
            query_words = query.lower().split()

            # Search in questions, answers, and keywords
            faqs = session.query(FAQ).filter(
                FAQ.is_active == True
            ).all()

            # Score each FAQ based on keyword matches
            scored_faqs = []
            for faq in faqs:
                score = 0
                text_to_search = f"{faq.question} {faq.answer} {faq.keywords or ''}".lower()

                for word in query_words:
                    if word in text_to_search:
                        score += text_to_search.count(word)

                if score > 0:
                    scored_faqs.append((faq, score))

            # Sort by score and priority
            scored_faqs.sort(key=lambda x: (x[1], x[0].priority), reverse=True)

            return [faq for faq, score in scored_faqs[:limit]]

        except Exception as e:
            logger.error(f"FAQ search error: {e}")
            return []
        finally:
            db.close_session(session)

    @staticmethod
    def get_faqs_by_category(category, limit=10):
        """Get FAQs by category"""
        try:
            session = db.get_session()
            return session.query(FAQ).filter(
                FAQ.category == category,
                FAQ.is_active == True
            ).order_by(FAQ.priority.desc()).limit(limit).all()
        except Exception as e:
            logger.error(f"FAQ category retrieval error: {e}")
            return []
        finally:
            db.close_session(session)

    @staticmethod
    def get_all_categories():
        """Get all FAQ categories"""
        try:
            session = db.get_session()
            categories = session.query(FAQ.category).filter(
                FAQ.is_active == True,
                FAQ.category.isnot(None)
            ).distinct().all()
            return [cat[0] for cat in categories]
        except Exception as e:
            logger.error(f"FAQ categories retrieval error: {e}")
            return []
        finally:
            db.close_session(session)

    @staticmethod
    def add_faq(question, answer, keywords=None, category=None, priority=0):
        """Add new FAQ"""
        try:
            session = db.get_session()
            faq = FAQ(
                question=question,
                answer=answer,
                keywords=keywords,
                category=category,
                priority=priority
            )
            session.add(faq)
            session.commit()
            logger.info(f"FAQ added: {question[:50]}...")
            return faq
        except Exception as e:
            session.rollback()
            logger.error(f"FAQ creation error: {e}")
            return None
        finally:
            db.close_session(session)

    @staticmethod
    def initialize_default_faqs():
        """Initialize default FAQ entries"""
        default_faqs = [
            {
                "question": "How do I make a payment?",
                "answer": "You can make payments using PayPal, Stripe (credit/debit cards), Mobile Money, or Cryptocurrency. Use the /pay command to start a payment.",
                "keywords": "payment, pay, how to pay, make payment",
                "category": "payment",
                "priority": 10
            },
            {
                "question": "What payment methods do you accept?",
                "answer": "We accept PayPal, Credit/Debit Cards (via Stripe), Mobile Money (M-Pesa, MTN), and Cryptocurrencies (Bitcoin, Ethereum, USDT).",
                "keywords": "payment methods, paypal, stripe, mobile money, crypto, bitcoin",
                "category": "payment",
                "priority": 9
            },
            {
                "question": "How can I track my order?",
                "answer": "Use the /track command followed by your order ID to get real-time status updates. You'll also receive automatic notifications when your order status changes.",
                "keywords": "track order, order status, order tracking",
                "category": "orders",
                "priority": 8
            },
            {
                "question": "How do I get a refund?",
                "answer": "Contact our support team using /support and provide your payment ID. Refunds are processed within 3-5 business days depending on your payment method.",
                "keywords": "refund, refunds, money back, cancel payment",
                "category": "payment",
                "priority": 7
            },
            {
                "question": "Is my payment secure?",
                "answer": "Yes! We use industry-standard encryption and secure payment gateways. We never store your payment details on our servers.",
                "keywords": "secure, security, safe, payment security, encryption",
                "category": "security",
                "priority": 6
            },
            {
                "question": "How long does payment processing take?",
                "answer": "PayPal and Card payments are instant. Mobile Money takes 1-5 minutes. Crypto payments take 10-30 minutes for confirmation.",
                "keywords": "payment time, processing time, how long, instant",
                "category": "payment",
                "priority": 5
            },
            {
                "question": "Can I cancel my order?",
                "answer": "Yes, you can cancel your order before it's shipped. Use /support to request cancellation or contact customer service.",
                "keywords": "cancel order, cancel, cancellation",
                "category": "orders",
                "priority": 4
            },
            {
                "question": "Do you offer customer support?",
                "answer": "Yes! Use the /support command to create a support ticket. Our team will respond within 24 hours.",
                "keywords": "support, customer support, help, assistance",
                "category": "support",
                "priority": 3
            }
        ]

        try:
            session = db.get_session()
            # Check if FAQs already exist
            existing_count = session.query(FAQ).count()
            if existing_count > 0:
                logger.info("FAQs already initialized")
                return

            # Add default FAQs
            for faq_data in default_faqs:
                faq = FAQ(**faq_data)
                session.add(faq)

            session.commit()
            logger.info(f"Initialized {len(default_faqs)} default FAQs")

        except Exception as e:
            session.rollback()
            logger.error(f"FAQ initialization error: {e}")
        finally:
            db.close_session(session)
