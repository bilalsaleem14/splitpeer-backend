from decimal import Decimal

from django.db.models import Sum, Q
from django.contrib.auth import get_user_model

from rest_framework import serializers

from allauth.socialaccount.models import SocialAccount

from api.core.validators import validate_image

from api.expenses.models import ExpenseSplit
from api.categories.models import Category

from api.users.utils import get_month_boundaries


User = get_user_model()
    

class UserSerializer(serializers.ModelSerializer):
    has_unread_activities = serializers.SerializerMethodField()
    is_social = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "fullname", "profile_picture", "is_darkmode", "is_cloud_sync", "has_unread_activities", "is_social"]
    
    def get_has_unread_activities(self, obj):
        has_unread = obj.received_notifications.all().filter(is_read=False).exists()
        return True if has_unread else False
    
    def get_is_social(self, obj):
        return SocialAccount.objects.filter(user=obj).exists()


class ImageSerializer(serializers.ModelSerializer):
    profile_picture = serializers.ImageField(validators=[validate_image()])
    
    class Meta:
        model = User
        fields = ["profile_picture"]


class ShortUserSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields = ["id", "email", "fullname", "profile_picture"]


class DashboardStatisticsSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)

    def calculate_statistics(self, user, date=None):
        month_start, today_end = get_month_boundaries(date)
        days_passed = (today_end.date() - month_start.date()).days + 1
        
        total_expense = ExpenseSplit.objects.filter(Q(participant__user=user) & Q(is_included=True) & Q(expense__created_at__gte=month_start) & Q(expense__created_at__lte=today_end)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        daily_average = total_expense / Decimal(days_passed) if days_passed > 0 else Decimal("0.00")
        
        return {
            "total_expense": total_expense.quantize(Decimal("0.01")),
            "daily_average": daily_average.quantize(Decimal("0.01")),
            # "days_passed": days_passed,
            # "month_start": month_start.date(),
            # "month_end": today_end.date(),
        }

    def to_representation(self, instance):
        user = self.context.get("user")
        date = self.validated_data.get("date")
        stats = self.calculate_statistics(user, date)
        
        return {
            "total_expense": str(stats["total_expense"]),
            "daily_average": str(stats["daily_average"]),
            # "days_passed": stats["days_passed"],
            # "period": {
            #     "start_date": stats["month_start"].isoformat(),
            #     "end_date": stats["month_end"].isoformat(),
            # }
        }


class DashboardSpendingPatternSerializer(serializers.Serializer):
    created_at__gte = serializers.DateTimeField(required=False)
    created_at__lte = serializers.DateTimeField(required=False)

    def calculate_spending_by_category(self, user, date_gte=None, date_lte=None):
        all_categories = Category.objects.all()
        filters = Q(participant__user=user) & Q(is_included=True)
        
        if date_gte:
            filters &= Q(expense__created_at__gte=date_gte)
        
        if date_lte:
            filters &= Q(expense__created_at__lte=date_lte)
        
        spending_by_category = ExpenseSplit.objects.filter(filters).values("expense__category__id").annotate(total_amount=Sum("amount"))
        spending_dict = {item["expense__category__id"]: item["total_amount"] or Decimal("0.00") for item in spending_by_category}
        uncategorized_spending = ExpenseSplit.objects.filter(filters & Q(expense__category__isnull=True)).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
        
        data = []
        total_spending = Decimal("0.00")
        
        for category in all_categories:
            amount = spending_dict.get(category.id, Decimal("0.00"))
            data.append({"label": category.name, "value": str(amount)})
            total_spending += amount
        
        if uncategorized_spending > 0:
            data.append({"label": "Uncategorized", "value": str(uncategorized_spending)})
            total_spending += uncategorized_spending
        
        return {"data": data}

    def to_representation(self, instance):
        user = self.context.get("user")
        
        date_gte = self.validated_data.get("created_at__gte")
        date_lte = self.validated_data.get("created_at__lte")
        
        result = self.calculate_spending_by_category(user, date_gte, date_lte)
        return {"data": result["data"]}
