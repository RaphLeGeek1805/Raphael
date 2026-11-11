"""
Notification service — stubs for SMS (Twilio-ready) and email (SMTP).
All sends are logged; actual delivery requires real credentials in config.
"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str) -> dict:
    """
    Send an SMS via Twilio.
    If Twilio credentials are not configured, logs and returns a stub response.
    """
    account_sid = current_app.config.get("TWILIO_ACCOUNT_SID", "")
    auth_token = current_app.config.get("TWILIO_AUTH_TOKEN", "")
    from_number = current_app.config.get("TWILIO_PHONE_FROM", "")

    if not account_sid or not auth_token:
        logger.info(f"[SMS STUB] To: {phone} | Message: {message}")
        return {"status": "stub", "to": phone, "message": message}

    try:
        # Twilio integration (uncomment when credentials are available)
        # from twilio.rest import Client
        # client = Client(account_sid, auth_token)
        # msg = client.messages.create(to=phone, from_=from_number, body=message)
        # logger.info(f"[SMS SENT] SID={msg.sid} To={phone}")
        # return {"status": "sent", "sid": msg.sid, "to": phone}

        logger.info(f"[SMS STUB — credentials present but Twilio not imported] To: {phone}")
        return {"status": "stub", "to": phone, "message": message}

    except Exception as exc:
        logger.error(f"[SMS ERROR] To: {phone} | Error: {exc}")
        return {"status": "error", "to": phone, "error": str(exc)}


def send_email(to: str, subject: str, body: str, html_body: str = None) -> dict:
    """
    Send an email via SMTP.
    If SMTP credentials are not configured, logs and returns a stub response.
    """
    smtp_host = current_app.config.get("SMTP_HOST", "")
    smtp_port = current_app.config.get("SMTP_PORT", 587)
    smtp_user = current_app.config.get("SMTP_USER", "")
    smtp_password = current_app.config.get("SMTP_PASSWORD", "")
    email_from = current_app.config.get("EMAIL_FROM", "noreply@acceskey.fr")

    if not smtp_user or not smtp_password:
        logger.info(f"[EMAIL STUB] To: {to} | Subject: {subject} | Body: {body[:100]}...")
        return {"status": "stub", "to": to, "subject": subject}

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = email_from
        msg["To"] = to

        msg.attach(MIMEText(body, "plain", "utf-8"))
        if html_body:
            msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(email_from, [to], msg.as_string())

        logger.info(f"[EMAIL SENT] To: {to} | Subject: {subject}")
        return {"status": "sent", "to": to, "subject": subject}

    except Exception as exc:
        logger.error(f"[EMAIL ERROR] To: {to} | Error: {exc}")
        return {"status": "error", "to": to, "error": str(exc)}


def send_access_code(guest_name: str, guest_phone: str = None, guest_email: str = None,
                     code: str = "", valid_from=None, valid_until=None,
                     property_name: str = "") -> dict:
    """
    High-level helper: send the access code to the guest via SMS and/or email.
    """
    from_str = valid_from.strftime("%d/%m/%Y %H:%M") if valid_from else "N/A"
    until_str = valid_until.strftime("%d/%m/%Y %H:%M") if valid_until else "N/A"

    sms_message = (
        f"Bonjour {guest_name},\n"
        f"Votre code d'accès pour {property_name} : {code}\n"
        f"Valide du {from_str} au {until_str}.\n"
        f"Bonne arrivée ! — ACCESKEY"
    )
    email_subject = f"Votre code d'accès — {property_name}"
    email_body = (
        f"Bonjour {guest_name},\n\n"
        f"Voici votre code d'accès pour {property_name} :\n\n"
        f"    CODE : {code}\n\n"
        f"Validité : du {from_str} au {until_str}.\n\n"
        f"En cas de problème, contactez votre hôte.\n\n"
        f"Bonne arrivée,\nL'équipe ACCESKEY"
    )

    results = {}
    if guest_phone:
        results["sms"] = send_sms(guest_phone, sms_message)
    if guest_email:
        results["email"] = send_email(guest_email, email_subject, email_body)

    if not guest_phone and not guest_email:
        logger.warning(f"[NOTIFICATION] No contact info for guest {guest_name}")
        results["warning"] = "No contact info provided"

    return results
