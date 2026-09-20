from django.contrib import admin
from accounts.models import User, Consent


@admin.register(User)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["email", "is_active", "is_staff", "email_verified_at"]
    exclude = ["password"]
    readonly_fields = ["email", "email_verified_at", "last_login", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Consent)
class ConsentAdmin(admin.ModelAdmin):
    list_display = ["user", "purpose", "version", "granted", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
