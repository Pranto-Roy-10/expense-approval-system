import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///expenses.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 30 * 1024 * 1024  # whole form, several receipts of up to 5 MB each
    SEED_SAMPLE_DATA = True
    # Browsers keep CSS/JS for a year; every static URL carries ?v=<file mtime>, so edits still show at once.
    SEND_FILE_MAX_AGE_DEFAULT = 31536000


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SEED_SAMPLE_DATA = False
