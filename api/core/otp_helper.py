import os
import secrets
import base64
from datetime import datetime
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import get_template
from django.utils import timezone

from api.core.utils import DotsValidationError


def get_random_otp():
    if settings.RANDOM_OTP:
        return str(secrets.randbelow(90000) + 10000)
    return "99999"


def get_otp_verified_token(otp, content):
    token_str = f"{datetime.now()}{content}{otp}"
    token_str_bytes = token_str.encode("ascii")
    base64_bytes = base64.b64encode(token_str_bytes)
    base64_message = base64_bytes.decode("ascii")
    return base64_message


def send_confirmation_code(new_otp, otp_type):
    email_subject = "WhoSplit OTP Verification."
    text_content = email_subject
    text_template = get_template("email_templates/verify-code-email.html")
    context_obj = {"verification_code": new_otp.code, "type": otp_type}
    template_content = text_template.render(context_obj)
    msg = EmailMultiAlternatives(email_subject, text_content, settings.EMAIL_HOST_USER, [new_otp.email])
    msg.attach_alternative(template_content, "text/html")
    msg.send()
    

def verify_otp(user_otp):
    if timezone.now() > user_otp.timeout:
        raise DotsValidationError("Verification token expired!")
    return user_otp


def send_report_email(data):
    email_subject = "WhoSplit Report Problem."
    text_content = email_subject
    text_template = get_template("email_templates/report-email.html")
    context_obj = {"data": data}
    template_content = text_template.render(context_obj)
    msg = EmailMultiAlternatives(email_subject, text_content, settings.EMAIL_HOST_USER, settings.CONTACT_US_EMAILS)
    msg.attach_alternative(template_content, "text/html")
    msg.send()


BADGE_DIR = os.path.join(settings.BASE_DIR, "media")

INLINE_IMAGES = [
    ("app-store-badge", "app-store-badge.png"),
    ("google-play-badge", "google-play-badge.png"),
]


def attach_inline_images(msg):
    msg.mixed_subtype = "related"
    for cid, filename in INLINE_IMAGES:
        with open(os.path.join(BADGE_DIR, filename), "rb") as f:
            img = MIMEImage(f.read(), _subtype="png")
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline", filename=filename)
        msg.attach(img)


def send_invite_email(email, inviter, group_name=None):
    """Send invitation email to join WhoSplit"""
    try:
        if group_name:
            email_subject = f"{inviter.fullname} added you to '{group_name}' on WhoSplit!"
        else:
            email_subject = f"{inviter.fullname} invited you to WhoSplit - Split expenses easily!"

        text_content = email_subject
        text_template = get_template("email_templates/friend_invitation.html")
        context_obj = {
            "inviter_name": inviter.fullname,
            "inviter_email": inviter.email,
            "invited_email": email,
            "group_name": group_name,
        }

        template_content = text_template.render(context_obj)
        msg = EmailMultiAlternatives(email_subject, text_content, settings.EMAIL_HOST_USER, [email])
        msg.attach_alternative(template_content, "text/html")
        attach_inline_images(msg)
        msg.send()

    except Exception as e:
        print(f"Failed to send invite email: {e}")
