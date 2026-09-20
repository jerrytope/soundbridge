from django import forms
from royalties.models import CURRENCIES, ManualIncome


class ScenarioForm(forms.Form):
    platform = forms.CharField(max_length=300)
    streams = forms.IntegerField(min_value=0, max_value=10**12)
    low_rate = forms.DecimalField(min_value=0, max_digits=18, decimal_places=8)
    midpoint_rate = forms.DecimalField(min_value=0, max_digits=18, decimal_places=8)
    high_rate = forms.DecimalField(min_value=0, max_digits=18, decimal_places=8)
    share = forms.DecimalField(
        min_value=0, max_value=100, max_digits=7, decimal_places=4, initial=100
    )
    deduction_percent = forms.DecimalField(
        min_value=0, max_value=100, max_digits=7, decimal_places=4, initial=0
    )
    tax_percent = forms.DecimalField(
        min_value=0,
        max_value=100,
        max_digits=7,
        decimal_places=4,
        required=False,
        label="Tax assumption, if known (%)",
    )
    currency = forms.ChoiceField(choices=CURRENCIES)
    market = forms.CharField(
        max_length=500, label="Selected market or territory mix assumptions"
    )
    period_start = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    period_end = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    rate_source = forms.CharField(
        max_length=200, label="Rate source (statement, agreement or research reference)"
    )
    rate_effective_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"})
    )
    rate_version = forms.CharField(max_length=40)

    def clean(self):
        data = super().clean()
        if (
            all(k in data for k in ("low_rate", "midpoint_rate", "high_rate"))
            and not data["low_rate"] <= data["midpoint_rate"] <= data["high_rate"]
        ):
            self.add_error("high_rate", "Rates must be ordered low ≤ midpoint ≤ high.")
        if (
            data.get("period_start")
            and data.get("period_end")
            and data["period_start"] > data["period_end"]
        ):
            self.add_error("period_end", "The period must end on or after its start.")
        return data


class ManualIncomeForm(forms.ModelForm):
    class Meta:
        model = ManualIncome
        exclude = ["owner", "created_at"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }
