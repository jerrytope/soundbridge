from django.contrib import admin
from django import forms
from billing.models import Plan, Subscription, BillingEvent
from operations.services import audit


class PlanForm(forms.ModelForm):
    class Meta:
        model = Plan
        fields = "__all__"

    def clean_limits(self):
        value = self.cleaned_data["limits"]
        if not isinstance(value, dict) or any(
            not isinstance(v, int) or isinstance(v, bool) or v < 0
            for v in value.values()
        ):
            raise forms.ValidationError(
                "Limits must be a JSON object of nonnegative integers."
            )
        return value

    def clean(self):
        data = super().clean()
        if data.get("approved_at") and not data.get("commercial_terms"):
            self.add_error(
                "commercial_terms", "Record approved terms before approving the plan."
            )
        return data


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    form = PlanForm
    list_display = ["code", "name", "approved_at"]

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("billing.approve_plan")

    def has_add_permission(self, request):
        return request.user.has_perm("billing.approve_plan")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        audit(request.user, "billing.plan.updated", obj)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Subscription, ReadOnlyAdmin)
admin.site.register(BillingEvent, ReadOnlyAdmin)
