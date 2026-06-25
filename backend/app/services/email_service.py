from email.message import EmailMessage
import smtplib
from typing import Iterable, Sequence

from ..config import settings


class EmailNotConfiguredError(RuntimeError):
    """Raised when SMTP settings required for notification mail are missing."""


def _normalize_recipients(recipients: Iterable[str] | str | None) -> list[str]:
    if not recipients:
        return []
    if isinstance(recipients, str):
        recipients = recipients.split(",")
    return [email.strip() for email in recipients if email and email.strip()]


def is_email_enabled() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)


def send_email(
    recipients: Sequence[str] | str,
    subject: str,
    body: str,
    *,
    cc: Sequence[str] | str | None = None,
) -> bool:
    to_emails = _normalize_recipients(recipients)
    cc_emails = _normalize_recipients(cc)
    if not to_emails:
        return False
    if not is_email_enabled():
        raise EmailNotConfiguredError("SMTP settings are not configured.")

    sender = settings.SMTP_FROM_EMAIL or settings.SMTP_USERNAME
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.SMTP_FROM_NAME} <{sender}>"
    message["To"] = ", ".join(to_emails)
    if cc_emails:
        message["Cc"] = ", ".join(cc_emails)
    message.set_content(body)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
        if settings.SMTP_USE_TLS:
            smtp.starttls()
        smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        smtp.send_message(message, from_addr=sender, to_addrs=to_emails + cc_emails)
    return True


def send_notification(
    recipients: Sequence[str] | str,
    subject: str,
    body: str,
    *,
    include_admins: bool = False,
) -> bool:
    cc = settings.admin_emails if include_admins else None
    return send_email(recipients, subject, body, cc=cc)
