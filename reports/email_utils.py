# reports/email_utils.py - Enhanced version
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from flask import current_app
from datetime import datetime

def send_email(to_email: str, subject: str, body: str):
    """Original function - keep for backward compatibility"""
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

def send_html_email(to_email: str, subject: str, html_content: str, text_content: str, sender_name="CityFix Team"):
    """
    Send HTML email with fallback to plain text.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        html_content (str): HTML email content
        text_content (str): Plain text fallback content
        sender_name (str): Display name for sender
    """
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        
        # Set sender with display name
        sender_addr = current_app.config["MAIL_DEFAULT_SENDER"]
        msg["From"] = formataddr((sender_name, sender_addr))
        msg["To"] = to_email
        
        # Set both plain text and HTML content
        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype='html')
        
        # Send the email
        server = smtplib.SMTP(
            current_app.config["MAIL_SERVER"],
            current_app.config["MAIL_PORT"]
        )
        
        if current_app.config.get("MAIL_USE_TLS"):
            server.starttls()
            
        if current_app.config.get("MAIL_USERNAME"):
            server.login(
                current_app.config["MAIL_USERNAME"],
                current_app.config["MAIL_PASSWORD"]
            )
            
        server.send_message(msg)
        server.quit()
        
        return True
        
    except Exception as e:
        current_app.logger.error(f"Failed to send HTML email: {e}")
        raise e

def get_password_reset_email(reset_code, expires_minutes=15):
    """
    Get password reset email in both HTML and plain text formats.
    
    Args:
        reset_code (str): 6-digit verification code
        expires_minutes (int): Number of minutes until code expires
        
    Returns:
        tuple: (html_content, text_content, subject)
    """
    subject = "🔐 CityFix Password Reset Code"
    
    # HTML version
    html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Password Reset - CityFix</title>
    <style>
        body {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #374151;
            background-color: #f9fafb;
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            background-color: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        .header {{
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            color: white;
            padding: 32px 24px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
            font-weight: 700;
        }}
        .content {{
            padding: 32px 24px;
        }}
        .code-container {{
            background: linear-gradient(135deg, #eff6ff, #dbeafe);
            border: 2px solid #3b82f6;
            border-radius: 12px;
            padding: 24px;
            text-align: center;
            margin: 24px 0;
        }}
        .reset-code {{
            font-size: 32px;
            font-weight: 800;
            color: #1d4ed8;
            letter-spacing: 8px;
            font-family: 'Courier New', monospace;
            margin: 8px 0;
        }}
        .code-label {{
            color: #6b7280;
            font-size: 14px;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 1px;
        }}
        .info-box {{
            background: #fef3c7;
            border: 1px solid #f59e0b;
            border-radius: 8px;
            padding: 16px;
            margin: 24px 0;
        }}
        .info-box .icon {{
            color: #d97706;
            font-weight: bold;
        }}
        .footer {{
            background: #f9fafb;
            padding: 24px;
            text-align: center;
            border-top: 1px solid #e5e7eb;
            font-size: 14px;
            color: #6b7280;
        }}
        @media (max-width: 480px) {{
            .container {{
                margin: 16px;
                border-radius: 8px;
            }}
            .header, .content {{
                padding: 24px 16px;
            }}
            .reset-code {{
                font-size: 24px;
                letter-spacing: 4px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🏙️ CityFix</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9;">Password Reset Request</p>
        </div>
        
        <div class="content">
            <h2 style="color: #1f2937; margin-top: 0;">Reset Your Password</h2>
            
            <p>Hello!</p>
            
            <p>You requested a password reset for your CityFix account. Use the verification code below to reset your password:</p>
            
            <div class="code-container">
                <div class="code-label">Your Verification Code</div>
                <div class="reset-code">{reset_code}</div>
                <div style="font-size: 14px; color: #6b7280; margin-top: 8px;">
                    Valid for {expires_minutes} minutes
                </div>
            </div>
            
            <div class="info-box">
                <p style="margin: 0;"><span class="icon">⏱️</span> <strong>Important:</strong> This code will expire in {expires_minutes} minutes for your security.</p>
            </div>
            
            <h3 style="color: #1f2937;">What's next?</h3>
            <ol style="padding-left: 20px;">
                <li>Copy the 6-digit code above</li>
                <li>Return to the CityFix password reset page</li>
                <li>Enter the code and your new password</li>
                <li>Click "Reset Password" to complete the process</li>
            </ol>
            
            <p><strong>🔒 Security Notice:</strong> If you didn't request this password reset, please ignore this email. Your account remains secure.</p>
        </div>
        
        <div class="footer">
            <p><strong>CityFix Team</strong></p>
            <p>Making cities better, one report at a time</p>
            <p style="font-size: 12px; margin-top: 16px;">
                This email was sent to you because a password reset was requested for your CityFix account.<br>
                © {datetime.now().year} CityFix. All rights reserved.
            </p>
        </div>
    </div>
</body>
</html>
    """
    
    # Plain text version
    text_content = f"""
🏙️ CityFix - Password Reset Request

Hello!

You requested a password reset for your CityFix account.

YOUR VERIFICATION CODE: {reset_code}

This code will expire in {expires_minutes} minutes.

WHAT'S NEXT?
1. Copy the 6-digit code above
2. Return to the CityFix password reset page
3. Enter the code and your new password
4. Click "Reset Password" to complete the process

SECURITY NOTICE:
If you didn't request this password reset, please ignore this email. 
Your account remains secure.

---
CityFix Team
Making cities better, one report at a time

© {datetime.now().year} CityFix. All rights reserved.
    """
    
    return html_content, text_content, subject

def send_password_reset_email(to_email: str, reset_code: str, expires_minutes: int = 15):
    """
    Send a password reset email with the verification code.
    
    Args:
        to_email (str): Recipient email address
        reset_code (str): 6-digit verification code
        expires_minutes (int): Number of minutes until code expires
    """
    html_content, text_content, subject = get_password_reset_email(reset_code, expires_minutes)
    return send_html_email(to_email, subject, html_content, text_content)