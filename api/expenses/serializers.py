from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator

from rest_framework import serializers

from api.core.utils import DotsValidationError

from api.expenses.models import Expense, ExpenseSplit, ExpenseItem
from api.groups.models import Group, GroupMember

from api.groups.serializers import GroupMemberSerializer
from api.categories.serializers import CategorySerializer


User = get_user_model()


class ExpenseSplitSerializer(serializers.ModelSerializer):
    participant = GroupMemberSerializer(read_only=True)
    
    class Meta:
        model = ExpenseSplit
        fields = ["id", "participant", "amount", "percentage", "is_included"]


class ExpenseItemSerializer(serializers.ModelSerializer):
    assignee = GroupMemberSerializer(read_only=True)

    class Meta:
        model = ExpenseItem
        fields = ["id", "title", "amount", "assignee"]


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by = GroupMemberSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    splits = ExpenseSplitSerializer(source="expense_splits", many=True, read_only=True)
    items = ExpenseItemSerializer(many=True, read_only=True)
    
    class Meta:
        model = Expense
        fields = [
            "id", "group", "title", "amount", "paid_by", "category", "notes",
            "split_type", "splits", "items", "created_by", "created_at", "updated_at"
        ]


class ExpenseSplitInputSerializer(serializers.Serializer):
    participant = serializers.IntegerField(required=True)
    percentage = serializers.DecimalField(max_digits=5, decimal_places=2, validators=[MinValueValidator(Decimal("0.10")), MaxValueValidator(Decimal("100.00"))], required=False, allow_null=True)
    is_included = serializers.BooleanField(required=True)


class ExpenseItemInputSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    title = serializers.CharField(required=True)
    amount = serializers.DecimalField(max_digits=9, decimal_places=2, required=True)
    assignee = serializers.IntegerField(required=True)


