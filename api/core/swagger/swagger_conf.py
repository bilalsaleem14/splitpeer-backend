from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

schema_view = get_schema_view(
    openapi.Info(
        title="SplitPeer",
        default_version="v3.2.0.2",
        contact=openapi.Contact(email="crymzee@crymzee.com"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)
