from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _

from rest_framework import status
from rest_framework.exceptions import APIException, _get_error_details

User = get_user_model()


class DotsValidationError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_detail = _("Invalid input.")
    default_code = "non_field"
    key = "validations"

    def __init__(self, detail=None, code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code

        if not isinstance(detail, dict) and not isinstance(detail, list):
            detail = {"non_field": [detail]}

        self.detail = _get_error_details(detail, code)


def validate_media_extension(value):
    valid_extensions = [".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov"]

    for file in value:
        if not any(file.name.lower().endswith(ext) for ext in valid_extensions):
            raise DotsValidationError({"image": f"Only images are allowed with this format: {valid_extensions}"})


def validate_file_extension(value):

    valid_extensions = [".jpg", ".jpeg", ".png", ".mp4", ".avi", ".mov"]

    if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
        raise DotsValidationError({"media": f"Only images and videos are allowed with this format: {valid_extensions}"})


def validate_document_extension(value):

    valid_extensions = [".pdf"]

    if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
        raise DotsValidationError({"media": f"Only valid pdf document is required."})


def build_serializer_context(scope):
    factory = RequestFactory()
    scheme = "https" if scope.get("scheme") == "https" else "http"
    host = dict(scope.get("headers", [])).get(b"host", b"localhost").decode()
    request = factory.get("/", **{"wsgi.url_scheme": scheme})
    request.META["HTTP_HOST"] = host
    return {"request": request}
