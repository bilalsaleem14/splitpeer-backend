from decimal import Decimal

from django.db import transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from rest_framework import serializers

from api.core.utils import DotsValidationError

from api.categories.models import Category
from api.expenses.models import Expense, ExpenseSplit
from api.groups.models import Group, GroupMember

from api.groups.serializers import GroupMemberSerializer
from api.categories.serializers import CategorySerializer


User = get_user_model()


class ExpenseSplitSerializer(serializers.ModelSerializer):
    participant = GroupMemberSerializer(read_only=True)
    
    class Meta:
        model = ExpenseSplit
        fields = ["id", "participant", "amount", "percentage", "is_included"]


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by = GroupMemberSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    splits = ExpenseSplitSerializer(source="expense_splits", many=True, read_only=True)
    
    class Meta:
        model = Expense
        fields = [
            "id", "group", "title", "amount", "paid_by", "category", "notes",
            "split_type", "splits", "created_by", "created_at", "updated_at"
        ]


class ExpenseSplitInputSerializer(serializers.Serializer):
    participant = serializers.IntegerField(required=True)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.10")), MaxValueValidator(Decimal("100.00"))], required=False, allow_null=True)
    is_included = serializers.BooleanField(required=True)


class ExpenseCreateSerializer(serializers.ModelSerializer):
    splits = ExpenseSplitInputSerializer(many=True, required=True, write_only=True)
    
    class Meta:
        model = Expense
        fields = ["group", "title", "amount", "paid_by", "category", "notes", "split_type", "splits"]
    
    def validate(self, attrs):
        request = self.context["request"]
        group = attrs["group"]
        paid_by = attrs["paid_by"]
        split_type = attrs["split_type"]
        splits = attrs["splits"]
        
        if not Group.objects.filter(id=group.id, created_by=request.user):
            raise DotsValidationError({"error": "You do not have permissions to add expense in this group."})

        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            raise DotsValidationError({"error": "You must be a member of this group to add expenses."})
        
        if paid_by.group != group:
            raise DotsValidationError({"error": "Paid by member must belong to this group."})
        
        group_member_ids = [s["participant"] for s in splits]
        group_members = GroupMember.objects.filter(group=group, id__in=group_member_ids)
        
        if group_members.count() != len(set(group_member_ids)):
            raise DotsValidationError({"error": "All members in splits must belong to this group."})
        
        included_splits = [s for s in splits if s["is_included"]]
        if not included_splits:
            raise DotsValidationError({"error": "At least one member must be included in the split."})
        
        if split_type == Expense.SplitType.PERCENTAGE:
            included_count = len(included_splits)
            total_percentage = Decimal("0")
            for split in included_splits:
                if "percentage" not in split or split["percentage"] is None:
                    raise DotsValidationError({"error": "Percentage is required for all included members in percentage split."})
                if split["percentage"] < 0.1:
                    raise DotsValidationError({"error": "Percentage must be greater than 0.1"})
                total_percentage += split["percentage"]
            
            if included_count % 2 != 0:
                if abs(total_percentage - Decimal("100")) > Decimal("0.5"):
                    raise DotsValidationError({"error": "Total percentage must be equal to 100%."})
            else:
                if total_percentage != Decimal("100"):
                    raise DotsValidationError({"error": "Total percentage must be equal to 100%."})
        
        attrs["_group_members"] = {gm.id: gm for gm in group_members}
        
        return attrs
    
    @transaction.atomic
    def create(self, validated_data):
        splits_data = validated_data.pop("splits")
        group_members = validated_data.pop("_group_members")
        validated_data["created_by"] = self.context["request"].user
        
        expense = Expense.objects.create(**validated_data)
        
        included_splits = [s for s in splits_data if s["is_included"]]
        
        if expense.split_type == Expense.SplitType.EQUAL:
            split_amount = expense.amount / len(included_splits)
            for split_data in splits_data:
                participant_id = split_data["participant"]
                ExpenseSplit.objects.create(
                    expense=expense,
                    participant=group_members[participant_id],
                    amount=split_amount if split_data["is_included"] else None,
                    is_included=split_data["is_included"]
                )
        
        elif expense.split_type == Expense.SplitType.PERCENTAGE:
            for split_data in splits_data:
                participant_id = split_data["participant"]
                if split_data["is_included"]:
                    percentage = split_data["percentage"]
                    amount = (expense.amount * percentage) / Decimal("100")
                else:
                    percentage = None
                    amount = None
                
                ExpenseSplit.objects.create(
                    expense=expense,
                    participant=group_members[participant_id],
                    amount=amount,
                    percentage=percentage,
                    is_included=split_data["is_included"]
                )
        
        return expense


