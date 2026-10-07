import os
from pathlib import Path

from sqlalchemy.engine import URL, make_url


BASE_DIR = Path(__file__).resolve().parent


def _database_settings():
    """Build a SQLAlchemy URL and engine options for SQLite, TiDB, or MySQL."""
    raw_url = (os.environ.get("DATABASE_URL") or os.environ.get("TIDB_URL") or "").strip()
    if raw_url:
        url = make_url(raw_url)
        if url.drivername in {"mysql", "mysql+mysqldb"}:
            url = url.set(drivername="mysql+pymysql")
    elif os.environ.get("TIDB_HOST") or os.environ.get("MYSQL_HOST"):
        url = URL.create(
            "mysql+pymysql",
            username=os.environ.get("TIDB_USER") or os.environ.get("MYSQL_USER"),
            password=os.environ.get("TIDB_PASSWORD") or os.environ.get("MYSQL_PASSWORD"),
            host=os.environ.get("TIDB_HOST") or os.environ.get("MYSQL_HOST"),
            port=int(os.environ.get("TIDB_PORT") or os.environ.get("MYSQL_PORT", "4000")),
            database=os.environ.get("TIDB_DATABASE") or os.environ.get("MYSQL_DB"),
        )
    else:
        url = make_url(f"sqlite:///{BASE_DIR / 'instance' / 'lost_found.db'}")

    pool_options = {
        # Avoid an extra network round trip on every request when using a warm DB pool.
        # Enable DATABASE_POOL_PRE_PING=1 only if the database/network drops idle connections.
        "pool_pre_ping": os.environ.get("DATABASE_POOL_PRE_PING", "0") == "1",
        "pool_recycle": int(os.environ.get("DATABASE_POOL_RECYCLE", "1800")),
    }
    if url.drivername.startswith("mysql"):
        pool_options.update({
            "pool_size": int(os.environ.get("DATABASE_POOL_SIZE", "5")),
            "max_overflow": int(os.environ.get("DATABASE_MAX_OVERFLOW", "2")),
            "pool_timeout": int(os.environ.get("DATABASE_POOL_TIMEOUT", "30")),
            "connect_args": {
                "connect_timeout": int(os.environ.get("DATABASE_CONNECT_TIMEOUT", "10")),
                "ssl_verify_cert": True,
                "ssl_verify_identity": True,
                **({"ssl_ca": os.environ["TIDB_SSL_CA"]} if os.environ.get("TIDB_SSL_CA") else {}),
            },
        })

    return url, pool_options


DATABASE_URL, SQLALCHEMY_ENGINE_OPTIONS = _database_settings()


class Config:
    DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_ENGINE_OPTIONS = SQLALCHEMY_ENGINE_OPTIONS
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024
    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", str(BASE_DIR / "instance" / "uploads"))
    IMAGE_STORAGE_BACKEND = os.environ.get("IMAGE_STORAGE_BACKEND", "local").strip().lower()
    GOOGLE_DRIVE_WEB_APP_URL = os.environ.get("GOOGLE_DRIVE_WEB_APP_URL", "").strip()
    GOOGLE_DRIVE_SHARED_SECRET = os.environ.get("GOOGLE_DRIVE_SHARED_SECRET", "")
    # The matching registered account receives admin access on Render. The
    # account still authenticates with its own normal login password.
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    PUBLIC_BASE_URL = (os.environ.get("PUBLIC_BASE_URL") or os.environ.get("RENDER_EXTERNAL_URL", "")).rstrip("/")
    MAP_TILE_URL = os.environ.get("MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 12
    AUTO_CREATE_DB = True
    RATELIMIT_ENABLED = True
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")
    TRUSTED_HOSTS = None


class DevelopmentConfig(Config):
    DEBUG = True


class TestingConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    AUTO_CREATE_DB = True
    RATELIMIT_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    AUTO_CREATE_DB = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    TRUSTED_HOSTS = [host.strip() for host in os.environ.get("TRUSTED_HOSTS", "").split(",") if host.strip()]
    if not TRUSTED_HOSTS and os.environ.get("RENDER_EXTERNAL_HOSTNAME"):
        TRUSTED_HOSTS = [os.environ["RENDER_EXTERNAL_HOSTNAME"]]

    @classmethod
    def validate(cls):
        if not os.environ.get("SECRET_KEY") or os.environ["SECRET_KEY"] in {"dev-only-change-me", "replace-with-a-random-secret", "changeme", "change-me"}:
            raise RuntimeError("Set a unique SECRET_KEY before running in production.")
        if not cls.TRUSTED_HOSTS:
            raise RuntimeError("Set TRUSTED_HOSTS or deploy on Render with RENDER_EXTERNAL_HOSTNAME configured.")
        if not (os.environ.get("DATABASE_URL") or os.environ.get("TIDB_URL") or os.environ.get("TIDB_HOST") or os.environ.get("MYSQL_HOST")):
            raise RuntimeError("Set DATABASE_URL or the TIDB_HOST/TIDB_USER/TIDB_PASSWORD/TIDB_DATABASE settings.")
        if cls.IMAGE_STORAGE_BACKEND == "google_drive":
            from app.services.google_drive_storage import validate_settings
            if not validate_settings(cls.GOOGLE_DRIVE_WEB_APP_URL, cls.GOOGLE_DRIVE_SHARED_SECRET):
                raise RuntimeError("Set a valid GOOGLE_DRIVE_WEB_APP_URL and a 32+ character GOOGLE_DRIVE_SHARED_SECRET.")
