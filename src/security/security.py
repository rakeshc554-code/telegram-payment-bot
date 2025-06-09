import time
import hashlib
import hmac
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    def __init__(self):
        """Initialize rate limiter with in-memory storage"""
        self.requests = defaultdict(list)
        self.limits = {
            'default': {'requests': 10, 'window': 60},  # 10 requests per minute
            'payment': {'requests': 5, 'window': 300},  # 5 payments per 5 minutes
            'support': {'requests': 3, 'window': 600},  # 3 support tickets per 10 minutes
        }

    def is_allowed(self, identifier, limit_type='default'):
        """Check if request is allowed under rate limit"""
        now = time.time()
        limit_config = self.limits.get(limit_type, self.limits['default'])
        window = limit_config['window']
        max_requests = limit_config['requests']

        # Clean old requests
        self.requests[identifier] = [
            req_time for req_time in self.requests[identifier]
            if now - req_time < window
        ]

        # Check if under limit
        if len(self.requests[identifier]) < max_requests:
            self.requests[identifier].append(now)
            return True

        return False

    def get_remaining_time(self, identifier, limit_type='default'):
        """Get time until rate limit resets"""
        if not self.requests[identifier]:
            return 0

        window = self.limits.get(limit_type, self.limits['default'])['window']
        oldest_request = min(self.requests[identifier])
        return max(0, window - (time.time() - oldest_request))


class SecurityValidator:
    @staticmethod
    def validate_payment_amount(amount):
        """Validate payment amount"""
        try:
            amount = float(amount)
            if amount <= 0:
                return False, "Amount must be positive"
            if amount > 10000:  # Max amount limit
                return False, "Amount exceeds maximum limit"
            if amount < 0.01:  # Min amount limit
                return False, "Amount below minimum limit"
            return True, None
        except (ValueError, TypeError):
            return False, "Invalid amount format"

    @staticmethod
    def validate_order_id(order_id):
        """Validate order ID format"""
        if not order_id or len(order_id) < 10:
            return False, "Invalid order ID format"
        if not order_id.startswith('ORD-'):
            return False, "Invalid order ID prefix"
        return True, None

    @staticmethod
    def validate_ticket_subject(subject):
        """Validate support ticket subject"""
        if not subject or len(subject.strip()) < 5:
            return False, "Subject too short (minimum 5 characters)"
        if len(subject) > 200:
            return False, "Subject too long (maximum 200 characters)"
        return True, None

    @staticmethod
    def sanitize_input(text):
        """Sanitize user input"""
        if not text:
            return ""

        # Remove potentially dangerous characters
        dangerous_chars = ['<', '>', '"', "'", '&', '\x00', '\n\r']
        sanitized = str(text)

        for char in dangerous_chars:
            sanitized = sanitized.replace(char, '')

        return sanitized.strip()[:1000]  # Limit length

    @staticmethod
    def generate_secure_token():
        """Generate secure random token"""
        import secrets
        return secrets.token_urlsafe(32)


class DataEncryption:
    def __init__(self, key=None):
        """Initialize encryption with key"""
        from cryptography.fernet import Fernet
        if key:
            self.cipher = Fernet(key.encode() if isinstance(key, str) else key)
        else:
            self.cipher = Fernet(Fernet.generate_key())

    def encrypt(self, data):
        """Encrypt sensitive data"""
        try:
            if isinstance(data, str):
                data = data.encode()
            return self.cipher.encrypt(data).decode()
        except Exception as e:
            logger.error(f"Encryption error: {e}")
            return None

    def decrypt(self, encrypted_data):
        """Decrypt sensitive data"""
        try:
            if isinstance(encrypted_data, str):
                encrypted_data = encrypted_data.encode()
            return self.cipher.decrypt(encrypted_data).decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return None


class WebhookSecurity:
    @staticmethod
    def verify_signature(payload, signature, secret):
        """Verify webhook signature"""
        try:
            expected_signature = hmac.new(
                secret.encode(),
                payload,
                hashlib.sha256
            ).hexdigest()

            # Use secure comparison to prevent timing attacks
            return hmac.compare_digest(signature, expected_signature)
        except Exception as e:
            logger.error(f"Signature verification error: {e}")
            return False

    @staticmethod
    def validate_timestamp(timestamp, tolerance=300):
        """Validate webhook timestamp (5 minute tolerance)"""
        try:
            webhook_time = int(timestamp)
            current_time = int(time.time())
            return abs(current_time - webhook_time) <= tolerance
        except (ValueError, TypeError):
            return False


def rate_limit(limit_type='default'):
    """Decorator for rate limiting"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            user_id = update.effective_user.id
            rate_limiter = getattr(self, '_rate_limiter', None)

            if not rate_limiter:
                # Initialize rate limiter if not exists
                self._rate_limiter = RateLimiter()
                rate_limiter = self._rate_limiter

            if not rate_limiter.is_allowed(str(user_id), limit_type):
                remaining_time = rate_limiter.get_remaining_time(str(user_id), limit_type)
                await update.message.reply_text(
                    f"⚠️ Rate limit exceeded. Please try again in {int(remaining_time)} seconds."
                )
                return

            return await func(self, update, context, *args, **kwargs)

        return wrapper

    return decorator


def validate_input(validation_func, error_message="Invalid input"):
    """Decorator for input validation"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            # Extract input based on function context
            if hasattr(update, 'message') and update.message and context.args:
                user_input = ' '.join(context.args)
                is_valid, error = validation_func(user_input)

                if not is_valid:
                    await update.message.reply_text(f"❌ {error or error_message}")
                    return

            return await func(self, update, context, *args, **kwargs)

        return wrapper

    return decorator


def log_user_action(action_type):
    """Decorator for logging user actions"""

    def decorator(func):
        @wraps(func)
        async def wrapper(self, update, context, *args, **kwargs):
            user = update.effective_user
            logger.info(
                f"User action: {action_type} | "
                f"User: {user.id} ({user.username or user.first_name}) | "
                f"Function: {func.__name__}"
            )
            return await func(self, update, context, *args, **kwargs)

        return wrapper

    return decorator


# Global instances
rate_limiter = RateLimiter()
security_validator = SecurityValidator()
webhook_security = WebhookSecurity()

# Initialize encryption with config
try:
    from config import Config

    data_encryption = DataEncryption(Config.ENCRYPTION_KEY)
except Exception as e:
    logger.warning(f"Encryption initialization failed: {e}")
    data_encryption = DataEncryption()  # Use default key
