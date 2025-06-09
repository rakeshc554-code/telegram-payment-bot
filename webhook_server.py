from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
import stripe
from config.config import Config
from src.gateways.payment_gateways import payment_gateway
import logging
import json

logger = logging.getLogger(__name__)

app = FastAPI(title="Payment Bot Webhook Server")

# Set up Stripe webhook endpoint secret
stripe.api_key = Config.STRIPE_SECRET_KEY


@app.post("/webhook/mpesa")
async def mpesa_callback(request: Request):
    """Handle M-Pesa STK Push callback"""
    try:
        data = await request.json()
        logger.info(f"M-Pesa callback received: {json.dumps(data, indent=2)}")

        # Extract callback data
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})

        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        checkout_request_id = stk_callback.get('CheckoutRequestID')
        merchant_request_id = stk_callback.get('MerchantRequestID')

        if result_code == 0:
            # Payment successful
            callback_metadata = stk_callback.get('CallbackMetadata', {})
            items = callback_metadata.get('Item', [])

            # Extract payment details from metadata
            payment_details = {}
            for item in items:
                name = item.get('Name')
                value = item.get('Value')
                if name == 'Amount':
                    payment_details['amount'] = value
                elif name == 'MpesaReceiptNumber':
                    payment_details['receipt'] = value
                elif name == 'TransactionDate':
                    payment_details['date'] = value
                elif name == 'PhoneNumber':
                    payment_details['phone'] = value

            # Process payment confirmation
            result = payment_gateway.handle_payment_confirmation(
                gateway="mobile_money",
                gateway_payment_id=checkout_request_id,
                additional_data={
                    "provider": "mpesa",
                    "result_code": result_code,
                    "result_desc": result_desc,
                    "payment_details": payment_details
                }
            )

            logger.info(f"M-Pesa payment confirmed: {checkout_request_id}")
        else:
            # Payment failed
            logger.warning(f"M-Pesa payment failed: {result_desc} (Code: {result_code})")

            result = payment_gateway.handle_payment_confirmation(
                gateway="mobile_money",
                gateway_payment_id=checkout_request_id,
                additional_data={
                    "provider": "mpesa",
                    "result_code": result_code,
                    "result_desc": result_desc,
                    "status": "failed"
                }
            )

        return {"ResultCode": 0, "ResultDesc": "Accepted"}

    except Exception as e:
        logger.error(f"M-Pesa callback error: {e}")
        return {"ResultCode": 1, "ResultDesc": "Failed"}


@app.post("/webhook/mtn")
async def mtn_callback(request: Request):
    """Handle MTN Mobile Money callback"""
    try:
        data = await request.json()
        logger.info(f"MTN callback received: {json.dumps(data, indent=2)}")

        # Extract callback data
        external_id = data.get('externalId')
        financial_transaction_id = data.get('financialTransactionId')
        status = data.get('status')
        reason = data.get('reason', {})

        # Process payment confirmation
        result = payment_gateway.handle_payment_confirmation(
            gateway="mobile_money",
            gateway_payment_id=external_id,
            additional_data={
                "provider": "mtn",
                "status": status,
                "financial_transaction_id": financial_transaction_id,
                "reason": reason
            }
        )

        if status == "SUCCESSFUL":
            logger.info(f"MTN Mobile Money payment confirmed: {external_id}")
        else:
            logger.warning(f"MTN Mobile Money payment {status.lower()}: {external_id}")

        return {"status": "accepted"}

    except Exception as e:
        logger.error(f"MTN callback error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/bitpay")
async def bitpay_ipn(request: Request):
    """Handle BitPay Instant Payment Notification"""
    try:
        data = await request.json()
        logger.info(f"BitPay IPN received: {json.dumps(data, indent=2)}")

        # Extract BitPay data
        invoice_id = data.get('id')
        status = data.get('status')
        order_id = data.get('orderId')
        price = data.get('price')
        currency = data.get('currency')

        # Process payment confirmation
        result = payment_gateway.handle_payment_confirmation(
            gateway="crypto",
            gateway_payment_id=invoice_id,
            additional_data={
                "provider": "bitpay",
                "status": status,
                "order_id": order_id,
                "price": price,
                "currency": currency
            }
        )

        if status in ["confirmed", "complete"]:
            logger.info(f"BitPay payment confirmed: {invoice_id}")
        elif status == "expired":
            logger.warning(f"BitPay payment expired: {invoice_id}")
        elif status == "invalid":
            logger.warning(f"BitPay payment invalid: {invoice_id}")

        return {"status": "accepted"}

    except Exception as e:
        logger.error(f"BitPay IPN error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/coingate")
