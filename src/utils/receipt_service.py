from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import smtplib
import os
from datetime import datetime
from src.models.models import Payment, Order, User
from config.database import db
import logging

logger = logging.getLogger(__name__)


class ReceiptGenerator:
    def __init__(self):
        """Initialize receipt generator"""
        self.styles = getSampleStyleSheet()
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#2E86AB'),
            alignment=1  # Center alignment
        )

    def generate_payment_receipt(self, payment_id, output_path=None):
        """Generate PDF receipt for payment"""
        try:
            # Get payment details from database
            session = db.get_session()
            payment = session.query(Payment).filter(Payment.payment_id == payment_id).first()

            if not payment:
                logger.error(f"Payment not found: {payment_id}")
                return None

            order = payment.order
            user = payment.user

            # Create output directory if not exists
            if not output_path:
                output_path = f"receipts/receipt_{payment_id}.pdf"

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create PDF document
            doc = SimpleDocTemplate(output_path, pagesize=letter)
            story = []

            # Title
            story.append(Paragraph("PAYMENT RECEIPT", self.title_style))
            story.append(Spacer(1, 20))

            # Company/Bot Info
            company_info = [
                ["Payment Bot Service", ""],
                ["Telegram Payment Processing", ""],
                ["Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
            ]

            company_table = Table(company_info, colWidths=[3 * inch, 3 * inch])
            company_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 12),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ]))
            story.append(company_table)
            story.append(Spacer(1, 20))

            # Customer Information
            story.append(Paragraph("Customer Information", self.styles['Heading2']))
            customer_info = [
                ["Customer ID:", str(user.telegram_id)],
                ["Name:", f"{user.first_name or ''} {user.last_name or ''}".strip()],
                ["Username:", f"@{user.username}" if user.username else "N/A"],
                ["Email:", user.email or "N/A"],
            ]

            customer_table = Table(customer_info, colWidths=[2 * inch, 4 * inch])
            customer_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ]))
            story.append(customer_table)
            story.append(Spacer(1, 20))

            # Payment Details
            story.append(Paragraph("Payment Details", self.styles['Heading2']))
            payment_info = [
                ["Payment ID:", payment.payment_id],
                ["Order ID:", order.order_id],
                ["Amount:", f"${payment.amount:.2f} {payment.currency}"],
                ["Payment Method:", payment.payment_method.title()],
                ["Status:", payment.status.value.title()],
                ["Transaction Date:", payment.created_at.strftime("%Y-%m-%d %H:%M:%S")],
                ["Gateway Transaction ID:", payment.gateway_transaction_id or "N/A"],
            ]

            payment_table = Table(payment_info, colWidths=[2.5 * inch, 3.5 * inch])
            payment_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 2), (1, 2), colors.lightgreen),  # Highlight amount
            ]))
            story.append(payment_table)
            story.append(Spacer(1, 30))

            # Footer
            footer_text = """
            <para align="center">
            <b>Thank you for your payment!</b><br/>
            This is an automatically generated receipt.<br/>
            For support, contact us through the Telegram bot.
            </para>
            """
            story.append(Paragraph(footer_text, self.styles['Normal']))

            # Build PDF
            doc.build(story)
            logger.info(f"Receipt generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Receipt generation error: {e}")
            return None
        finally:
            db.close_session(session)

    def generate_refund_receipt(self, payment_id, refund_amount, refund_reason="Customer Request"):
        """Generate PDF receipt for refund"""
        try:
            session = db.get_session()
            payment = session.query(Payment).filter(Payment.payment_id == payment_id).first()

            if not payment:
                return None

            output_path = f"receipts/refund_{payment_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            doc = SimpleDocTemplate(output_path, pagesize=letter)
            story = []

            # Title
            story.append(Paragraph("REFUND RECEIPT", self.title_style))
            story.append(Spacer(1, 20))

            # Refund Details
            refund_info = [
                ["Original Payment ID:", payment.payment_id],
                ["Original Order ID:", payment.order.order_id],
                ["Original Amount:", f"${payment.amount:.2f} {payment.currency}"],
                ["Refund Amount:", f"${refund_amount:.2f} {payment.currency}"],
                ["Refund Reason:", refund_reason],
                ["Refund Date:", datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
                ["Status:", "Processed"],
            ]

            refund_table = Table(refund_info, colWidths=[2.5 * inch, 3.5 * inch])
            refund_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 3), (1, 3), colors.lightblue),  # Highlight refund amount
            ]))
            story.append(refund_table)

            doc.build(story)
            logger.info(f"Refund receipt generated: {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Refund receipt generation error: {e}")
            return None
        finally:
            db.close_session(session)


