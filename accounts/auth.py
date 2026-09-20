"""Email/password authentication backend.

Mirrors server/backend.js: the email is normalised, a missing account still
performs a hash comparison so timing does not reveal whether an address is
registered, and the single error message never distinguishes the two cases.
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.hashers import make_password

_DUMMY = make_password("unusable-comparison-password")


class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        if not email or not password:
            return None
        User = get_user_model()
        try:
            user = User.objects.get(email=email.strip().lower())
        except User.DoesNotExist:
            from django.contrib.auth.hashers import check_password

            check_password(password, _DUMMY)
            return None
        if not user.is_active or not user.check_password(password):
            return None
        return user

    def get_user(self, user_id):
        User = get_user_model()
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except (User.DoesNotExist, ValueError):
            return None
