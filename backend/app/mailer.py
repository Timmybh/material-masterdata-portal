import smtplib
from email.message import EmailMessage
from .config import get_settings

settings = get_settings()


def send_email(to: str, subject: str, body: str):
    if not settings.email_notifications_enabled:
        return False
    if not settings.smtp_host:
        print(f"[EMAIL MOCK] to={to} subject={subject}\n{body}")
        return False
    msg = EmailMessage()
    msg["From"] = settings.smtp_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
        if settings.smtp_starttls:
            s.starttls()
        if settings.smtp_user:
            s.login(settings.smtp_user, settings.smtp_password)
        s.send_message(msg)
    return True
