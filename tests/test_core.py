import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.services import UserService, OrderService, PaymentService, SupportService
from src.models.models import User, Order, Payment, SupportTicket, OrderStatus, PaymentStatus, TicketStatus
from src.security.security import SecurityValidator, RateLimiter, security_validator
from src.gateways.payment_gateways import PaymentGatewayManager


class TestUserService(unittest.TestCase):
    """Test UserService functionality"""

    @patch('services.db.get_session')
    def test_get_or_create_user_new(self, mock_get_session):
        """Test creating a new user"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_session.query().filter().first.return_value = None

        # Test user creation
        user = UserService.get_or_create_user(
            telegram_id=123456,
            username="testuser",
            first_name="Test",
            last_name="User"
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('services.db.get_session')
    def test_get_or_create_user_existing(self, mock_get_session):
        """Test getting existing user"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        existing_user = Mock()
        mock_session.query().filter().first.return_value = existing_user

        user = UserService.get_or_create_user(telegram_id=123456)

        # Should not create new user
        mock_session.add.assert_not_called()
        self.assertEqual(user, existing_user)


class TestOrderService(unittest.TestCase):
    """Test OrderService functionality"""

    def test_generate_order_id(self):
        """Test order ID generation"""
        order_id = OrderService.generate_order_id()

        self.assertTrue(order_id.startswith('ORD-'))
        self.assertTrue(len(order_id) > 20)  # Should have timestamp and random part

    @patch('services.db.get_session')
    def test_create_order(self, mock_get_session):
        """Test order creation"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        order = OrderService.create_order(
            user_id=1,
            amount=100.0,
            currency="USD",
            description="Test order"
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()

    @patch('services.db.get_session')
    def test_update_order_status(self, mock_get_session):
        """Test order status update"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session
        mock_order = Mock()
        mock_session.query().filter().first.return_value = mock_order

        result = OrderService.update_order_status("ORD-123", OrderStatus.PAYMENT_CONFIRMED)

        self.assertEqual(mock_order.status, OrderStatus.PAYMENT_CONFIRMED)
        mock_session.commit.assert_called_once()


