from decimal import Decimal

from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model

from api.core.models import BaseModel, CharFieldSizes
from api.groups.models import Group, GroupMember
from api.categories.models import Category


User = get_user_model()


class Expense(BaseModel):

    class SplitType(models.TextChoices):
        EQUAL = "equal", "equal" 
        PERCENTAGE = "percentage", "percentage"
        ITEMIZED = "itemized", "itemized"
    
    group = models.ForeignKey(Group, related_name="group_expenses", on_delete=models.CASCADE)
    title = models.CharField(max_length=CharFieldSizes.SMALL)
    amount = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.50"))])
    paid_by = models.ForeignKey(GroupMember, related_name="expenses_paid_by", on_delete=models.CASCADE)
    category = models.ForeignKey(Category, related_name="expense_category", on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)
    split_type = models.CharField(max_length=CharFieldSizes.SMALL, choices=SplitType)
    created_by = models.ForeignKey(User, related_name="expenses_created_by", on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.title} - {self.amount} ({self.group.name})"


class ExpenseSplit(BaseModel):
    expense = models.ForeignKey(Expense, related_name="expense_splits", on_delete=models.CASCADE)
    participant = models.ForeignKey(GroupMember, related_name="expense_splits_member", on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=9, decimal_places=2, validators=[MinValueValidator(Decimal("0.50"))], null=True, blank=True)
    percentage = models.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.10")), MaxValueValidator(Decimal("100.00"))], null=True, blank=True)
    is_included = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ("expense", "participant")
    
    def __str__(self):
        return f"{self.expense.title} - {self.participant.user.get_full_name()} ({self.get_display_value()})"
    
    def get_display_value(self):
        if self.expense.split_type == Expense.SplitType.PERCENTAGE and self.percentage:
            return f"{self.percentage}%"
        elif self.amount:
            return f"${self.amount}"
        return "N/A"
