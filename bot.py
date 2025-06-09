from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from config.config import Config
from config.database import db
from src.services.services import UserService, OrderService, PaymentService, SupportService, FAQService
from src.models.models import OrderStatus
from src.security.security import rate_limit, validate_input, log_user_action, security_validator
import logging

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, Config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self):
        self.application = None

    @log_user_action("start")
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user

        # Create or get user in database
        db_user = UserService.get_or_create_user(
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name
        )

        welcome_message = f"""
🤖 Welcome to Payment Bot, {user.first_name}!

I can help you with:
💳 Making payments
📦 Tracking orders
🎧 Customer support

Use /help to see all available commands.
        """

        keyboard = [
            [InlineKeyboardButton("💳 Make Payment", callback_data="make_payment")],
            [InlineKeyboardButton("📦 Track Order", callback_data="track_order")],
            [InlineKeyboardButton("🎧 Get Support", callback_data="get_support")],
            [InlineKeyboardButton("📋 Order History", callback_data="order_history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_message, reply_markup=reply_markup)

    @log_user_action("help")
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
🤖 **Payment Bot Commands:**

/start - Start the bot and see main menu
/help - Show this help message
/pay <amount> - Make a payment
/track <order_id> - Track an order
/support - Create support ticket
/history - View order history
/receipt <payment_id> - Generate payment receipt
/profile [email] - View or update your email address
/faq - View frequently asked questions

**Payment Methods Supported:**
💳 Credit/Debit Cards
🌐 PayPal
📱 Mobile Money
₿ Cryptocurrency

**Need Help?**
Use /support to contact our customer service team.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    @rate_limit('payment')
    @validate_input(security_validator.validate_payment_amount, "Invalid payment amount")
    @log_user_action("payment_initiation")
    async def pay_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pay command"""
        if not context.args:
            await update.message.reply_text("Please specify amount: /pay <amount>")
            return

        try:
            amount = float(context.args[0])
            if amount < Config.MIN_PAYMENT_AMOUNT or amount > Config.MAX_PAYMENT_AMOUNT:
                await update.message.reply_text(
                    f"Amount must be between ${Config.MIN_PAYMENT_AMOUNT} and ${Config.MAX_PAYMENT_AMOUNT}"
                )
                return

            # Get user
            user = update.effective_user
            db_user = UserService.get_or_create_user(telegram_id=user.id)

            # Create order
            order = OrderService.create_order(
                user_id=db_user.id,
                amount=amount,
                description=f"Payment via Telegram Bot"
            )

            # Show payment options
            keyboard = [
                [InlineKeyboardButton("💳 Card Payment", callback_data=f"pay_card_{order.order_id}")],
                [InlineKeyboardButton("🌐 PayPal", callback_data=f"pay_paypal_{order.order_id}")],
                [InlineKeyboardButton("📱 Mobile Money", callback_data=f"pay_mobile_{order.order_id}")],
                [InlineKeyboardButton("₿ Cryptocurrency", callback_data=f"pay_crypto_{order.order_id}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"💰 Payment Request Created\n\n"
                f"Order ID: `{order.order_id}`\n"
                f"Amount: ${amount:.2f}\n\n"
                f"Choose your payment method:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )

        except ValueError:
            await update.message.reply_text("Invalid amount. Please enter a valid number.")
        except Exception as e:
            logger.error(f"Error in pay command: {e}")
            await update.message.reply_text("Sorry, there was an error processing your request.")

    @validate_input(security_validator.validate_order_id, "Invalid order ID format")
    @log_user_action("order_tracking")
    async def track_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /track command"""
        if not context.args:
            await update.message.reply_text("Please specify order ID: /track <order_id>")
            return

        order_id = security_validator.sanitize_input(context.args[0])
        order = OrderService.get_order_by_id(order_id)

        if not order:
            await update.message.reply_text("Order not found. Please check your order ID.")
            return

        status_emoji = {
            OrderStatus.PENDING_PAYMENT: "⏳",
            OrderStatus.PAYMENT_CONFIRMED: "✅",
            OrderStatus.PROCESSING: "🔄",
            OrderStatus.SHIPPED: "🚚",
            OrderStatus.DELIVERED: "📦",
            OrderStatus.CANCELLED: "❌"
        }

        await update.message.reply_text(
            f"📦 **Order Tracking**\n\n"
            f"Order ID: `{order.order_id}`\n"
            f"Status: {status_emoji.get(order.status, '❓')} {order.status.value.replace('_', ' ').title()}\n"
            f"Amount: ${order.amount:.2f}\n"
            f"Created: {order.created_at.strftime('%Y-%m-%d %H:%M')}\n"
            f"Updated: {order.updated_at.strftime('%Y-%m-%d %H:%M')}",
            parse_mode='Markdown'
        )

    @rate_limit('support')
    @log_user_action("support_request")
    async def support_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /support command"""
        user = update.effective_user
        db_user = UserService.get_or_create_user(telegram_id=user.id)

        keyboard = [
            [InlineKeyboardButton("🐛 Report Bug", callback_data="support_bug")],
            [InlineKeyboardButton("💰 Payment Issue", callback_data="support_payment")],
            [InlineKeyboardButton("📦 Order Issue", callback_data="support_order")],
            [InlineKeyboardButton("❓ General Question", callback_data="support_general")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "🎧 **Customer Support**\n\n"
            "How can we help you today?",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    @log_user_action("order_history")
    async def history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /history command"""
        user = update.effective_user
        db_user = UserService.get_or_create_user(telegram_id=user.id)

        orders = OrderService.get_user_orders(db_user.id, limit=5)

        if not orders:
            await update.message.reply_text("No orders found.")
            return

        history_text = "📋 **Your Order History**\n\n"

        status_emoji = {
            OrderStatus.PENDING_PAYMENT: "⏳",
            OrderStatus.PAYMENT_CONFIRMED: "✅",
            OrderStatus.PROCESSING: "🔄",
            OrderStatus.SHIPPED: "🚚",
            OrderStatus.DELIVERED: "📦",
            OrderStatus.CANCELLED: "❌"
        }

        for order in orders:
            history_text += (
                f"Order: `{order.order_id}`\n"
                f"Status: {status_emoji.get(order.status, '❓')} {order.status.value.replace('_', ' ').title()}\n"
                f"Amount: ${order.amount:.2f}\n"
                f"Date: {order.created_at.strftime('%Y-%m-%d')}\n\n"
            )

        await update.message.reply_text(history_text, parse_mode='Markdown')

    @log_user_action("receipt_request")
    async def receipt_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /receipt command"""
        if not context.args:
            await update.message.reply_text("Please specify payment ID: /receipt <payment_id>")
            return

        payment_id = security_validator.sanitize_input(context.args[0])
        user = update.effective_user

        try:
            # Generate and send receipt
            from src.gateways.payment_gateways import payment_gateway
            from src.models.models import Payment
            from config.database import db

            # Verify user owns this payment
            session = db.get_session()
            payment = session.query(Payment).filter(
                Payment.payment_id == payment_id
            ).first()

            if not payment:
                await update.message.reply_text("❌ Payment not found.")
                return

            if payment.user.telegram_id != user.id:
                await update.message.reply_text("❌ You can only request receipts for your own payments.")
                return

            # Generate receipt
            result = payment_gateway.generate_and_send_receipt(
                payment_id,
                payment.user.email if payment.user.email else None
            )

            if result["success"]:
                message = f"✅ Receipt generated successfully!\n\n"
                message += f"Payment ID: `{payment_id}`\n"
                message += f"Receipt saved to: {result['receipt_path']}\n"

                if result.get("email_sent"):
                    message += f"📧 Receipt also sent to your email address."
                elif payment.user.email:
                    message += f"⚠️ Email sending failed, but receipt file is available."
                else:
                    message += f"💡 Add an email to your profile to receive receipts via email."

                await update.message.reply_text(message, parse_mode='Markdown')
            else:
                await update.message.reply_text(f"❌ Failed to generate receipt: {result.get('error', 'Unknown error')}")

        except Exception as e:
            logger.error(f"Error in receipt command: {e}")
            await update.message.reply_text("Sorry, there was an error generating your receipt.")
        finally:
            if 'session' in locals():
                db.close_session(session)

    @log_user_action("profile_update")
    async def profile_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /profile command to update user email"""
        user = update.effective_user
        db_user = UserService.get_or_create_user(telegram_id=user.id)

        if not context.args:
            # Show current profile
            profile_text = f"👤 **Your Profile**\n\n"
            profile_text += f"Name: {user.first_name or ''} {user.last_name or ''}".strip() + "\n"
            profile_text += f"Username: @{user.username}\n" if user.username else ""
            profile_text += f"Email: {db_user.email or 'Not set'}\n\n"
            profile_text += f"To update your email: /profile <email>\n"
            profile_text += f"Example: /profile user@example.com"

            await update.message.reply_text(profile_text, parse_mode='Markdown')
            return

        # Update email
        email = security_validator.sanitize_input(context.args[0])

        # Basic email validation
        import re
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            await update.message.reply_text("❌ Please provide a valid email address.")
            return

        # Update user email
        UserService.update_user_email(db_user.id, email)

        await update.message.reply_text(
            f"✅ Email updated successfully!\n\n"
            f"Email: {email}\n\n"
            f"You will now receive payment receipts via email.",
            parse_mode='Markdown'
        )

    @log_user_action("faq_access")
    async def faq_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /faq command"""
        if not context.args:
            # Show FAQ categories
            categories = FAQService.get_all_categories()
            if not categories:
                await update.message.reply_text(
                    "❓ **Frequently Asked Questions**\n\n"
                    "No FAQs available at the moment. Please contact support if you need help."
                )
                return

            keyboard = []
            for category in categories:
                display_name = category.replace('_', ' ').title()
                keyboard.append([InlineKeyboardButton(f"📋 {display_name}", callback_data=f"faq_cat_{category}")])

            keyboard.append([InlineKeyboardButton("🔍 Search FAQs", callback_data="faq_search")])
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "❓ **Frequently Asked Questions**\n\n"
                "Choose a category or search for specific topics:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
        else:
            # Search FAQs
            query = " ".join(context.args)
            faqs = FAQService.search_faqs(query, limit=5)

            if not faqs:
                await update.message.reply_text(
                    f"🔍 No FAQs found for: '{query}'\n\n"
                    f"Try different keywords or contact support: /support"
                )
                return

            response = f"🔍 **Search Results for '{query}'**\n\n"
            for i, faq in enumerate(faqs, 1):
                response += f"**{i}. {faq.question}**\n"
                response += f"{faq.answer}\n\n"
                if len(response) > 3500:  # Telegram message limit
                    break

            response += f"💡 Use /faq to browse categories or /support for more help."
            await update.message.reply_text(response, parse_mode='Markdown')

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()

        data = query.data

        if data == "make_payment":
            await query.edit_message_text("Please use command: /pay <amount>\nExample: /pay 50")
        elif data == "track_order":
            await query.edit_message_text("Please use command: /track <order_id>\nExample: /track ORD-20231201-abc123")
        elif data == "get_support":
            await query.edit_message_text("Please use command: /support")
        elif data == "order_history":
            await query.edit_message_text("Please use command: /history")
        elif data.startswith("pay_"):
            await self.handle_payment_selection(query, data)
        elif data.startswith("support_"):
            await self.handle_support_selection(query, data)
        elif data.startswith("faq_"):
            await self.handle_faq_selection(query, data)

    async def handle_faq_selection(self, query, data):
        """Handle FAQ category selection"""
        if data.startswith("faq_cat_"):
            # Show FAQs for specific category
            category = data.replace("faq_cat_", "")
            faqs = FAQService.get_faqs_by_category(category, limit=10)

            if not faqs:
                await query.edit_message_text(
                    f"No FAQs found in category: {category.replace('_', ' ').title()}"
                )
                return

            response = f"📋 **{category.replace('_', ' ').title()} FAQs**\n\n"
            for i, faq in enumerate(faqs, 1):
                response += f"**{i}. {faq.question}**\n"
                response += f"{faq.answer}\n\n"
                if len(response) > 3500:  # Telegram message limit
                    response += "... (more FAQs available)\n\n"
                    break

            response += "💡 Use /faq <search term> to search or /support for personalized help."
            await query.edit_message_text(response, parse_mode='Markdown')

        elif data == "faq_search":
            await query.edit_message_text(
                "🔍 **Search FAQs**\n\n"
                "Use: /faq <your question>\n"
                "Example: /faq how to pay\n\n"
                "Or browse categories with /faq"
            )

    async def handle_payment_selection(self, query, data):
        """Handle payment method selection"""
        parts = data.split("_")
        method = parts[1]
        order_id = security_validator.sanitize_input(parts[2])

        # Get order details
        order = OrderService.get_order_by_id(order_id)
        if not order:
            await query.edit_message_text("❌ Order not found. Please try again.")
            return

        method_names = {
            "card": "💳 Card Payment",
            "paypal": "🌐 PayPal",
            "mobile": "📱 Mobile Money",
            "crypto": "₿ Cryptocurrency"
        }

        await query.edit_message_text(
            f"🔄 Processing {method_names.get(method, method)}...\n\n"
            f"Order ID: `{order_id}`\n"
            f"Amount: ${order.amount:.2f}\n\n"
            f"Please wait...",
            parse_mode='Markdown'
        )

        if method in ["card", "paypal"]:
            # Process payment through gateway
            from src.gateways.payment_gateways import payment_gateway

            gateway_method = "stripe" if method == "card" else "paypal"
            result = payment_gateway.process_payment(
                payment_method=gateway_method,
                order_id=order_id,
                amount=order.amount,
                currency="USD"
            )

            if result["success"]:
                if gateway_method == "paypal":
                    # PayPal requires user to complete payment on PayPal website
                    keyboard = [[InlineKeyboardButton("💰 Complete Payment", url=result["approval_url"])]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    await query.edit_message_text(
                        f"✅ Payment Created Successfully!\n\n"
                        f"Order ID: `{order_id}`\n"
                        f"Amount: ${order.amount:.2f}\n"
                        f"Payment ID: `{result['payment_id']}`\n\n"
                        f"Click the button below to complete your PayPal payment:",
                        reply_markup=reply_markup,
                        parse_mode='Markdown'
                    )

                elif gateway_method == "stripe":
                    # For Stripe, we'll provide instructions (in real implementation, you'd integrate with Stripe Elements)
                    await query.edit_message_text(
                        f"💳 Card Payment Ready\n\n"
                        f"Order ID: `{order_id}`\n"
                        f"Amount: ${order.amount:.2f}\n"
                        f"Payment ID: `{result['payment_id']}`\n\n"
                        f"⚠️ In a production environment, this would show a secure card payment form.\n"
                        f"For demo purposes, payment processing is simulated.\n\n"
                        f"Your payment is being processed...",
                        parse_mode='Markdown'
                    )

                    # Simulate successful payment after a delay (for demo)
                    import asyncio
                    await asyncio.sleep(2)

                    # Update order status to simulate successful payment
                    from src.models.models import OrderStatus
                    OrderService.update_order_status(order_id, OrderStatus.PAYMENT_CONFIRMED)

                    await query.edit_message_text(
                        f"✅ Payment Successful!\n\n"
                        f"Order ID: `{order_id}`\n"
                        f"Amount: ${order.amount:.2f}\n"
                        f"Payment ID: `{result['payment_id']}`\n"
                        f"Status: Payment Confirmed\n\n"
                        f"Thank you for your payment! Your order is now being processed.",
                        parse_mode='Markdown'
                    )
            else:
                await query.edit_message_text(
                    f"❌ Payment Processing Failed\n\n"
                    f"Order ID: `{order_id}`\n"
                    f"Error: {result.get('error', 'Unknown error')}\n\n"
                    f"Please try again or contact support."
                )
        else:
            # For mobile money and crypto payments
            if method == "mobile":
                # Show mobile money provider options
                keyboard = [
                    [InlineKeyboardButton("📱 M-Pesa", callback_data=f"pay_mobile_mpesa_{order_id}")],
                    [InlineKeyboardButton("📱 MTN Mobile Money", callback_data=f"pay_mobile_mtn_{order_id}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"pay_back_{order_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"📱 **Mobile Money Payment**\n\n"
                    f"Order ID: `{order_id}`\n"
                    f"Amount: ${order.amount:.2f}\n\n"
                    f"Choose your mobile money provider:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

            elif method == "crypto":
                # Show crypto provider options
                keyboard = [
                    [InlineKeyboardButton("₿ BitPay", callback_data=f"pay_crypto_bitpay_{order_id}")],
                    [InlineKeyboardButton("🪙 CoinGate", callback_data=f"pay_crypto_coingate_{order_id}")],
                    [InlineKeyboardButton("🔙 Back", callback_data=f"pay_back_{order_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"₿ **Cryptocurrency Payment**\n\n"
                    f"Order ID: `{order_id}`\n"
                    f"Amount: ${order.amount:.2f}\n\n"
                    f"Choose your crypto payment provider:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

            elif data.startswith("pay_mobile_"):
                # Handle specific mobile money provider
                provider = parts[2]  # mpesa or mtn
                await self.handle_mobile_money_payment(query, order_id, provider, order.amount)

            elif data.startswith("pay_crypto_"):
                # Handle specific crypto provider
                provider = parts[2]  # bitpay or coingate
                await self.handle_crypto_payment(query, order_id, provider, order.amount)

            elif data.startswith("pay_back_"):
                # Go back to payment method selection
                keyboard = [
                    [InlineKeyboardButton("💳 Card Payment", callback_data=f"pay_card_{order_id}")],
                    [InlineKeyboardButton("🌐 PayPal", callback_data=f"pay_paypal_{order_id}")],
                    [InlineKeyboardButton("📱 Mobile Money", callback_data=f"pay_mobile_{order_id}")],
                    [InlineKeyboardButton("₿ Cryptocurrency", callback_data=f"pay_crypto_{order_id}")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    f"💰 Payment Request\n\n"
                    f"Order ID: `{order_id}`\n"
                    f"Amount: ${order.amount:.2f}\n\n"
                    f"Choose your payment method:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )

    async def handle_mobile_money_payment(self, query, order_id, provider, amount):
        """Handle mobile money payment processing"""
        await query.edit_message_text(
            f"📱 **{provider.upper()} Payment**\n\n"
            f"Order ID: `{order_id}`\n"
            f"Amount: ${amount:.2f}\n\n"
            f"Please provide your phone number for {provider.upper()} payment.\n"
            f"Format: +254XXXXXXXXX (for M-Pesa) or +256XXXXXXXXX (for MTN)\n\n"
            f"Reply with your phone number to continue.\n"
            f"Example: +254712345678",
            parse_mode='Markdown'
        )

        # Store the payment context for the user
        user_id = query.from_user.id
        context_key = f"mobile_payment_{user_id}"

        # In a real implementation, you'd store this in Redis or similar
        # For now, we'll simulate the process
        await query.edit_message_text(
            f"📱 **{provider.upper()} Payment Processing**\n\n"
            f"Order ID: `{order_id}`\n"
            f"Amount: ${amount:.2f}\n\n"
            f"⚠️ Demo Mode: Mobile money integration requires:\n"
            f"• {provider.upper()} API credentials\n"
            f"• Phone number validation\n"
            f"• Real-time payment processing\n\n"
            f"In production, you would:\n"
            f"1. Enter your phone number\n"
            f"2. Receive payment prompt on your phone\n"
            f"3. Enter your {provider.upper()} PIN\n"
            f"4. Payment confirmed automatically\n\n"
            f"Contact support for manual payment processing.",
            parse_mode='Markdown'
        )

    async def handle_crypto_payment(self, query, order_id, provider, amount):
        """Handle cryptocurrency payment processing"""
        await query.edit_message_text(
            f"₿ **{provider.title()} Crypto Payment**\n\n"
            f"Order ID: `{order_id}`\n"
            f"Amount: ${amount:.2f} USD\n\n"
            f"🔄 Creating crypto payment invoice...",
            parse_mode='Markdown'
        )

        try:
            # Process crypto payment
            from src.gateways.payment_gateways import payment_gateway

            result = payment_gateway.process_payment(
                payment_method=f"crypto_{provider}",
                order_id=order_id,
                amount=amount,
                currency="USD",
                user_data={"email": None}  # Would get from user profile in real implementation
            )

            if result["success"]:
                keyboard = [[InlineKeyboardButton("🪙 Pay with Crypto", url=result["payment_url"])]]
                reply_markup = InlineKeyboardMarkup(keyboard)

                supported_cryptos = ", ".join(result.get("supported_currencies", ["BTC", "ETH", "LTC"]))

                await query.edit_message_text(
                    f"₿ **Crypto Payment Ready**\n\n"
                    f"Order ID: `{order_id}`\n"
                    f"Amount: ${amount:.2f} USD\n"
                    f"Payment ID: `{result['payment_id']}`\n"
                    f"Provider: {provider.title()}\n\n"
                    f"Supported Cryptocurrencies:\n{supported_cryptos}\n\n"
                    f"Click the button below to complete your crypto payment:",
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await query.edit_message_text(
                    f"❌ **Crypto Payment Failed**\n\n"
                    f"Order ID: `{order_id}`\n"
                    f"Provider: {provider.title()}\n"
                    f"Error: {result.get('error', 'Unknown error')}\n\n"
                    f"Please try again or contact support.\n\n"
                    f"⚠️ Note: This requires {provider.title()} API configuration."
                )

        except Exception as e:
            logger.error(f"Crypto payment error: {e}")
            await query.edit_message_text(
                f"❌ **Crypto Payment Error**\n\n"
                f"Order ID: `{order_id}`\n"
                f"Provider: {provider.title()}\n\n"
                f"⚠️ Crypto payment gateway not fully configured.\n"
                f"Please contact support or try another payment method."
            )

    async def handle_support_selection(self, query, data):
        """Handle support category selection"""
        category = security_validator.sanitize_input(data.split("_")[1])
        user = query.from_user
        db_user = UserService.get_or_create_user(telegram_id=user.id)

        category_subjects = {
            "bug": "Bug Report",
            "payment": "Payment Issue",
            "order": "Order Issue",
            "general": "General Question"
        }

        # Create support ticket
        ticket = SupportService.create_ticket(
            user_id=db_user.id,
            subject=category_subjects.get(category, "General Support"),
            description=f"Support request via Telegram bot - Category: {category}"
        )

        await query.edit_message_text(
            f"🎫 **Support Ticket Created**\n\n"
            f"Ticket ID: `{ticket.ticket_id}`\n"
            f"Category: {category_subjects.get(category)}\n"
            f"Status: Open\n\n"
            f"Our support team will contact you soon.\n"
            f"You can reference this ticket ID in future communications.",
            parse_mode='Markdown'
        )

    async def setup_bot(self):
        """Setup bot with handlers"""
        self.application = Application.builder().token(Config.TELEGRAM_BOT_TOKEN).build()

        # Add command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("pay", self.pay_command))
        self.application.add_handler(CommandHandler("track", self.track_command))
        self.application.add_handler(CommandHandler("support", self.support_command))
        self.application.add_handler(CommandHandler("history", self.history_command))
        self.application.add_handler(CommandHandler("receipt", self.receipt_command))
        self.application.add_handler(CommandHandler("profile", self.profile_command))
        self.application.add_handler(CommandHandler("faq", self.faq_command))

        # Add callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))

        logger.info("Bot handlers setup complete")

    async def run_bot(self):
        """Run the bot"""
        await self.setup_bot()
        logger.info("Starting bot...")
        await self.application.run_polling()


# Global bot instance
bot = TelegramBot()