class TestPaymentService(unittest.TestCase):
    """Test PaymentService functionality"""

    def test_generate_payment_id(self):
        """Test payment ID generation"""
        payment_id = PaymentService.generate_payment_id()

        self.assertTrue(payment_id.startswith('PAY-'))
        self.assertTrue(len(payment_id) > 20)

    @patch('services.db.get_session')
    def test_create_payment(self, mock_get_session):
        """Test payment creation"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        payment = PaymentService.create_payment(
            order_id=1,
            user_id=1,
            amount=100.0,
            currency="USD",
            payment_method="stripe"
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


class TestSupportService(unittest.TestCase):
    """Test SupportService functionality"""

    def test_generate_ticket_id(self):
        """Test ticket ID generation"""
        ticket_id = SupportService.generate_ticket_id()

        self.assertTrue(ticket_id.startswith('TKT-'))
        self.assertTrue(len(ticket_id) > 20)

    @patch('services.db.get_session')
    def test_create_ticket(self, mock_get_session):
        """Test support ticket creation"""
        mock_session = Mock()
        mock_get_session.return_value = mock_session

        ticket = SupportService.create_ticket(
            user_id=1,
            subject="Test Issue",
            description="Test description",
            priority="medium"
        )

        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()


class TestSecurityValidator(unittest.TestCase):
    """Test SecurityValidator functionality"""

    def test_validate_payment_amount_valid(self):
        """Test valid payment amount"""
        is_valid, error = SecurityValidator.validate_payment_amount("100.50")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_payment_amount_invalid(self):
        """Test invalid payment amount"""
        # Test negative amount
        is_valid, error = SecurityValidator.validate_payment_amount("-10")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

        # Test too large amount
        is_valid, error = SecurityValidator.validate_payment_amount("50000")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

        # Test invalid format
        is_valid, error = SecurityValidator.validate_payment_amount("abc")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_validate_order_id_valid(self):
        """Test valid order ID"""
        is_valid, error = SecurityValidator.validate_order_id("ORD-20231201-abc123")
        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_order_id_invalid(self):
        """Test invalid order ID"""
        # Test wrong prefix
        is_valid, error = SecurityValidator.validate_order_id("INVALID-123")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

        # Test too short
        is_valid, error = SecurityValidator.validate_order_id("ORD-123")
        self.assertFalse(is_valid)
        self.assertIsNotNone(error)

    def test_sanitize_input(self):
        """Test input sanitization"""
        dangerous_input = "<script>alert('xss')</script>"
        sanitized = SecurityValidator.sanitize_input(dangerous_input)

        self.assertNotIn('<', sanitized)
        self.assertNotIn('>', sanitized)

    def test_generate_secure_token(self):
        """Test secure token generation"""
        token1 = SecurityValidator.generate_secure_token()
        token2 = SecurityValidator.generate_secure_token()

        self.assertNotEqual(token1, token2)
        self.assertTrue(len(token1) > 20)


class TestRateLimiter(unittest.TestCase):
    """Test RateLimiter functionality"""

    def setUp(self):
        """Set up test rate limiter"""
        self.rate_limiter = RateLimiter()

    def test_rate_limit_allows_requests(self):
        """Test that rate limiter allows requests under limit"""
        identifier = "test_user_123"

        # Should allow first request
        self.assertTrue(self.rate_limiter.is_allowed(identifier))

        # Should allow multiple requests under limit
        for _ in range(8):  # Default limit is 10 per minute
            self.assertTrue(self.rate_limiter.is_allowed(identifier))

    def test_rate_limit_blocks_excess_requests(self):
        """Test that rate limiter blocks requests over limit"""
        identifier = "test_user_456"

        # Use up all allowed requests
        for _ in range(10):  # Default limit is 10 per minute
            self.assertTrue(self.rate_limiter.is_allowed(identifier))

        # Next request should be blocked
        self.assertFalse(self.rate_limiter.is_allowed(identifier))

    def test_different_limit_types(self):
        """Test different rate limit types"""
        identifier = "test_user_789"

        # Payment limit is 5 per 5 minutes
        for _ in range(5):
            self.assertTrue(self.rate_limiter.is_allowed(identifier, 'payment'))

        # Sixth request should be blocked
        self.assertFalse(self.rate_limiter.is_allowed(identifier, 'payment'))


class TestPaymentGatewayManager(unittest.TestCase):
    """Test PaymentGatewayManager functionality"""

    def setUp(self):
        """Set up test payment gateway manager"""
        self.gateway_manager = PaymentGatewayManager()

    @patch('src.gateways.payment_gateways.OrderService.get_order_by_id')
    @patch('src.gateways.payment_gateways.PaymentService.create_payment')
    def test_process_payment_unsupported_method(self, mock_create_payment, mock_get_order):
        """Test processing payment with unsupported method"""
        mock_order = Mock()
        mock_order.id = 1
        mock_order.user_id = 1
        mock_get_order.return_value = mock_order

        result = self.gateway_manager.process_payment(
            payment_method="unsupported",
            order_id="ORD-123",
            amount=100.0
        )

        self.assertFalse(result["success"])
        self.assertIn("Unsupported payment method", result["error"])


class TestIntegration(unittest.IsolatedAsyncioTestCase):
    """Integration tests for bot functionality"""

    async def test_bot_command_validation(self):
        """Test bot command input validation"""
        from bot import TelegramBot

        bot = TelegramBot()

        # Mock update and context
        update = Mock()
        context = Mock()
        update.effective_user = Mock()
        update.effective_user.id = 123456
        update.message = Mock()
        context.args = ["invalid_amount"]

        # Mock the reply_text method to be async
        update.message.reply_text = AsyncMock()

        # Test invalid payment amount
        await bot.pay_command(update, context)

        # Should have called reply_text with error message
        update.message.reply_text.assert_called()


if __name__ == '__main__':
    # Set up test environment
    os.environ['TELEGRAM_BOT_TOKEN'] = 'test_token'
    os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
    os.environ['SECRET_KEY'] = 'test_secret_key'

    # Run tests
    unittest.main(verbosity=2)
