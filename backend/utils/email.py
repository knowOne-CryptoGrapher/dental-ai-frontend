"""
DEPRECATED — this module has been retired.

All email sending now goes through EmailService in backend/services/email_service.py.
Import and call: from services.email_service import email_service
"""


def send_invite_email(*args, **kwargs):
    raise NotImplementedError(
        "send_invite_email() is retired. "
        "Use EmailService.send() from services/email_service.py instead."
    )
