import os

class Config:
    # ── Flask settings ─────────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    MONGO_URI  = os.getenv("MONGO_URI", "mongodb://localhost:27017/yourdb")

    # ── Mail (SMTP) settings ───────────────────────────────────
    MAIL_SERVER         = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    MAIL_PORT           = int(os.getenv("SMTP_PORT", 587))
    MAIL_USE_TLS        = os.getenv("SMTP_USE_TLS", "true").lower() in ("true","1","yes")
    MAIL_USERNAME       = os.getenv("SMTP_USERNAME")
    MAIL_PASSWORD       = os.getenv("SMTP_PASSWORD")
    MAIL_DEFAULT_SENDER     = os.getenv("MAIL_DEFAULT_SENDER", "cityfix101@gmail.com")
    MAIL_DEFAULT_SENDER_NAME = os.getenv("MAIL_DEFAULT_SENDER_NAME", "City Fix Team")
