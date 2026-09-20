from django.contrib import admin
from django import forms
from django.utils import timezone
from network.models import Report, Opportunity
from operations.services import audit


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["id", "created_at", "state", "target_user", "opportunity"]
    readonly_fields = ["reporter", "target_user", "opportunity", "collaboration_message", "reason", "created_at"]
    list_filter = ["state"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "report.reviewed", obj)

    def has_add_permission(self, request):
        return False


class OpportunityForm(forms.ModelForm):
    class Meta:
        model = Opportunity
        fields = "__all__"

    def clean(self):
        data = super().clean()
        if data.get("verification_state") == "verified":
            for key in (
                "source",
                "city",
                "eligibility",
                "deadline",
                "cost",
                "url",
                "verification_evidence",
            ):
                if not data.get(key):
                    self.add_error(
                        key, "Required before marking an opportunity verified."
                    )
            if data.get("is_sample"):
                self.add_error("is_sample", "Sample records cannot be verified.")
        if data.get("url") and not data["url"].startswith(("https://", "http://")):
            self.add_error("url", "Use an HTTP or HTTPS application URL.")
        return data


@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    form = OpportunityForm
    readonly_fields = ["verified_at", "verified_by"]
    list_display = ["title", "verification_state", "deadline"]
    list_filter = ["verification_state"]

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if obj.verification_state == "verified":
            obj.verified_at = timezone.now()
            obj.verified_by = request.user
            obj.save(update_fields=["verified_at", "verified_by"])
        audit(request.user, "opportunity.reviewed", obj)
