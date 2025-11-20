from django.urls import include, path

from rest_framework.routers import DefaultRouter

from api.jwtauth.views import OTPViewSet, RegistrationViewSet, ProfileViewSets, UserProfileViewset
from api.friends.views import FriendViewSet
from api.groups.views import GroupViewSet, GroupMemberViewSet
from api.categories.views import CategoryViewset
from api.expenses.views import ExpenseViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r"otp", OTPViewSet, basename="otp")
router.register(r"register", RegistrationViewSet, basename="register")
router.register(r"profile", ProfileViewSets, basename="profile")
router.register(r"friends", FriendViewSet, basename="friends")
router.register(r"groups", GroupViewSet, basename="groups")
router.register(r"group-members", GroupMemberViewSet, basename="group-members")
router.register(r"categories", CategoryViewset, basename="categories")
router.register(r"expenses", ExpenseViewSet, basename="expenses")

urlpatterns = [
    path("auth/", include("api.jwtauth.urls")),
    path("profile/update", UserProfileViewset.as_view({"patch": "partial_update"}), name="user-update"),
    path("profile/image", UserProfileViewset.as_view({"patch": "user_image"}), name="user-image"),
] + router.urls
