from django.contrib import admin
from aiteam.models import Feedback
from operations.services import audit


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ["id", "rating", "reviewed", "created_at"]
    list_filter = ["rating", "reviewed"]
    readonly_fields = ["user", "message", "rating", "details", "created_at"]

    def has_add_permission(self, request):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "ai.feedback.reviewed", obj)
