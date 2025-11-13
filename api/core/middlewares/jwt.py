from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser

from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError


async def get_user(scope):
    try:
        token = scope["query_string"].decode().split("=")[1]
        valid_data = JWTAuthentication().get_validated_token(token)
        user = await sync_to_async(JWTAuthentication().get_user)(valid_data)
        return user
    except (InvalidToken, TokenError, IndexError, KeyError):
        return AnonymousUser()


class JWTAuthMiddleware:

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        scope["user"] = await get_user(scope)
        return await self.app(scope, receive, send)
