# reports/email_utils.py

import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from flask import current_app

def send_email(to_email: str, subject: str, body: str):
    msg = EmailMessage()
    msg["Subject"] = subject

    # combine display name + address
    display_name = current_app.config.get("MAIL_DEFAULT_SENDER_NAME")
    sender_addr  = current_app.config["MAIL_DEFAULT_SENDER"]
    msg["From"]  = formataddr((display_name, sender_addr))

    msg["To"]     = to_email
    msg.set_content(body)

    server = smtplib.SMTP(
        current_app.config["MAIL_SERVER"],
        current_app.config["MAIL_PORT"]
    )
    if current_app.config["MAIL_USE_TLS"]:
        server.starttls()
    server.login(
        current_app.config["MAIL_USERNAME"],
        current_app.config["MAIL_PASSWORD"]
    )
    server.send_message(msg)
    server.quit()