class ExpenseUpdateSerializer(serializers.ModelSerializer):
    splits = ExpenseSplitInputSerializer(many=True, required=True, write_only=True)
    
    class Meta:
        model = Expense
        fields = ["title", "amount", "paid_by", "category", "notes", "splits"]
    
    def validate(self, attrs):
        request = self.context["request"]
        instance = self.instance
        group = instance.group
        split_type = attrs.get("split_type", None)
        
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            raise DotsValidationError({"error": "You must be a member of this group to update expenses."})
        
        if "paid_by" in attrs:
            paid_by = attrs["paid_by"]
            if paid_by.group != group:
                raise DotsValidationError({"error": "Paid by member must belong to this group."})
        
        if "splits" in attrs:
            splits = attrs["splits"]
            split_type = instance.split_type
            
            group_member_ids = [s["participant"] for s in splits]
            group_members = GroupMember.objects.filter(group=group, id__in=group_member_ids)
            
            if group_members.count() != len(set(group_member_ids)):
                raise DotsValidationError({"error": "All members in splits must belong to this group."})
            
            included_splits = [s for s in splits if s["is_included"]]
            if not included_splits:
                raise DotsValidationError({"error": "At least one member must be included in the split."})
            
            if split_type == Expense.SplitType.PERCENTAGE:
                included_count = len(included_splits)
                total_percentage = Decimal("0")
                for split in included_splits:
                    if "percentage" not in split or split["percentage"] is None:
                        raise DotsValidationError({"splits": "Percentage is required for all included members in percentage split."})
                    if split["percentage"] < 0.1:
                        raise DotsValidationError({"splits": "Percentage must be greater than 0.1."})
                    total_percentage += split["percentage"]
                
                if included_count % 2 != 0:
                    if abs(total_percentage - Decimal("100")) > Decimal("0.5"):
                        raise DotsValidationError({"error": "Total percentage must be ~100%."})
                else:
                    if total_percentage != Decimal("100"):
                        raise DotsValidationError({"error": "Total percentage must be equal to 100%."})
            
            attrs["_group_members"] = {gm.id: gm for gm in group_members}
        
        return attrs
    
    @transaction.atomic
    def update(self, instance, validated_data):
        splits_data = validated_data.pop("splits", None)

        old_amount = instance.amount
        old_split_type = instance.split_type

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        existing_splits = {s.participant_id: s for s in instance.expense_splits.all()}

        if splits_data:
            for data in splits_data:
                participant_id = data["participant"]
                split = existing_splits.get(participant_id)

                if split:
                    if "is_included" in data:
                        split.is_included = data["is_included"]

                    if "percentage" in data:
                        split.percentage = data["percentage"]

                    if "amount" in data:
                        split.amount = data["amount"]

                    split.save()
                else:
                    ExpenseSplit.objects.create(
                        expense=instance,
                        participant_id=participant_id,
                        is_included=data.get("is_included", True),
                        percentage=data.get("percentage"),
                        amount=data.get("amount"),
                    )

        amount_changed = ("amount" in validated_data and validated_data["amount"] != old_amount)
        split_type_changed = ("split_type" in validated_data and validated_data["split_type"] != old_split_type)
        splits_provided = splits_data is not None

        must_recalculate = amount_changed or split_type_changed or splits_provided

        if must_recalculate:
            all_splits_qs = instance.expense_splits.all()
            included_splits = [s for s in all_splits_qs if s.is_included]

            if instance.split_type == Expense.SplitType.EQUAL:
                per_participant = (instance.amount / len(included_splits)) if included_splits else Decimal("0")
                for s in all_splits_qs:
                    s.amount = per_participant if s.is_included else None
                    s.percentage = None
                    s.save()

            elif instance.split_type == Expense.SplitType.PERCENTAGE:
                for s in all_splits_qs:
                    if s.is_included and s.percentage:
                        s.amount = (instance.amount * s.percentage) / Decimal("100")
                    else:
                        s.amount = None
                    s.save()

        return instance
