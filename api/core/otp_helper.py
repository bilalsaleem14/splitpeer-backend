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


def send_html_email(subject, recipient_list, template_name, context_obj, attach_badges=False):
    if isinstance(recipient_list, str):
        recipient_list = [recipient_list]
    text_template = get_template(template_name)
    template_content = text_template.render(context_obj)
    msg = EmailMultiAlternatives(subject, subject, settings.EMAIL_HOST_USER, recipient_list)
    msg.attach_alternative(template_content, "text/html")
    if attach_badges:
        attach_inline_images(msg)
    msg.send()


def send_confirmation_code(new_otp, otp_type):
    send_html_email(
        subject="WhoSplit OTP Verification.",
        recipient_list=[new_otp.email],
        template_name="email_templates/verify-code-email.html",
        context_obj={"verification_code": new_otp.code, "type": otp_type},
    )


def verify_otp(user_otp):
    if timezone.now() > user_otp.timeout:
        raise DotsValidationError("Verification token expired!")
    return user_otp


def send_report_email(data):
    send_html_email(
        subject="WhoSplit Report Problem.",
        recipient_list=settings.CONTACT_US_EMAILS,
        template_name="email_templates/report-email.html",
        context_obj={"data": data},
    )


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


# Send invitation email to join WhoSplit
def send_invite_email(email, inviter, group_name=None):
    try:
        if group_name:
            email_subject = f"{inviter.fullname} added you to '{group_name}' on WhoSplit!"
        else:
            email_subject = f"{inviter.fullname} invited you to WhoSplit - Split expenses easily!"

        context_obj = {"inviter_name": inviter.fullname, "inviter_email": inviter.email, "invited_email": email, "group_name": group_name}
        send_html_email(subject=email_subject, recipient_list=[email], template_name="email_templates/friend_invitation.html", context_obj=context_obj, attach_badges=True)
    except Exception as e:
        print(f"Failed to send invite email: {e}")


# Send group join/access request email with Approve/Reject links to the group creator
def send_group_join_request_email(creator, requester, group, approve_url, reject_url):
    try:
        email_subject = f"WhoSplit Group Join Request - {group.name}"
        context_obj = {
            "creator_name": creator.fullname, "requester_name": requester.fullname,
            "requester_email": requester.email, "group_name": group.name,
            "approve_url": approve_url, "reject_url": reject_url,
        }
        send_html_email(subject=email_subject, recipient_list=[creator.email], template_name="email_templates/group_join_request.html", context_obj=context_obj)
    except Exception as e:
        print(f"Failed to send group join request email: {e}")


# Send approval or rejection notification email to the participant
def send_group_join_response_email(member_user, creator, group, is_approved):
    try:
        email_subject = f"WhoSplit Group Join Request Update - {group.name}"
        context_obj = {"member_name": member_user.fullname, "creator_name": creator.fullname, "group_name": group.name, "is_approved": is_approved}
        send_html_email(subject=email_subject, recipient_list=[member_user.email], template_name="email_templates/group_join_response.html", context_obj=context_obj)
    except Exception as e:
        print(f"Failed to send group join response email: {e}")
