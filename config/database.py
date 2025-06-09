from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base
from config import Config
import logging

# Configure logging
logging.basicConfig(level=getattr(logging, Config.LOG_LEVEL))
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.engine = None
        self.SessionLocal = None

    def init_db(self):
        """Initialize database connection and create tables"""
        try:
            self.engine = create_engine(Config.DATABASE_URL)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

            # Create all tables
            Base.metadata.create_all(bind=self.engine)
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_session(self):
        """Get database session"""
        if not self.SessionLocal:
            raise Exception("Database not initialized. Call init_db() first.")
        return self.SessionLocal()

    def close_session(self, session):
        """Close database session"""
        if session:
            session.close()


# Global database instance
db = Database()
