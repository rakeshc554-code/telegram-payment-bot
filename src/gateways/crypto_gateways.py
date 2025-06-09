import requests
import json
import hashlib
import hmac
from datetime import datetime
from config.config import Config
import logging

logger = logging.getLogger(__name__)


class BitPayGateway:
    """BitPay cryptocurrency payment gateway"""

    def __init__(self):
        """Initialize BitPay gateway"""
        self.api_token = getattr(Config, 'BITPAY_API_TOKEN', None)
        self.environment = getattr(Config, 'BITPAY_ENVIRONMENT', 'test')
        self.notification_url = getattr(Config, 'BITPAY_NOTIFICATION_URL', f"{Config.WEBHOOK_URL}/bitpay/ipn")
        self.redirect_url = getattr(Config, 'BITPAY_REDIRECT_URL', f"{Config.WEBHOOK_URL}/bitpay/redirect")

        # API URLs
        if self.environment == 'prod':
            self.base_url = 'https://bitpay.com/api'
        else:
            self.base_url = 'https://test.bitpay.com/api'

    def create_invoice(self, amount, currency="USD", order_id=None, buyer_email=None):
        """Create BitPay invoice for crypto payment"""
        try:
            if not self.api_token:
                return {"success": False, "error": "BitPay API token not configured"}

            payload = {
                "price": amount,
                "currency": currency,
                "orderId": order_id,
                "notificationURL": self.notification_url,
                "redirectURL": self.redirect_url,
                "transactionSpeed": "medium",
                "fullNotifications": True
            }

            if buyer_email:
                payload["buyer"] = {"email": buyer_email}

            headers = {
                'Authorization': f'Bearer {self.api_token}',
                'Content-Type': 'application/json',
                'X-accept-version': '2.0.0'
            }

            response = requests.post(
                f"{self.base_url}/invoices",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                invoice_data = result.get('data', {})

                logger.info(f"BitPay invoice created: {invoice_data.get('id')}")
                return {
                    "success": True,
                    "invoice_id": invoice_data.get('id'),
                    "payment_url": invoice_data.get('url'),
                    "status": invoice_data.get('status'),
                    "crypto_info": invoice_data.get('paymentCodes', {}),
                    "expiration_time": invoice_data.get('expirationTime')
                }
            else:
                logger.error(f"BitPay invoice creation failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Invoice creation failed: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"BitPay invoice creation error: {e}")
            return {"success": False, "error": str(e)}

    def get_invoice_status(self, invoice_id):
        """Get BitPay invoice status"""
        try:
            if not self.api_token:
                return {"success": False, "error": "BitPay API token not configured"}

            headers = {
                'Authorization': f'Bearer {self.api_token}',
                'X-accept-version': '2.0.0'
            }

            response = requests.get(
                f"{self.base_url}/invoices/{invoice_id}",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                invoice_data = result.get('data', {})

                return {
                    "success": True,
                    "invoice_id": invoice_id,
                    "status": invoice_data.get('status'),
                    "price": invoice_data.get('price'),
                    "currency": invoice_data.get('currency'),
                    "payment_totals": invoice_data.get('paymentTotals', {}),
                    "transaction_currency": invoice_data.get('transactionCurrency')
                }
            else:
                logger.error(f"BitPay invoice status check failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Status check failed: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"BitPay invoice status error: {e}")
            return {"success": False, "error": str(e)}


class CoinGateGateway:
    """CoinGate cryptocurrency payment gateway"""

    def __init__(self):
        """Initialize CoinGate gateway"""
        self.api_token = getattr(Config, 'COINGATE_API_TOKEN', None)
        self.environment = getattr(Config, 'COINGATE_ENVIRONMENT', 'sandbox')
        self.callback_url = getattr(Config, 'COINGATE_CALLBACK_URL', f"{Config.WEBHOOK_URL}/coingate/callback")
        self.success_url = getattr(Config, 'COINGATE_SUCCESS_URL', f"{Config.WEBHOOK_URL}/coingate/success")
        self.cancel_url = getattr(Config, 'COINGATE_CANCEL_URL', f"{Config.WEBHOOK_URL}/coingate/cancel")

        # API URLs
        if self.environment == 'live':
            self.base_url = 'https://api.coingate.com/v2'
        else:
            self.base_url = 'https://api-sandbox.coingate.com/v2'

    def create_order(self, amount, currency="USD", order_id=None, description="Crypto Payment"):
        """Create CoinGate order for crypto payment"""
        try:
            if not self.api_token:
                return {"success": False, "error": "CoinGate API token not configured"}

            payload = {
                "order_id": order_id or f"order_{int(datetime.now().timestamp())}",
                "price_amount": amount,
                "price_currency": currency,
                "receive_currency": currency,
                "title": "Payment via Telegram Bot",
                "description": description,
                "callback_url": self.callback_url,
                "success_url": self.success_url,
                "cancel_url": self.cancel_url
            }

            headers = {
                'Authorization': f'Token {self.api_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f"{self.base_url}/orders",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                logger.info(f"CoinGate order created: {result.get('id')}")
                return {
                    "success": True,
                    "order_id": result.get('id'),
                    "payment_url": result.get('payment_url'),
                    "status": result.get('status'),
                    "price_amount": result.get('price_amount'),
                    "price_currency": result.get('price_currency'),
                    "lightning_network": result.get('lightning_network'),
                    "created_at": result.get('created_at')
                }
            else:
                logger.error(f"CoinGate order creation failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Order creation failed: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"CoinGate order creation error: {e}")
            return {"success": False, "error": str(e)}

    def get_order_status(self, order_id):
        """Get CoinGate order status"""
        try:
            if not self.api_token:
                return {"success": False, "error": "CoinGate API token not configured"}

            headers = {
                'Authorization': f'Token {self.api_token}'
            }

            response = requests.get(
                f"{self.base_url}/orders/{order_id}",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()

                return {
                    "success": True,
                    "order_id": order_id,
                    "status": result.get('status'),
                    "price_amount": result.get('price_amount'),
                    "price_currency": result.get('price_currency'),
                    "receive_amount": result.get('receive_amount'),
                    "receive_currency": result.get('receive_currency'),
                    "payment_currency": result.get('payment_currency'),
                    "payment_amount": result.get('payment_amount')
                }
            else:
                logger.error(f"CoinGate order status check failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Status check failed: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"CoinGate order status error: {e}")
            return {"success": False, "error": str(e)}


class CryptoPaymentGateway:
    """Unified cryptocurrency payment gateway manager"""

    def __init__(self):
        """Initialize crypto payment gateways"""
        self.bitpay = BitPayGateway()
        self.coingate = CoinGateGateway()

    def process_payment(self, provider, amount, currency="USD", order_id=None, user_email=None):
        """Process cryptocurrency payment"""
        try:
            if provider.lower() == 'bitpay':
                return self.bitpay.create_invoice(
                    amount=amount,
                    currency=currency,
                    order_id=order_id,
                    buyer_email=user_email
                )
            elif provider.lower() == 'coingate':
                return self.coingate.create_order(
                    amount=amount,
                    currency=currency,
                    order_id=order_id,
                    description=f"Payment for Order {order_id}"
                )
            else:
                return {"success": False, "error": "Unsupported crypto payment provider"}

        except Exception as e:
            logger.error(f"Crypto payment error: {e}")
            return {"success": False, "error": str(e)}

    def check_payment_status(self, provider, transaction_id):
        """Check cryptocurrency payment status"""
        try:
            if provider.lower() == 'bitpay':
                return self.bitpay.get_invoice_status(transaction_id)
            elif provider.lower() == 'coingate':
                return self.coingate.get_order_status(transaction_id)
            else:
                return {"success": False, "error": "Unsupported crypto payment provider"}

        except Exception as e:
            logger.error(f"Crypto payment status check error: {e}")
            return {"success": False, "error": str(e)}

    def get_supported_currencies(self, provider):
        """Get supported cryptocurrencies for provider"""
        if provider.lower() == 'bitpay':
            return ['BTC', 'BCH', 'ETH', 'USDC', 'GUSD', 'PAX', 'BUSD', 'DOGE', 'LTC', 'XRP']
        elif provider.lower() == 'coingate':
            return ['BTC', 'ETH', 'LTC', 'XRP', 'BCH', 'BNB', 'USDT', 'USDC', 'DAI', 'DOGE']
        else:
            return []


# Global crypto payment gateway
crypto_payment_gateway = CryptoPaymentGateway()
