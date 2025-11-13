from django.contrib.auth import get_user_model

from api.core.otp_helper import verify_otp
from api.core.utils import DotsValidationError
from api.jwtauth.models import OTP


User = get_user_model()


class UserProfileOperations:

    @staticmethod
    def update_user_field(validated_data, user=None, field="password"):
        verification_token = validated_data["verification_token"]
        otp_type = OTP.Type.FORGOT if field == "password" else OTP.Type.CHANGE

        try:
            updated_fields = [field]
            otp = OTP.objects.get(verification_token=verification_token, type=otp_type)
            user = user or User.objects.get(email=otp.email)
            verify_otp(otp)

            if field == "password":
                user.set_password(validated_data["password"])
            elif field == "email":
                user.email = otp.email
            user.save(update_fields=updated_fields)
            otp.delete()
        except (OTP.DoesNotExist, User.DoesNotExist):
            raise DotsValidationError({"otp": ["Invalid token, regenerate the OTP."]})