class ExpenseCreateSerializer(serializers.ModelSerializer):
    splits = ExpenseSplitInputSerializer(many=True, required=False, write_only=True)
    items = ExpenseItemInputSerializer(many=True, required=False, write_only=True)
    
    class Meta:
        model = Expense
        fields = ["group", "title", "amount", "paid_by", "category", "notes", "split_type", "splits", "items"]
    
    def validate(self, attrs):
        request = self.context["request"]
        group = attrs["group"]
        paid_by = attrs["paid_by"]
        split_type = attrs["split_type"]
        splits = attrs.get("splits", None)
        items = attrs.get("items", [])
        
        if not Group.objects.filter(id=group.id, created_by=request.user):
            raise DotsValidationError({"error": "You do not have permissions to add expense in this group."})

        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            raise DotsValidationError({"error": "You must be a member of this group to add expenses."})
        
        if paid_by.group != group:
            raise DotsValidationError({"error": "Paid by member must belong to this group."})
        
        if split_type == Expense.SplitType.ITEMIZED:
            if not items:
                raise DotsValidationError({"error": "Items are required for itemized split type."})
            
            assignee_ids = [i["assignee"] for i in items]
            group_members = GroupMember.objects.filter(group=group, id__in=assignee_ids)
            if group_members.count() != len(set(assignee_ids)):
                raise DotsValidationError({"error": "All item assignees must belong to this group."})

            total_items_amount = sum([i["amount"] for i in items])
            if total_items_amount != attrs["amount"]:
                raise DotsValidationError({"error": "Total of item amounts must equal expense amount."})

            attrs["_group_members"] = {gm.id: gm for gm in group_members}
            return attrs
        
        if split_type in (Expense.SplitType.EQUAL, Expense.SplitType.PERCENTAGE):
            if not splits:
                raise DotsValidationError({"error": "Splits are required for equal/percentage split types."})
            
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
        splits_data = validated_data.pop("splits", [])
        items_data = validated_data.pop("items", [])
        group_members = validated_data.pop("_group_members", {})
        validated_data["created_by"] = self.context["request"].user
        
        expense = Expense.objects.create(**validated_data)

        if expense.split_type == Expense.SplitType.ITEMIZED:
            for item in items_data:
                assignee_id = item["assignee"]
                ExpenseItem.objects.create(
                    expense=expense,
                    title=item["title"],
                    amount=item["amount"],
                    assignee=group_members[assignee_id]
                )
            
            agg = {}
            for it in items_data:
                pid = it["assignee"]
                agg.setdefault(pid, Decimal("0"))
                agg[pid] += it["amount"]

            for pid, amt in agg.items():
                ExpenseSplit.objects.create(
                    expense=expense,
                    participant=group_members[pid],
                    amount=amt,
                    is_included=True
                )
            return expense
        
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
    splits = ExpenseSplitInputSerializer(many=True, required=False, write_only=True)
    items = ExpenseItemInputSerializer(many=True, required=False, write_only=True)
    delete_items = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, write_only=True)
    
    class Meta:
        model = Expense
        fields = ["title", "amount", "paid_by", "category", "notes", "splits", "items", "delete_items"]
    
    def validate(self, attrs):
        request = self.context["request"]
        instance = self.instance
        amount = attrs.get("amount", instance.amount)
        group = instance.group
        split_type = attrs.get("split_type", instance.split_type)
        items = attrs.get("items", None)
        delete_items = attrs.get("delete_items", None)
        
        if not GroupMember.objects.filter(group=group, user=request.user).exists():
            raise DotsValidationError({"error": "You must be a member of this group to update expenses."})
        
        if "paid_by" in attrs:
            paid_by = attrs["paid_by"]
            if paid_by.group != group:
                raise DotsValidationError({"error": "Paid by member must belong to this group."})

        if split_type == Expense.SplitType.ITEMIZED:
            if amount != instance.amount and (items is None and delete_items is None):
                raise DotsValidationError({"error": "When updating amount for an itemized expense, you must provide `items` and/or `delete_items` to reflect the change."})
            
            existing_items_qs = ExpenseItem.objects.filter(expense=instance)
            existing_items = {itm.id: itm for itm in existing_items_qs}
            delete_ids = set()

            if delete_items is not None:
                delete_ids = set(delete_items or [])
                if delete_ids:
                    not_owned = delete_ids - set(existing_items.keys())
                    if not_owned:
                        raise DotsValidationError({"error": "Some item ids to delete do not belong to this expense."})
            
            if items is not None:
                update_items = []
                create_items = []
                seen_ids = set()

                group_member_ids = [it["assignee"] for it in items]
                group_members = {gm.id: gm for gm in GroupMember.objects.filter(group=group, id__in=group_member_ids)}

                if len(group_members) != len(set(group_member_ids)):
                    raise DotsValidationError({"error": "All item assignees must belong to this group."})

                attrs["_group_members"] = group_members

                for raw in items:
                    if "id" in raw:
                        iid = raw["id"]
                        if iid not in existing_items:
                            raise DotsValidationError({"error": f"Item id {iid} does not belong to this expense."})
                        if iid in seen_ids:
                            raise DotsValidationError({"error": f"Duplicate item id {iid} in payload."})
                        seen_ids.add(iid)
                        update_items.append(raw)
                    else:
                        create_items.append(raw)
            else:
                update_items = []
                create_items = []
            
            total = Decimal("0")
            for eid, itm in existing_items.items():
                if eid in delete_ids:
                    continue
                
                updated = next((raw for raw in update_items if raw.get("id") == eid), None)
                if updated:
                    amt = updated.get("amount")
                    if amt is None:
                        raise DotsValidationError({"error": "Updated items must include `amount`."})
                    total += Decimal(str(amt))
                else:
                    total += (itm.amount or Decimal("0"))
            
            for raw in create_items:
                amt = raw.get("amount")
                if amt is None:
                    raise DotsValidationError({"error": "New items must include `amount`."})
                total += Decimal(str(amt))

            remaining_items_count = (
                len(existing_items) 
                - len(delete_ids) 
                + len([raw for raw in update_items if raw.get("id") in existing_items]) 
                + len(create_items)
            )

            if remaining_items_count == 0:
                raise DotsValidationError({"error": "An itemized expense must contain at least one item."})

            if total != Decimal(str(amount)):
                raise DotsValidationError({"error": f"Total of items ({total}) does not equal expense amount ({amount})."})
            
            attrs["_items_ops"] = {
                "delete_ids": delete_ids,
                "update_items": update_items,
                "create_items": create_items,
            }

            return attrs
        
        if "splits" in attrs and split_type in (Expense.SplitType.EQUAL, Expense.SplitType.PERCENTAGE):
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
        items_ops = validated_data.pop("_items_ops", None)
        old_items = validated_data.pop("items", None)

        old_amount = instance.amount
        old_split_type = instance.split_type

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        existing_splits = {s.participant_id: s for s in instance.expense_splits.all()}

        if instance.split_type == Expense.SplitType.ITEMIZED and items_ops is not None:
            delete_ids = items_ops["delete_ids"]
            update_items = items_ops["update_items"]
            create_items = items_ops["create_items"]

            if delete_ids:
                ExpenseItem.objects.filter(id__in=delete_ids, expense=instance).delete()
            
            items_to_update = []
            if update_items:
                ids_to_update = [raw["id"] for raw in update_items]
                existing_map = {itm.id: itm for itm in ExpenseItem.objects.filter(id__in=ids_to_update, expense=instance)}
                for raw in update_items:
                    itm = existing_map[raw["id"]]
                    itm.title = raw["title"]
                    itm.amount = Decimal(str(raw["amount"]))
                    assignee_id = raw["assignee"]
                    if assignee_id != itm.assignee_id:
                        try:
                            gm = GroupMember.objects.get(id=assignee_id, group=instance.group)
                        except GroupMember.DoesNotExist:
                            raise DotsValidationError({"error": f"Assignee {assignee_id} does not belong to this expense's group."})
                        itm.assignee = gm
                    items_to_update.append(itm)
                if items_to_update:
                    ExpenseItem.objects.bulk_update(items_to_update, ["title", "amount", "assignee"])
            
            if create_items:
                assignee_ids = list({raw["assignee"] for raw in create_items})
                gm_map = {gm.id: gm for gm in GroupMember.objects.filter(group=instance.group, id__in=assignee_ids)}
                to_create = []
                for raw in create_items:
                    assignee = gm_map.get(raw["assignee"])
                    if assignee is None:
                        raise DotsValidationError({"error": f"Assignee {raw['assignee']} does not belong to this expense's group."})
                    to_create.append(ExpenseItem(
                        expense=instance,
                        title=raw["title"],
                        amount=Decimal(str(raw["amount"])),
                        assignee=assignee
                    ))
                if to_create:
                    ExpenseItem.objects.bulk_create(to_create)
            
            agg_qs = ExpenseItem.objects.filter(expense=instance).values("assignee").annotate(total=Sum("amount"))
            aggregated = {row["assignee"]: Decimal(row["total"] or 0) for row in agg_qs}

            splits_to_update = []
            splits_to_create = []
            for participant_id, amt in aggregated.items():
                if participant_id in existing_splits:
                    s = existing_splits[participant_id]
                    s.amount = amt
                    s.is_included = True
                    s.percentage = None
                    splits_to_update.append(s)
                else:
                    splits_to_create.append(ExpenseSplit(
                        expense=instance,
                        participant_id=participant_id,
                        amount=amt,
                        is_included=True
                    ))

            participants_with_items = set(aggregated.keys())
            for pid, s in existing_splits.items():
                if pid not in participants_with_items:
                    s.amount = None
                    s.is_included = False
                    s.percentage = None
                    splits_to_update.append(s)

            if splits_to_update:
                ExpenseSplit.objects.bulk_update(splits_to_update, ["amount", "is_included", "percentage"])
            if splits_to_create:
                ExpenseSplit.objects.bulk_create(splits_to_create)
            
            return instance

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
