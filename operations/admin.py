from django.contrib import admin
from .models import AuditEvent, LaunchDecision, PrivacyRequest, EmailDelivery


@admin.register(AuditEvent)
class AuditAdmin(admin.ModelAdmin):
    list_display = ["created_at", "actor", "action", "resource_type", "resource_id"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmailDelivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "attempts", "available_at", "sent_at"]
    exclude = ["body"]
    readonly_fields = ["user", "subject", "dedupe_key", "attempts", "sent_at"]

    def has_add_permission(self, request):
        return False


admin.site.register(LaunchDecision)
admin.site.register(PrivacyRequest)
