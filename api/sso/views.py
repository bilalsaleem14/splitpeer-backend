from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response

from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.facebook.views import FacebookOAuth2Adapter

from api.sso.serializers import SocialLoginSerializer


class GoogleLoginView(APIView):
    serializer_class = SocialLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save(adapter_class=GoogleOAuth2Adapter, request=request)
        return Response(serializer.get_login_response(user), status=status.HTTP_200_OK)


class FacebookLoginView(APIView):
    serializer_class = SocialLoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.save(adapter_class=FacebookOAuth2Adapter, request=request)
        return Response(serializer.get_login_response(user), status=status.HTTP_200_OK)