class EmailService:
    def __init__(self):
        """Initialize email service"""
        from config.config import Config
        self.smtp_server = getattr(Config, 'SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = getattr(Config, 'SMTP_PORT', 587)
        self.email_user = getattr(Config, 'EMAIL_USER', None)
        self.email_password = getattr(Config, 'EMAIL_PASSWORD', None)
        self.from_email = getattr(Config, 'FROM_EMAIL', self.email_user)

    def send_receipt_email(self, to_email, payment_id, receipt_path, subject=None):
        """Send receipt via email"""
        if not self.email_user or not self.email_password:
            logger.warning("Email credentials not configured")
            return False

        try:
            # Create message
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = to_email
            msg['Subject'] = subject or f"Payment Receipt - {payment_id}"

            # Email body
            body = f"""
            Dear Customer,
            
            Thank you for your payment! Please find your receipt attached.
            
            Payment ID: {payment_id}
            Date: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
            
            If you have any questions, please contact our support team through the Telegram bot.
            
            Best regards,
            Payment Bot Team
            """

            msg.attach(MIMEText(body, 'plain'))

            # Attach receipt PDF
            if receipt_path and os.path.exists(receipt_path):
                with open(receipt_path, "rb") as attachment:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(attachment.read())

                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= receipt_{payment_id}.pdf'
                )
                msg.attach(part)

            # Send email
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.email_user, self.email_password)
            server.send_message(msg)
            server.quit()

            logger.info(f"Receipt emailed to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Email sending error: {e}")
            return False


class RefundService:
    def __init__(self):
        """Initialize refund service"""
        self.receipt_generator = ReceiptGenerator()
        self.email_service = EmailService()

    def process_refund(self, payment_id, refund_amount=None, reason="Customer Request"):
        """Process payment refund"""
        try:
            session = db.get_session()
            payment = session.query(Payment).filter(Payment.payment_id == payment_id).first()

            if not payment:
                return {"success": False, "error": "Payment not found"}

            if payment.status.value != "completed":
                return {"success": False, "error": "Can only refund completed payments"}

            # Default to full refund if amount not specified
            if refund_amount is None:
                refund_amount = payment.amount

            if refund_amount > payment.amount:
                return {"success": False, "error": "Refund amount cannot exceed original payment"}

            # Process refund based on payment method
            if payment.payment_method == "paypal":
                result = self._process_paypal_refund(payment, refund_amount, reason)
            elif payment.payment_method == "stripe":
                result = self._process_stripe_refund(payment, refund_amount, reason)
            else:
                return {"success": False, "error": "Refund not supported for this payment method"}

            if result["success"]:
                # Update payment status
                from src.models.models import PaymentStatus
                payment.status = PaymentStatus.REFUNDED
                payment.gateway_response = f"Refunded: ${refund_amount:.2f} - {reason}"
                session.commit()

                # Update order status
                from src.services.services import OrderService
                from src.models.models import OrderStatus
                OrderService.update_order_status(payment.order.order_id, OrderStatus.CANCELLED)

                # Generate refund receipt
                receipt_path = self.receipt_generator.generate_refund_receipt(
                    payment_id, refund_amount, reason
                )

                # Send email if user has email
                if payment.user.email and receipt_path:
                    self.email_service.send_receipt_email(
                        payment.user.email,
                        payment_id,
                        receipt_path,
                        f"Refund Receipt - {payment_id}"
                    )

                logger.info(f"Refund processed: {payment_id} - ${refund_amount:.2f}")
                return {
                    "success": True,
                    "refund_amount": refund_amount,
                    "receipt_path": receipt_path
                }
            else:
                return result

        except Exception as e:
            session.rollback()
            logger.error(f"Refund processing error: {e}")
            return {"success": False, "error": str(e)}
        finally:
            db.close_session(session)

    def _process_paypal_refund(self, payment, refund_amount, reason):
        """Process PayPal refund"""
        try:
            import paypalrestsdk
            from config.config import Config

            # Configure PayPal
            paypalrestsdk.configure({
                "mode": Config.PAYPAL_MODE,
                "client_id": Config.PAYPAL_CLIENT_ID,
                "client_secret": Config.PAYPAL_CLIENT_SECRET
            })

            # Get the sale from gateway transaction ID
            sale = paypalrestsdk.Sale.find(payment.gateway_transaction_id)

            # Create refund
            refund = sale.refund({
                "amount": {
                    "total": str(refund_amount),
                    "currency": payment.currency
                },
                "description": reason
            })

            if refund.success():
                logger.info(f"PayPal refund successful: {refund.id}")
                return {
                    "success": True,
                    "refund_id": refund.id,
                    "gateway": "paypal"
                }
            else:
                logger.error(f"PayPal refund failed: {refund.error}")
                return {
                    "success": False,
                    "error": f"PayPal refund failed: {refund.error}"
                }

        except Exception as e:
            logger.error(f"PayPal refund error: {e}")
            return {"success": False, "error": str(e)}

    def _process_stripe_refund(self, payment, refund_amount, reason):
        """Process Stripe refund"""
        try:
            import stripe
            from config.config import Config

            stripe.api_key = Config.STRIPE_SECRET_KEY

            # Create refund
            refund = stripe.Refund.create(
                payment_intent=payment.gateway_transaction_id,
                amount=int(refund_amount * 100),  # Convert to cents
                reason='requested_by_customer',
                metadata={
                    'reason': reason,
                    'payment_id': payment.payment_id
                }
            )

            logger.info(f"Stripe refund successful: {refund.id}")
            return {
                "success": True,
                "refund_id": refund.id,
                "gateway": "stripe"
            }

        except stripe.error.StripeError as e:
            logger.error(f"Stripe refund failed: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Stripe refund error: {e}")
            return {"success": False, "error": str(e)}


# Global instances
receipt_generator = ReceiptGenerator()
email_service = EmailService()
refund_service = RefundService()
