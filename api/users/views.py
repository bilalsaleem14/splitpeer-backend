from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.users.serializers import DashboardStatisticsSerializer, DashboardSpendingPatternSerializer


class DashboardStatisticsView(APIView):
    serializer_class = DashboardStatisticsSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = self.serializer_class(data=request.query_params, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        statistics = serializer.to_representation(None)
        return Response(statistics, status=status.HTTP_200_OK)


class DashboardSpendingPatternView(APIView):
    serializer_class = DashboardSpendingPatternSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = self.serializer_class(data=request.query_params, context={'user': request.user})
        serializer.is_valid(raise_exception=True)
        spending_pattern = serializer.to_representation(None)
        return Response(spending_pattern, status=status.HTTP_200_OK)


