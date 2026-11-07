import re

from flask import request

from .errors import ApiError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^[0-9+\-\s()]{7,20}$")
PROPERTY_TYPES = ("house", "flat", "portion", "room", "studio")


def json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ApiError(400, "Request body must be a JSON object.")
    return data


class Validator:
    """Collects all field errors so the UI can show them together."""

    def __init__(self, data):
        self.data = data
        self.errors = {}
        self.clean = {}

    def string(self, field, required=True, min_len=1, max_len=255, label=None):
        label = label or field.replace("_", " ").capitalize()
        value = self.data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            if required:
                self.errors[field] = f"{label} is required."
            else:
                self.clean[field] = None
            return self
        if not isinstance(value, str):
            self.errors[field] = f"{label} must be text."
            return self
        value = value.strip()
        if len(value) < min_len:
            self.errors[field] = f"{label} must be at least {min_len} characters."
        elif len(value) > max_len:
            self.errors[field] = f"{label} must be at most {max_len} characters."
        else:
            self.clean[field] = value
        return self

    def integer(self, field, required=True, min_value=None, max_value=None, label=None):
        label = label or field.replace("_", " ").capitalize()
        value = self.data.get(field)
        if value is None or value == "":
            if required:
                self.errors[field] = f"{label} is required."
            else:
                self.clean[field] = None
            return self
        try:
            if isinstance(value, bool):
                raise ValueError
            number = int(value)
            if isinstance(value, float) and value != number:
                raise ValueError
        except (TypeError, ValueError):
            self.errors[field] = f"{label} must be a whole number."
            return self
        if min_value is not None and number < min_value:
            self.errors[field] = f"{label} must be at least {min_value}."
        elif max_value is not None and number > max_value:
            self.errors[field] = f"{label} must be at most {max_value}."
        else:
            self.clean[field] = number
        return self

    def boolean(self, field, default=False):
        value = self.data.get(field, default)
        if isinstance(value, str):
            value = value.lower() in ("1", "true", "yes", "on")
        self.clean[field] = bool(value)
        return self

    def choice(self, field, choices, required=True, label=None):
        label = label or field.replace("_", " ").capitalize()
        value = self.data.get(field)
        if value in (None, ""):
            if required:
                self.errors[field] = f"{label} is required."
            return self
        if value not in choices:
            self.errors[field] = f"{label} must be one of: {', '.join(choices)}."
        else:
            self.clean[field] = value
        return self

    def email(self, field="email"):
        self.string(field, max_len=255, label="Email")
        if field in self.clean:
            value = self.clean[field].lower()
            if not EMAIL_RE.match(value):
                self.errors[field] = "Enter a valid email address."
                del self.clean[field]
            else:
                self.clean[field] = value
        return self

    def phone(self, field="phone", required=False):
        self.string(field, required=required, max_len=30, label="Phone")
        value = self.clean.get(field)
        if value and not PHONE_RE.match(value):
            self.errors[field] = "Enter a valid phone number."
            del self.clean[field]
        return self

    def result(self):
        if self.errors:
            raise ApiError(400, "Please fix the highlighted fields.", self.errors)
        return self.clean


def query_int(name, default=None, min_value=None, max_value=None):
    raw = request.args.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ApiError(400, f"Query parameter '{name}' must be a number.")
    if min_value is not None:
        value = max(value, min_value)
    if max_value is not None:
        value = min(value, max_value)
    return value
