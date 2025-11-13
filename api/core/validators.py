import re
import inspect

from rest_framework import serializers


class PasswordValidator(object):

    @staticmethod
    def one_symbol(value):
        if not set("[.?~!@#$%^&*()_+{}\":-;']+$").intersection(value):
            raise serializers.ValidationError("Password should have at least one symbol")
        return value

    @staticmethod
    def lower_letter(value):
        if not any(char.islower() for char in value):
            raise serializers.ValidationError("Password should have at least one lowercase letter")

        return value

    @staticmethod
    def upper_letter(value):
        if not any(char.isupper() for char in value):
            raise serializers.ValidationError("Password should have at least one uppercase letter")
        return value

    @staticmethod
    def number(value):
        if not any(char.isdigit() for char in value):
            raise serializers.ValidationError("Password should have at least one numeral")
        return value

    @staticmethod
    def length(value):
        if len(value) < 8:
            raise serializers.ValidationError("This password is too short. It must contain at least 8 characters.")
    
    @staticmethod
    def ascii_only(value):
        try:
            value.encode('ascii')
        except UnicodeEncodeError:
            raise serializers.ValidationError("Password contains unsupported symbols. Please use only standard symbols.")
        return value
    
    @classmethod
    def validate_all(cls, value):
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name not in ("validate_all", "__init__"):
                method(value)
        return value


def validate_coordinates(value):
    pattern = r"^POINT\s*\((-?\d+(\.\d+)?)\s+(-?\d+(\.\d+)?)\)$"
    if not re.match(pattern, value.strip()):
        raise serializers.ValidationError("Coordinates must be in format 'POINT (longitude latitude)'")


def validate_range(value):
    if len(value) < 2:
        raise serializers.ValidationError("Salary: From and To range both are required")

    if value[0] > value[1]:
        raise serializers.ValidationError("Salary: From should be lower than To")


def validate_length(text):
    text = re.sub(r"\s+", "", text)
    if len(text) > 75:
        raise serializers.ValidationError("Max len is 75")
