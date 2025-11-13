from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from api.jwtauth.views import LoginViewset, LogoutView


urlpatterns = [
    path(r"login", LoginViewset.as_view(), name="login"),
    path(r"logout", LogoutView.as_view(), name="logout"),
    path(r"token/refresh", TokenRefreshView.as_view(), name="logout"),
]
