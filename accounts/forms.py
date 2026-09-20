from django import forms
from accounts.models import CreatorProfile, Credit, ProfileLink
from accounts.security import verified


class ProfileForm(forms.ModelForm):
    skills_text = forms.CharField(
        required=False, max_length=500, label="Skills (comma separated)"
    )

    class Meta:
        model = CreatorProfile
        fields = [
            "name",
            "username",
            "role",
            "country",
            "city",
            "bio",
            "portfolio",
            "availability",
            "city_public",
            "portfolio_public",
            "photo_public",
            "availability_public",
            "published",
        ]
        labels = {
            "published": "Publish my profile",
            "photo_public": "Show my photo publicly",
        }
        widgets = {"bio": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["skills_text"].initial = ", ".join(self.instance.skills)

    def clean_username(self):
        name = (self.cleaned_data.get("username") or "").lower()
        return name or None

    def clean(self):
        values = super().clean()
        skills = [
            v.strip() for v in values.get("skills_text", "").split(",") if v.strip()
        ]
        if len(skills) > 20:
            self.add_error("skills_text", "Use at most 20 skills.")
        if values.get("published"):
            for key in ("name", "username", "role", "country", "bio"):
                if not values.get(key):
                    self.add_error(key, "Required to publish your profile.")
            if not skills and not self.instance.genres:
                self.add_error(
                    "skills_text", "Add at least one genre or skill before publishing."
                )
            if not verified(self.instance.user):
                self.add_error("published", "Verify your email before publishing.")
        self.instance.skills = skills
        return values


class CreditForm(forms.ModelForm):
    class Meta:
        model = Credit
        fields = ["work", "role", "source", "date"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class ProfileLinkForm(forms.ModelForm):
    class Meta:
        model = ProfileLink
        fields = ["title", "url", "public"]
