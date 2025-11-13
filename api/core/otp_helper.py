import base64
import secrets
from datetime import datetime

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils import timezone

from api.core.utils import DotsValidationError


def get_random_otp():
    # if is_send:
    #     return str(secrets.randbelow(90000) + 10000)
    return "99999"


def get_otp_verified_token(otp, content):
    token_str = f"{datetime.now()}{content}{otp}"
    token_str_bytes = token_str.encode("ascii")
    base64_bytes = base64.b64encode(token_str_bytes)
    base64_message = base64_bytes.decode("ascii")
    return base64_message


def send_confirmation_code(new_otp, otp_type):
    email_subject = "Splitpeer OTP Verification."
    text_content = email_subject
    text_template = get_template("email_templates/verify-code-email.html")
    context_obj = {"verification_code": new_otp.code, "type": otp_type}
    template_content = text_template.render(context_obj)
    msg = EmailMultiAlternatives(email_subject, text_content, settings.EMAIL_HOST_USER, [new_otp.email])
    msg.attach_alternative(template_content, "text/html")
    msg.send()
    

def verify_otp(user_otp):
    """returns user otp and error response if found any"""
    if timezone.now() > user_otp.timeout:
        raise DotsValidationError("Verification token expired!")
    return user_otp


def send_report_email(data):
    email_subject = "Splitpeer Report Problem."
    text_content = email_subject
    text_template = get_template("email_templates/report-email.html")
    context_obj = {"data": data}
    template_content = text_template.render(context_obj)
    msg = EmailMultiAlternatives(email_subject, text_content, settings.EMAIL_HOST_USER, settings.CONTACT_US_EMAILS)
    msg.attach_alternative(template_content, "text/html")
    msg.send()
