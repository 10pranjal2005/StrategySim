
import os
from pathlib import Path

from dotenv import load_dotenv


# ---------------------------------------------------------
# PROJECT ROOT DIRECTORY
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from the project root .env file.
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------
# APPLICATION CONFIGURATION
# ---------------------------------------------------------

class Config:
    """
    Base configuration for the StrategySim application.
    """

    # Application identity
    APP_NAME = "StrategySim"
    APP_VERSION = "1.0.0"

    # Flask security configuration
    SECRET_KEY = os.getenv("SECRET_KEY")

    # Database configuration
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        "instance/strategysim.db"
    )

    # Session configuration
    SESSION_COOKIE_HTTPONLY = (
        os.getenv("SESSION_COOKIE_HTTPONLY", "True").lower() == "true"
    )

    SESSION_COOKIE_SAMESITE = os.getenv(
        "SESSION_COOKIE_SAMESITE",
        "Lax"
    )

    SESSION_COOKIE_SECURE = (
        os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"
    )

    PERMANENT_SESSION_LIFETIME = 1800

    # CSRF protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = 3600

    # Upload configuration
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024

    # Development settings
    DEBUG = False
    TESTING = False


# ---------------------------------------------------------
# DEVELOPMENT CONFIGURATION
# ---------------------------------------------------------

class DevelopmentConfig(Config):
    """
    Configuration used during local development.
    """

    DEBUG = os.getenv("FLASK_DEBUG", "False").lower() == "true"


# ---------------------------------------------------------
# TESTING CONFIGURATION
# ---------------------------------------------------------

class TestingConfig(Config):
    """
    Configuration used during automated tests.
    """

    TESTING = True
    WTF_CSRF_ENABLED = False
    SECRET_KEY = "strategysim-testing-secret-key"


# ---------------------------------------------------------
# PRODUCTION CONFIGURATION
# ---------------------------------------------------------

class ProductionConfig(Config):
    """
    Configuration used when deploying StrategySim.
    """

    DEBUG = False
    SESSION_COOKIE_SECURE = True


# ---------------------------------------------------------
# CONFIGURATION REGISTRY
# ---------------------------------------------------------

configurations = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig
}
