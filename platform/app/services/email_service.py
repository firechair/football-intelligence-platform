"""
Email Service for sending notifications, password reset, and email verification emails.
"""
import os
import logging
from typing import Optional, Dict, Any
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, To
from jinja2 import Template
from datetime import datetime

logger = logging.getLogger(__name__)

class EmailService:
    """Service for sending emails using SendGrid."""
    
    def __init__(self):
        self.api_key = os.getenv("SENDGRID_API_KEY")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@example.invalid")
        self.from_name = os.getenv("FROM_NAME", "FIP")
        self.base_url = os.getenv("BASE_URL", "https://example.invalid")
        
        if self.api_key:
            self.sg = SendGridAPIClient(api_key=self.api_key)
        else:
            logger.warning("SendGrid API key not found. Email service will not function.")
            self.sg = None
    
    def _send_email(self, to_email: str, subject: str, html_content: str, text_content: str = None) -> bool:
        """Send email using SendGrid."""
        if not self.sg:
            logger.error("SendGrid not configured. Cannot send email.")
            return False
            
        try:
            message = Mail(
                from_email=f"{self.from_name} <{self.from_email}>",
                to_emails=To(to_email),
                subject=subject,
                html_content=html_content,
                plain_text_content=text_content or self._html_to_text(html_content)
            )
            
            response = self.sg.send(message)
            
            if response.status_code in [200, 202]:
                logger.info(f"Email sent successfully to {to_email}")
                return True
            else:
                logger.error(f"Failed to send email to {to_email}. Status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            return False
    
    def _html_to_text(self, html_content: str) -> str:
        """Convert HTML content to plain text (basic implementation)."""
        # Simple HTML to text conversion
        import re
        text = re.sub(r'<[^>]+>', '', html_content)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def send_password_reset_email(self, to_email: str, username: str, reset_token: str) -> bool:
        """Send password reset email."""
        reset_url = f"{self.base_url}/reset-password?token={reset_token}"
        
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Password Reset - FIP</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #076cb9;">FIP</h1>
                </div>
                
                <h2>Password Reset Request</h2>
                
                <p>Hello {{ username }},</p>
                
                <p>You have requested to reset your password for your FIP account. Click the button below to reset your password:</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ reset_url }}" style="background-color: #076cb9; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Reset Password</a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background-color: #f5f5f5; padding: 10px; border-radius: 5px;">{{ reset_url }}</p>
                
                <p><strong>This link will expire in 1 hour.</strong></p>
                
                <p>If you didn't request this password reset, please ignore this email. Your password will remain unchanged.</p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    This email was sent by FIP.<br>
                    If you have any questions, please contact our support team.
                </p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            username=username,
            reset_url=reset_url
        )
        
        subject = "Reset Your FIP Password"
        
        return self._send_email(to_email, subject, html_content)
    
    def send_email_verification_email(self, to_email: str, username: str, verification_token: str) -> bool:
        """Send email verification email."""
        verification_url = f"{self.base_url}/verify-email?token={verification_token}"
        
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Verify Your Email - FIP</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #076cb9;">FIP</h1>
                </div>
                
                <h2>Welcome to FIP!</h2>
                
                <p>Hello {{ username }},</p>
                
                <p>Thank you for creating an account with FIP. To complete your registration and start using all our features, please verify your email address.</p>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ verification_url }}" style="background-color: #076cb9; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Verify Email Address</a>
                </div>
                
                <p>If the button doesn't work, copy and paste this link into your browser:</p>
                <p style="word-break: break-all; background-color: #f5f5f5; padding: 10px; border-radius: 5px;">{{ verification_url }}</p>
                
                <p><strong>This verification link will expire in 24 hours.</strong></p>
                
                <p>If you didn't create an account with FIP, please ignore this email.</p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    This email was sent by FIP.<br>
                    If you have any questions, please contact our support team.
                </p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            username=username,
            verification_url=verification_url
        )
        
        subject = "Verify Your FIP Account"
        
        return self._send_email(to_email, subject, html_content)
    
    def send_welcome_email(self, to_email: str, username: str) -> bool:
        """Send welcome email after successful email verification."""
        html_template = Template("""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Welcome to FIP!</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h1 style="color: #076cb9;">FIP</h1>
                </div>
                
                <h2>Welcome to FIP!</h2>
                
                <p>Hello {{ username }},</p>
                
                <p>Your email has been successfully verified! Welcome to FIP, your intelligent companion for making informed betting decisions.</p>
                
                <h3>What's Next?</h3>
                <ul>
                    <li>Explore our AI-powered match predictions</li>
                    <li>Get real-time odds comparisons</li>
                    <li>Use our intelligent chatbot for betting insights</li>
                    <li>Set up Two-Factor Authentication for enhanced security</li>
                </ul>
                
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{{ base_url }}" style="background-color: #076cb9; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block;">Start Exploring</a>
                </div>
                
                <p>If you have any questions, our support team is here to help.</p>
                
                <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                <p style="font-size: 12px; color: #666;">
                    This email was sent by FIP.<br>
                    If you have any questions, please contact our support team.
                </p>
            </div>
        </body>
        </html>
        """)
        
        html_content = html_template.render(
            username=username,
            base_url=self.base_url
        )
        
        subject = "Welcome to FIP - Your Account is Ready!"
        
        return self._send_email(to_email, subject, html_content)

# Create global instance
email_service = EmailService()
