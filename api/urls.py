from django.urls import include, path

from rest_framework.routers import DefaultRouter

from api.jwtauth.views import OTPViewSet, RegistrationViewSet, ProfileViewSets, UserProfileViewset
from api.friends.views import FriendViewSet
from api.groups.views import GroupViewSet, GroupMemberViewSet
from api.categories.views import CategoryViewset
from api.expenses.views import ExpenseViewSet
from api.activities.views import ActivityViewset, send_test_notification
from api.users.views import DashboardStatisticsView, DashboardSpendingPatternView
from fcm_django.api.rest_framework import FCMDeviceAuthorizedViewSet

router = DefaultRouter(trailing_slash=False)

router.register(r"otp", OTPViewSet, basename="otp")
router.register(r"register", RegistrationViewSet, basename="register")
router.register(r"profile", ProfileViewSets, basename="profile")
router.register(r"friends", FriendViewSet, basename="friends")
router.register(r"groups", GroupViewSet, basename="groups")
router.register(r"group-members", GroupMemberViewSet, basename="group_members")
router.register(r"categories", CategoryViewset, basename="categories")
router.register(r"expenses", ExpenseViewSet, basename="expenses")
router.register(r'activities', ActivityViewset, basename="notifications")
router.register(r"devices", FCMDeviceAuthorizedViewSet, basename="devices")

urlpatterns = [
    path("auth/", include("api.jwtauth.urls")),
    path("profile/update", UserProfileViewset.as_view({"patch": "partial_update"}), name="user_update"),
    path("profile/image", UserProfileViewset.as_view({"patch": "user_image"}), name="user_image"),
    path("dashboard/statistics", DashboardStatisticsView.as_view(), name="dashboard_statistics"),
    path("dashboard/spending-patterns", DashboardSpendingPatternView.as_view(), name="dashboard_spending_patterns"),
    path("send-test-fcm", send_test_notification),
] + router.urls
