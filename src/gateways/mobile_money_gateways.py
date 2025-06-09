import requests
import json
import base64
import hashlib
from datetime import datetime
from config.config import Config
import logging

logger = logging.getLogger(__name__)


class MPesaGateway:
    """M-Pesa payment gateway integration"""

    def __init__(self):
        """Initialize M-Pesa gateway"""
        self.consumer_key = getattr(Config, 'MPESA_CONSUMER_KEY', None)
        self.consumer_secret = getattr(Config, 'MPESA_CONSUMER_SECRET', None)
        self.business_short_code = getattr(Config, 'MPESA_BUSINESS_SHORT_CODE', None)
        self.passkey = getattr(Config, 'MPESA_PASSKEY', None)
        self.callback_url = getattr(Config, 'MPESA_CALLBACK_URL', f"{Config.WEBHOOK_URL}/mpesa/callback")
        self.environment = getattr(Config, 'MPESA_ENVIRONMENT', 'sandbox')

        # API URLs
        if self.environment == 'production':
            self.base_url = 'https://api.safaricom.co.ke'
        else:
            self.base_url = 'https://sandbox.safaricom.co.ke'

    def get_access_token(self):
        """Get OAuth access token"""
        try:
            if not self.consumer_key or not self.consumer_secret:
                return None

            # Create credentials
            credentials = base64.b64encode(f"{self.consumer_key}:{self.consumer_secret}".encode()).decode()

            headers = {
                'Authorization': f'Basic {credentials}',
                'Content-Type': 'application/json'
            }

            response = requests.get(
                f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get('access_token')
            else:
                logger.error(f"M-Pesa token error: {response.text}")
                return None

        except Exception as e:
            logger.error(f"M-Pesa token generation error: {e}")
            return None

    def generate_password(self):
        """Generate password for STK push"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        password_string = f"{self.business_short_code}{self.passkey}{timestamp}"
        password = base64.b64encode(password_string.encode()).decode()
        return password, timestamp

    def initiate_stk_push(self, phone_number, amount, account_reference, transaction_desc="Payment"):
        """Initiate STK push payment"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            password, timestamp = self.generate_password()

            # Format phone number (remove + and ensure it starts with 254)
            phone = phone_number.replace('+', '').replace(' ', '')
            if phone.startswith('0'):
                phone = '254' + phone[1:]
            elif not phone.startswith('254'):
                phone = '254' + phone

            payload = {
                "BusinessShortCode": self.business_short_code,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(amount),
                "PartyA": phone,
                "PartyB": self.business_short_code,
                "PhoneNumber": phone,
                "CallBackURL": self.callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers=headers,
                timeout=30
            )

            result = response.json()

            if response.status_code == 200 and result.get('ResponseCode') == '0':
                logger.info(f"M-Pesa STK push initiated: {result.get('CheckoutRequestID')}")
                return {
                    "success": True,
                    "checkout_request_id": result.get('CheckoutRequestID'),
                    "merchant_request_id": result.get('MerchantRequestID'),
                    "response_description": result.get('ResponseDescription')
                }
            else:
                logger.error(f"M-Pesa STK push failed: {result}")
                return {
                    "success": False,
                    "error": result.get('errorMessage', 'STK push failed')
                }

        except Exception as e:
            logger.error(f"M-Pesa STK push error: {e}")
            return {"success": False, "error": str(e)}


class MTNMoMoGateway:
    """MTN Mobile Money gateway integration"""

    def __init__(self):
        """Initialize MTN MoMo gateway"""
        self.subscription_key = getattr(Config, 'MTN_SUBSCRIPTION_KEY', None)
        self.api_user = getattr(Config, 'MTN_API_USER', None)
        self.api_key = getattr(Config, 'MTN_API_KEY', None)
        self.environment = getattr(Config, 'MTN_ENVIRONMENT', 'sandbox')

        # API URLs
        if self.environment == 'production':
            self.base_url = 'https://ericssonbasicapi2.azure-api.net'
        else:
            self.base_url = 'https://sandbox.momodeveloper.mtn.com'

    def get_access_token(self):
        """Get OAuth access token"""
        try:
            if not self.subscription_key or not self.api_user or not self.api_key:
                return None

            headers = {
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'Authorization': f'Basic {base64.b64encode(f"{self.api_user}:{self.api_key}".encode()).decode()}'
            }

            response = requests.post(
                f"{self.base_url}/collection/token/",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                return response.json().get('access_token')
            else:
                logger.error(f"MTN MoMo token error: {response.text}")
                return None

        except Exception as e:
            logger.error(f"MTN MoMo token generation error: {e}")
            return None

    def request_to_pay(self, phone_number, amount, currency="EUR", payer_message="Payment", payee_note="Payment"):
        """Request payment from customer"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            # Generate reference ID
            reference_id = f"mtn_{int(datetime.now().timestamp())}"

            # Format phone number
            phone = phone_number.replace('+', '').replace(' ', '')

            payload = {
                "amount": str(int(amount)),
                "currency": currency,
                "externalId": reference_id,
                "payer": {
                    "partyIdType": "MSISDN",
                    "partyId": phone
                },
                "payerMessage": payer_message,
                "payeeNote": payee_note
            }

            headers = {
                'Authorization': f'Bearer {access_token}',
                'X-Reference-Id': reference_id,
                'X-Target-Environment': self.environment,
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'Content-Type': 'application/json'
            }

            response = requests.post(
                f"{self.base_url}/collection/v1_0/requesttopay",
                json=payload,
                headers=headers,
                timeout=30
            )

            if response.status_code == 202:
                logger.info(f"MTN MoMo payment request created: {reference_id}")
                return {
                    "success": True,
                    "reference_id": reference_id,
                    "status": "PENDING"
                }
            else:
                logger.error(f"MTN MoMo payment request failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Payment request failed: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"MTN MoMo payment request error: {e}")
            return {"success": False, "error": str(e)}

    def get_payment_status(self, reference_id):
        """Get payment status"""
        try:
            access_token = self.get_access_token()
            if not access_token:
                return {"success": False, "error": "Failed to get access token"}

            headers = {
                'Authorization': f'Bearer {access_token}',
                'X-Target-Environment': self.environment,
                'Ocp-Apim-Subscription-Key': self.subscription_key
            }

            response = requests.get(
                f"{self.base_url}/collection/v1_0/requesttopay/{reference_id}",
                headers=headers,
                timeout=30
            )

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": True,
                    "status": result.get('status'),
                    "reference_id": reference_id,
                    "financial_transaction_id": result.get('financialTransactionId')
                }
            else:
                logger.error(f"MTN MoMo status check failed: {response.text}")
                return {
                    "success": False,
                    "error": f"Status check failed: {response.status_code}"
                }

        except Exception as e:
            logger.error(f"MTN MoMo status check error: {e}")
            return {"success": False, "error": str(e)}


class MobileMoneyGateway:
    """Unified mobile money gateway manager"""

    def __init__(self):
        """Initialize mobile money gateways"""
        self.mpesa = MPesaGateway()
        self.mtn = MTNMoMoGateway()

    def process_payment(self, provider, phone_number, amount, order_id, currency="USD"):
        """Process mobile money payment"""
        try:
            if provider.lower() == 'mpesa':
                return self.mpesa.initiate_stk_push(
                    phone_number=phone_number,
                    amount=amount,
                    account_reference=f"ORDER_{order_id}",
                    transaction_desc=f"Payment for Order {order_id}"
                )
            elif provider.lower() == 'mtn':
                return self.mtn.request_to_pay(
                    phone_number=phone_number,
                    amount=amount,
                    currency=currency,
                    payer_message=f"Payment for Order {order_id}",
                    payee_note=f"Order {order_id} payment"
                )
            else:
                return {"success": False, "error": "Unsupported mobile money provider"}

        except Exception as e:
            logger.error(f"Mobile money payment error: {e}")
            return {"success": False, "error": str(e)}

    def check_payment_status(self, provider, reference_id):
        """Check mobile money payment status"""
        try:
            if provider.lower() == 'mpesa':
                # M-Pesa status is handled via callback
                return {"success": True, "status": "PENDING"}
            elif provider.lower() == 'mtn':
                return self.mtn.get_payment_status(reference_id)
            else:
                return {"success": False, "error": "Unsupported mobile money provider"}

        except Exception as e:
            logger.error(f"Mobile money status check error: {e}")
            return {"success": False, "error": str(e)}


# Global mobile money gateway
mobile_money_gateway = MobileMoneyGateway()
