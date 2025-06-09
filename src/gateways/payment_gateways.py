import stripe
import paypalrestsdk
from config.config import Config
from src.services.services import PaymentService, OrderService
from src.models.models import PaymentStatus, OrderStatus
import logging
import json

logger = logging.getLogger(__name__)


class PayPalPaymentGateway:
    def __init__(self):
        """Initialize PayPal SDK"""
        paypalrestsdk.configure({
            "mode": Config.PAYPAL_MODE,  # sandbox or live
            "client_id": Config.PAYPAL_CLIENT_ID,
            "client_secret": Config.PAYPAL_CLIENT_SECRET
        })

    def create_payment(self, amount, currency="USD", description="Payment via Telegram Bot", return_url=None,
                       cancel_url=None):
        """Create PayPal payment"""
        try:
            payment = paypalrestsdk.Payment({
                "intent": "sale",
                "payer": {
                    "payment_method": "paypal"
                },
                "redirect_urls": {
                    "return_url": return_url or f"{Config.WEBHOOK_URL}/paypal/return",
                    "cancel_url": cancel_url or f"{Config.WEBHOOK_URL}/paypal/cancel"
                },
                "transactions": [{
                    "item_list": {
                        "items": [{
                            "name": description,
                            "sku": "telegram_bot_payment",
                            "price": str(amount),
                            "currency": currency,
                            "quantity": 1
                        }]
                    },
                    "amount": {
                        "total": str(amount),
                        "currency": currency
                    },
                    "description": description
                }]
            })

            if payment.create():
                logger.info(f"PayPal payment created: {payment.id}")
                # Find approval URL
                approval_url = None
                for link in payment.links:
                    if link.rel == "approval_url":
                        approval_url = link.href
                        break

                return {
                    "success": True,
                    "payment_id": payment.id,
                    "approval_url": approval_url,
                    "payment": payment
                }
            else:
                logger.error(f"PayPal payment creation failed: {payment.error}")
                return {
                    "success": False,
                    "error": payment.error
                }

        except Exception as e:
            logger.error(f"PayPal payment creation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def execute_payment(self, payment_id, payer_id):
        """Execute PayPal payment after approval"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)

            if payment.execute({"payer_id": payer_id}):
                logger.info(f"PayPal payment executed: {payment_id}")
                return {
                    "success": True,
                    "payment": payment,
                    "transaction_id": payment.transactions[0].related_resources[0].sale.id
                }
            else:
                logger.error(f"PayPal payment execution failed: {payment.error}")
                return {
                    "success": False,
                    "error": payment.error
                }

        except Exception as e:
            logger.error(f"PayPal payment execution error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_payment_status(self, payment_id):
        """Get PayPal payment status"""
        try:
            payment = paypalrestsdk.Payment.find(payment_id)
            return {
                "success": True,
                "status": payment.state,
                "payment": payment
            }
        except Exception as e:
            logger.error(f"PayPal payment status error: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class StripePaymentGateway:
    def __init__(self):
        """Initialize Stripe SDK"""
        stripe.api_key = Config.STRIPE_SECRET_KEY

    def create_payment_intent(self, amount, currency="usd", description="Payment via Telegram Bot", metadata=None,
                              enable_3d_secure=True):
        """Create Stripe payment intent with 3D Secure support"""
        try:
            # Convert amount to cents for Stripe
            amount_cents = int(amount * 100)

            # Configure payment intent with 3D Secure
            payment_intent_data = {
                'amount': amount_cents,
                'currency': currency,
                'description': description,
                'metadata': metadata or {},
                'automatic_payment_methods': {
                    'enabled': True,
                }
            }

            # Enable 3D Secure authentication
            if enable_3d_secure:
                payment_intent_data.update({
                    'confirmation_method': 'manual',
                    'confirm': False,
                    'payment_method_options': {
                        'card': {
                            'request_three_d_secure': 'automatic'
                        }
                    }
                })

            intent = stripe.PaymentIntent.create(**payment_intent_data)

            logger.info(f"Stripe payment intent created with 3D Secure: {intent.id}")
            return {
                "success": True,
                "payment_intent_id": intent.id,
                "client_secret": intent.client_secret,
                "amount": amount,
                "currency": currency,
                "status": intent.status,
                "requires_action": intent.status == 'requires_action',
                "next_action": intent.next_action if hasattr(intent, 'next_action') else None
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment intent creation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Stripe payment intent creation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def confirm_payment_intent(self, payment_intent_id, payment_method_id=None):
        """Confirm Stripe payment intent"""
        try:
            intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                payment_method=payment_method_id
            )

            logger.info(f"Stripe payment intent confirmed: {payment_intent_id}")
            return {
                "success": True,
                "payment_intent": intent,
                "status": intent.status
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment confirmation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def confirm_payment_intent_with_3ds(self, payment_intent_id, payment_method_id=None, return_url=None):
        """Confirm Stripe payment intent with 3D Secure handling"""
        try:
            # Set return URL for 3D Secure redirects
            if not return_url:
                return_url = f"{Config.WEBHOOK_URL}/stripe/3ds-return"

            confirm_data = {
                'return_url': return_url
            }

            if payment_method_id:
                confirm_data['payment_method'] = payment_method_id

            intent = stripe.PaymentIntent.confirm(
                payment_intent_id,
                **confirm_data
            )

            logger.info(f"Stripe payment intent confirmed with 3DS: {payment_intent_id}")

            response = {
                "success": True,
                "payment_intent": intent,
                "status": intent.status
            }

            # Handle 3D Secure authentication requirements
            if intent.status == 'requires_action':
                if intent.next_action and intent.next_action.type == 'use_stripe_sdk':
                    response.update({
                        "requires_action": True,
                        "next_action": intent.next_action,
                        "client_secret": intent.client_secret
                    })
                elif intent.next_action and intent.next_action.type == 'redirect_to_url':
                    response.update({
                        "requires_redirect": True,
                        "redirect_url": intent.next_action.redirect_to_url.url,
                        "return_url": intent.next_action.redirect_to_url.return_url
                    })

            return response

        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment confirmation with 3DS failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def handle_3ds_return(self, payment_intent_id):
        """Handle return from 3D Secure authentication"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if intent.status == 'requires_confirmation':
                # Final confirmation after 3DS
                intent = stripe.PaymentIntent.confirm(payment_intent_id)

            logger.info(f"3D Secure return handled for: {payment_intent_id}, status: {intent.status}")
            return {
                "success": True,
                "payment_intent": intent,
                "status": intent.status,
                "authentication_complete": intent.status in ['succeeded', 'processing']
            }

        except stripe.error.StripeError as e:
            logger.error(f"3D Secure return handling failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def get_payment_intent(self, payment_intent_id):
        """Get Stripe payment intent status"""
        try:
            intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            return {
                "success": True,
                "payment_intent": intent,
                "status": intent.status
            }
        except stripe.error.StripeError as e:
            logger.error(f"Stripe payment intent retrieval failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    def create_customer(self, email=None, name=None, metadata=None):
        """Create Stripe customer"""
        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {}
            )

            logger.info(f"Stripe customer created: {customer.id}")
            return {
                "success": True,
                "customer": customer
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe customer creation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }


class PaymentGatewayManager:
    def __init__(self):
        """Initialize payment gateways"""
        self.paypal = PayPalPaymentGateway()
        self.stripe = StripePaymentGateway()

        # Import new gateways
        try:
            from src.gateways.mobile_money_gateways import mobile_money_gateway
            from src.gateways.crypto_gateways import crypto_payment_gateway
            self.mobile_money = mobile_money_gateway
            self.crypto = crypto_payment_gateway
        except ImportError as e:
            logger.warning(f"Failed to import additional payment gateways: {e}")
            self.mobile_money = None
            self.crypto = None

    def process_payment(self, payment_method, order_id, amount, currency="USD", user_data=None):
        """Process payment through selected gateway"""
        try:
            order = OrderService.get_order_by_id(order_id)
            if not order:
                return {"success": False, "error": "Order not found"}

            # Create payment record
            payment = PaymentService.create_payment(
                order_id=order.id,
                user_id=order.user_id,
                amount=amount,
                currency=currency,
                payment_method=payment_method
            )

            if payment_method == "paypal":
                result = self.paypal.create_payment(
                    amount=amount,
                    currency=currency,
                    description=f"Order {order_id}"
                )

                if result["success"]:
                    # Update payment with gateway transaction ID
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.PENDING,
                        gateway_transaction_id=result["payment_id"],
                        gateway_response=json.dumps(result)
                    )

                    return {
                        "success": True,
                        "payment_id": payment.payment_id,
                        "gateway_payment_id": result["payment_id"],
                        "approval_url": result["approval_url"],
                        "gateway": "paypal"
                    }
                else:
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.FAILED,
                        gateway_response=json.dumps(result)
                    )
                    return result

            elif payment_method == "stripe":
                result = self.stripe.create_payment_intent(
                    amount=amount,
                    currency=currency.lower(),
                    description=f"Order {order_id}",
                    metadata={"order_id": order_id, "payment_id": payment.payment_id}
                )

                if result["success"]:
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.PENDING,
                        gateway_transaction_id=result["payment_intent_id"],
                        gateway_response=json.dumps(result)
                    )

                    return {
                        "success": True,
                        "payment_id": payment.payment_id,
                        "gateway_payment_id": result["payment_intent_id"],
                        "client_secret": result["client_secret"],
                        "gateway": "stripe"
                    }
                else:
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.FAILED,
                        gateway_response=json.dumps(result)
                    )
                    return result

            elif payment_method.startswith("mobile_"):
                # Handle mobile money payments
                if not self.mobile_money:
                    return {"success": False, "error": "Mobile money gateway not available"}

                provider = payment_method.split("_")[1]  # mobile_mpesa -> mpesa
                phone_number = user_data.get("phone_number") if user_data else None

                if not phone_number:
                    return {"success": False, "error": "Phone number required for mobile money payment"}

                result = self.mobile_money.process_payment(
                    provider=provider,
                    phone_number=phone_number,
                    amount=amount,
                    order_id=order_id,
                    currency=currency
                )

                if result["success"]:
                    gateway_id = result.get("checkout_request_id") or result.get("reference_id")
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.PENDING,
                        gateway_transaction_id=gateway_id,
                        gateway_response=json.dumps(result)
                    )

                    return {
                        "success": True,
                        "payment_id": payment.payment_id,
                        "gateway_payment_id": gateway_id,
                        "provider": provider,
                        "gateway": "mobile_money",
                        "instructions": f"Check your phone for {provider.upper()} payment prompt"
                    }
                else:
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.FAILED,
                        gateway_response=json.dumps(result)
                    )
                    return result

            elif payment_method.startswith("crypto_"):
                # Handle cryptocurrency payments
                if not self.crypto:
                    return {"success": False, "error": "Crypto payment gateway not available"}

                provider = payment_method.split("_")[1]  # crypto_bitpay -> bitpay
                user_email = user_data.get("email") if user_data else None

                result = self.crypto.process_payment(
                    provider=provider,
                    amount=amount,
                    currency=currency,
                    order_id=order_id,
                    user_email=user_email
                )

                if result["success"]:
                    gateway_id = result.get("invoice_id") or result.get("order_id")
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.PENDING,
                        gateway_transaction_id=gateway_id,
                        gateway_response=json.dumps(result)
                    )

                    return {
                        "success": True,
                        "payment_id": payment.payment_id,
                        "gateway_payment_id": gateway_id,
                        "payment_url": result.get("payment_url"),
                        "provider": provider,
                        "gateway": "crypto",
                        "supported_currencies": self.crypto.get_supported_currencies(provider)
                    }
                else:
                    PaymentService.update_payment_status(
                        payment.payment_id,
                        PaymentStatus.FAILED,
                        gateway_response=json.dumps(result)
                    )
                    return result

            else:
                return {"success": False, "error": "Unsupported payment method"}

        except Exception as e:
            logger.error(f"Payment processing error: {e}")
            return {"success": False, "error": str(e)}

    def handle_payment_confirmation(self, gateway, gateway_payment_id, additional_data=None):
        """Handle payment confirmation from gateway"""
        try:
            if gateway == "paypal":
                # Execute PayPal payment
                payer_id = additional_data.get("payer_id") if additional_data else None
                if not payer_id:
                    return {"success": False, "error": "Missing payer_id for PayPal"}

                result = self.paypal.execute_payment(gateway_payment_id, payer_id)

                if result["success"]:
                    # Update payment status
                    payment = self._get_payment_by_gateway_id(gateway_payment_id)
                    if payment:
                        PaymentService.update_payment_status(
                            payment.payment_id,
                            PaymentStatus.COMPLETED,
                            gateway_response=json.dumps(result)
                        )

                        # Update order status
                        OrderService.update_order_status(
                            payment.order.order_id,
                            OrderStatus.PAYMENT_CONFIRMED
                        )

                        return {"success": True, "payment": payment}

                return result

            elif gateway == "stripe":
                # Check Stripe payment status
                result = self.stripe.get_payment_intent(gateway_payment_id)

                if result["success"]:
                    intent = result["payment_intent"]
                    payment = self._get_payment_by_gateway_id(gateway_payment_id)

                    if payment:
                        if intent.status == "succeeded":
                            PaymentService.update_payment_status(
                                payment.payment_id,
                                PaymentStatus.COMPLETED,
                                gateway_response=json.dumps(result)
                            )

                            OrderService.update_order_status(
                                payment.order.order_id,
                                OrderStatus.PAYMENT_CONFIRMED
                            )
                        elif intent.status == "payment_failed":
                            PaymentService.update_payment_status(
                                payment.payment_id,
                                PaymentStatus.FAILED,
                                gateway_response=json.dumps(result)
                            )

                        return {"success": True, "payment": payment, "status": intent.status}

                return result

            else:
                return {"success": False, "error": "Unsupported gateway"}

        except Exception as e:
            logger.error(f"Payment confirmation error: {e}")
            return {"success": False, "error": str(e)}

    def _get_payment_by_gateway_id(self, gateway_transaction_id):
        """Get payment by gateway transaction ID"""
        from config.database import db
        from src.models.models import Payment

        session = db.get_session()
        try:
            return session.query(Payment).filter(
                Payment.gateway_transaction_id == gateway_transaction_id
            ).first()
        finally:
            db.close_session(session)

    def process_refund(self, payment_id, refund_amount=None, reason="Customer Request"):
        """Process payment refund through appropriate gateway"""
        try:
            from src.utils.receipt_service import refund_service
            return refund_service.process_refund(payment_id, refund_amount, reason)
        except Exception as e:
            logger.error(f"Refund processing error: {e}")
            return {"success": False, "error": str(e)}

    def generate_and_send_receipt(self, payment_id, user_email=None):
        """Generate and optionally email payment receipt"""
        try:
            from src.utils.receipt_service import receipt_generator, email_service

            # Generate receipt
            receipt_path = receipt_generator.generate_payment_receipt(payment_id)

            if not receipt_path:
                return {"success": False, "error": "Failed to generate receipt"}

            result = {"success": True, "receipt_path": receipt_path}

            # Send email if email provided
            if user_email:
                email_sent = email_service.send_receipt_email(user_email, payment_id, receipt_path)
                result["email_sent"] = email_sent

            return result

        except Exception as e:
            logger.error(f"Receipt generation error: {e}")
            return {"success": False, "error": str(e)}


# Global payment gateway manager
payment_gateway = PaymentGatewayManager()
