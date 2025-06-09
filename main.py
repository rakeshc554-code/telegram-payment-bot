import asyncio
import logging
import sys
import threading
import uvicorn
from config.config import Config
from config.database import db
from bot import bot
from webhook_server import app
from src.services.services import FAQService

logger = logging.getLogger(__name__)


def run_webhook_server():
    """Run the webhook server in a separate thread"""
    try:
        uvicorn.run(
            app,
            host="0.0.0.0",
            port=8000,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Webhook server error: {e}")


async def initialize_application():
    """Initialize the application"""
    try:
        # Validate configuration
        Config.validate_config()
        logger.info("Configuration validated successfully")

        # Initialize database
        db.create_tables()
        logger.info("Database tables created/verified")

        # Initialize default FAQs
        FAQService.initialize_default_faqs()
        logger.info("FAQ system initialized")

        logger.info("Application initialization complete")

    except Exception as e:
        logger.error(f"Application initialization failed: {e}")
        raise


async def run_bot():
    """Run the Telegram bot"""
    try:
        await bot.run_bot()
    except Exception as e:
        logger.error(f"Bot error: {e}")


async def main():
    """Main application entry point"""
    try:
        # Configure logging
        logging.basicConfig(
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            level=logging.INFO
        )

        logger.info("Starting Telegram Payment Bot...")

        # Initialize application components
        await initialize_application()

        # Start webhook server in background thread
        webhook_thread = threading.Thread(target=run_webhook_server, daemon=True)
        webhook_thread.start()
        logger.info("Webhook server started on port 8000")

        # Wait a moment for webhook server to start
        await asyncio.sleep(2)

        # Run the bot (this will block)
        await run_bot()

    except Exception as e:
        logger.error(f"Application startup failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    print("🤖 Starting Telegram Payment Bot...")
    print("📋 Checking configuration...")
    print("🗄️  Initializing database...")
    print("🌐 Starting webhook server...")
    print("🚀 Starting bot...")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Bot stopped by user")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
