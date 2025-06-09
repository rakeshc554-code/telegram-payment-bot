import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    # Bot Configuration
    TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')

    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL')
    REDIS_URL = os.getenv('REDIS_URL')

    # PayPal Configuration
    PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID')
    PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET')
    PAYPAL_MODE = os.getenv('PAYPAL_MODE', 'sandbox')

    # Stripe Configuration
    STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')
    STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')

    # Security Configuration
    SECRET_KEY = os.getenv('SECRET_KEY')
    ENCRYPTION_KEY = os.getenv('ENCRYPTION_KEY')

    # Email Configuration
    SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
    EMAIL_USER = os.getenv('EMAIL_USER')
    EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
    FROM_EMAIL = os.getenv('FROM_EMAIL')

    # Mobile Money Configuration
    # M-Pesa Settings
    MPESA_CONSUMER_KEY = os.getenv('MPESA_CONSUMER_KEY')
    MPESA_CONSUMER_SECRET = os.getenv('MPESA_CONSUMER_SECRET')
    MPESA_BUSINESS_SHORT_CODE = os.getenv('MPESA_BUSINESS_SHORT_CODE')
    MPESA_PASSKEY = os.getenv('MPESA_PASSKEY')
    MPESA_ENVIRONMENT = os.getenv('MPESA_ENVIRONMENT', 'sandbox')
    MPESA_CALLBACK_URL = os.getenv('MPESA_CALLBACK_URL')

    # MTN Mobile Money Settings
    MTN_SUBSCRIPTION_KEY = os.getenv('MTN_SUBSCRIPTION_KEY')
    MTN_API_USER = os.getenv('MTN_API_USER')
    MTN_API_KEY = os.getenv('MTN_API_KEY')
    MTN_ENVIRONMENT = os.getenv('MTN_ENVIRONMENT', 'sandbox')

    # Cryptocurrency Payment Configuration
    # BitPay Settings
    BITPAY_API_TOKEN = os.getenv('BITPAY_API_TOKEN')
    BITPAY_ENVIRONMENT = os.getenv('BITPAY_ENVIRONMENT', 'test')
    BITPAY_NOTIFICATION_URL = os.getenv('BITPAY_NOTIFICATION_URL')
    BITPAY_REDIRECT_URL = os.getenv('BITPAY_REDIRECT_URL')

    # CoinGate Settings
    COINGATE_API_TOKEN = os.getenv('COINGATE_API_TOKEN')
    COINGATE_ENVIRONMENT = os.getenv('COINGATE_ENVIRONMENT', 'sandbox')
    COINGATE_CALLBACK_URL = os.getenv('COINGATE_CALLBACK_URL')
    COINGATE_SUCCESS_URL = os.getenv('COINGATE_SUCCESS_URL')
    COINGATE_CANCEL_URL = os.getenv('COINGATE_CANCEL_URL')

    # Application Settings
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    MAX_PAYMENT_AMOUNT = float(os.getenv('MAX_PAYMENT_AMOUNT', 10000))
    MIN_PAYMENT_AMOUNT = float(os.getenv('MIN_PAYMENT_AMOUNT', 1))

    @classmethod
    def validate_config(cls):
        """Validate that all required configuration is present"""
        required_vars = [
            'TELEGRAM_BOT_TOKEN',
            'DATABASE_URL',
            'SECRET_KEY'
        ]

        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        return True