async def coingate_callback(request: Request):
    """Handle CoinGate callback"""
    try:
        data = await request.json()
        logger.info(f"CoinGate callback received: {json.dumps(data, indent=2)}")

        # Extract CoinGate data
        order_id = data.get('id')
        status = data.get('status')
        price_amount = data.get('price_amount')
        price_currency = data.get('price_currency')
        receive_amount = data.get('receive_amount')
        receive_currency = data.get('receive_currency')

        # Process payment confirmation
        result = payment_gateway.handle_payment_confirmation(
            gateway="crypto",
            gateway_payment_id=order_id,
            additional_data={
                "provider": "coingate",
                "status": status,
                "price_amount": price_amount,
                "price_currency": price_currency,
                "receive_amount": receive_amount,
                "receive_currency": receive_currency
            }
        )

        if status == "paid":
            logger.info(f"CoinGate payment confirmed: {order_id}")
        elif status in ["expired", "canceled", "refunded"]:
            logger.warning(f"CoinGate payment {status}: {order_id}")

        return {"status": "accepted"}

    except Exception as e:
        logger.error(f"CoinGate callback error: {e}")
        return {"status": "error", "message": str(e)}


@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks"""
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, Config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.error(f"Invalid signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        logger.info(f"Payment succeeded: {payment_intent['id']}")

        # Update payment status
        result = payment_gateway.handle_payment_confirmation(
            gateway="stripe",
            gateway_payment_id=payment_intent['id']
        )

        if result["success"]:
            logger.info(f"Payment confirmation processed: {payment_intent['id']}")
        else:
            logger.error(f"Payment confirmation failed: {result.get('error')}")

    elif event['type'] == 'payment_intent.payment_failed':
        payment_intent = event['data']['object']
        logger.info(f"Payment failed: {payment_intent['id']}")

        result = payment_gateway.handle_payment_confirmation(
            gateway="stripe",
            gateway_payment_id=payment_intent['id']
        )

    else:
        logger.info(f"Unhandled event type: {event['type']}")

    return {"status": "success"}


@app.get("/stripe/3ds-return")
async def stripe_3ds_return(request: Request):
    """Handle Stripe 3D Secure authentication return"""
    query_params = request.query_params
    payment_intent_id = query_params.get('payment_intent')
    payment_intent_client_secret = query_params.get('payment_intent_client_secret')
    redirect_status = query_params.get('redirect_status')

    if not payment_intent_id:
        logger.error("Missing Stripe 3DS payment intent ID")
        return HTMLResponse(
            content="<h1>Authentication Error</h1><p>Missing payment intent ID</p>",
            status_code=400
        )

    try:
        # Handle 3D Secure return
        result = payment_gateway.stripe.handle_3ds_return(payment_intent_id)

        if result["success"]:
            if result.get("authentication_complete"):
                # Update payment status
                confirmation_result = payment_gateway.handle_payment_confirmation(
                    gateway="stripe",
                    gateway_payment_id=payment_intent_id
                )

                if confirmation_result["success"]:
                    return HTMLResponse(
                        content="""
                        <h1>Payment Successful!</h1>
                        <p>Your payment has been authenticated and processed successfully.</p>
                        <p>You can now return to the Telegram bot to continue.</p>
                        <script>
                            setTimeout(function() {
                                window.close();
                            }, 3000);
                        </script>
                        """
                    )
                else:
                    return HTMLResponse(
                        content=f"""
                        <h1>Payment Processing Error</h1>
                        <p>Authentication successful but payment processing failed: {confirmation_result.get('error', 'Unknown error')}</p>
                        <p>Please contact support.</p>
                        """,
                        status_code=500
                    )
            else:
                # Authentication failed or still pending
                status = result.get("status", "unknown")
                if status == "requires_payment_method":
                    return HTMLResponse(
                        content="""
                        <h1>Authentication Failed</h1>
                        <p>Card authentication failed. Please try with a different payment method.</p>
                        <p>Return to the Telegram bot to try again.</p>
                        """
                    )
                else:
                    return HTMLResponse(
                        content=f"""
                        <h1>Authentication Incomplete</h1>
                        <p>Payment status: {status}</p>
                        <p>Please return to the Telegram bot for further instructions.</p>
                        """
                    )
        else:
            return HTMLResponse(
                content=f"""
                <h1>Authentication Error</h1>
                <p>There was an error processing your authentication: {result.get('error', 'Unknown error')}</p>
                <p>Please try again or contact support.</p>
                """,
                status_code=400
            )

    except Exception as e:
        logger.error(f"3D Secure return handling error: {e}")
        return HTMLResponse(
            content=f"""
            <h1>System Error</h1>
            <p>There was a system error processing your authentication: {str(e)}</p>
            <p>Please contact support.</p>
            """,
            status_code=500
        )


@app.get("/paypal/return")
async def paypal_return(request: Request):
    """Handle PayPal return after payment approval"""
    query_params = request.query_params
    payment_id = query_params.get('paymentId')
    payer_id = query_params.get('PayerID')

    if not payment_id or not payer_id:
        logger.error("Missing PayPal payment parameters")
        return HTMLResponse(
            content="<h1>Payment Error</h1><p>Missing payment parameters</p>",
            status_code=400
        )

    # Process payment confirmation
    result = payment_gateway.handle_payment_confirmation(
        gateway="paypal",
        gateway_payment_id=payment_id,
        additional_data={"payer_id": payer_id}
    )

    if result["success"]:
        return HTMLResponse(
            content="""
            <h1>Payment Successful!</h1>
            <p>Your payment has been processed successfully.</p>
            <p>You can now return to the Telegram bot to continue.</p>
            <script>
                setTimeout(function() {
                    window.close();
                }, 3000);
            </script>
            """
        )
    else:
        return HTMLResponse(
            content=f"""
            <h1>Payment Error</h1>
            <p>There was an error processing your payment: {result.get('error', 'Unknown error')}</p>
            <p>Please try again or contact support.</p>
            """,
            status_code=400
        )


@app.get("/paypal/cancel")
async def paypal_cancel():
    """Handle PayPal payment cancellation"""
    return HTMLResponse(
        content="""
        <h1>Payment Cancelled</h1>
        <p>Your payment has been cancelled.</p>
        <p>You can return to the Telegram bot to try again.</p>
        <script>
            setTimeout(function() {
                window.close();
            }, 3000);
        </script>
        """
    )


@app.post("/admin/refund")
async def process_refund_endpoint(request: Request):
    """Admin endpoint to process refunds"""
    try:
        data = await request.json()
        payment_id = data.get('payment_id')
        refund_amount = data.get('refund_amount')
        reason = data.get('reason', 'Admin refund')

        if not payment_id:
            raise HTTPException(status_code=400, detail="Payment ID is required")

        result = payment_gateway.process_refund(payment_id, refund_amount, reason)

        if result["success"]:
            return {
                "status": "success",
                "message": "Refund processed successfully",
                "refund_amount": result.get("refund_amount"),
                "receipt_path": result.get("receipt_path")
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Refund failed"))

    except Exception as e:
        logger.error(f"Refund endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/receipt")
async def generate_receipt_endpoint(request: Request):
    """Admin endpoint to generate and send receipts"""
    try:
        data = await request.json()
        payment_id = data.get('payment_id')
        user_email = data.get('user_email')

        if not payment_id:
            raise HTTPException(status_code=400, detail="Payment ID is required")

        result = payment_gateway.generate_and_send_receipt(payment_id, user_email)

        if result["success"]:
            return {
                "status": "success",
                "message": "Receipt generated successfully",
                "receipt_path": result.get("receipt_path"),
                "email_sent": result.get("email_sent", False)
            }
        else:
            raise HTTPException(status_code=400, detail=result.get("error", "Receipt generation failed"))

    except Exception as e:
        logger.error(f"Receipt endpoint error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "Payment Bot Webhook Server is running"}


@app.get("/health")
async def health_check():
    """Health check for monitoring"""
    return {
        "status": "healthy",
        "service": "payment-bot-webhooks",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
