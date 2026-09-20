from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from releases.models import ReleaseProject, ReleaseTask
from operations.services import audit

METADATA = [
    "track_titles",
    "artist_names",
    "credits",
    "identifiers",
    "rights_and_splits",
    "artwork",
    "explicit_content",
    "delivery_requirements",
]


class ReleaseForm(forms.ModelForm):
    needs = forms.CharField(
        max_length=1000, required=False, label="Support needs (comma separated)"
    )

    class Meta:
        model = ReleaseProject
        fields = [
            "title",
            "type",
            "date",
            "stage",
            "campaign_plan",
            "reminders_enabled",
        ]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "campaign_plan": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["needs"].initial = ", ".join(self.instance.support_needs)
        for key in METADATA:
            self.fields[key] = forms.BooleanField(
                required=False,
                initial=self.instance.metadata_ready.get(key, False),
                label=key.replace("_", " ").title(),
            )

    def save(self, commit=True):
        self.instance.support_needs = [
            value.strip()
            for value in self.cleaned_data["needs"].split(",")
            if value.strip()
        ]
        self.instance.metadata_ready = {key: self.cleaned_data[key] for key in METADATA}
        return super().save(commit)


class TaskForm(forms.ModelForm):
    class Meta:
        model = ReleaseTask
        fields = ["title", "assignee", "due_date", "done"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}


@login_required
@require_http_methods(["GET", "POST"])
def detail(request, release_id):
    project = get_object_or_404(ReleaseProject, pk=release_id, owner=request.user)
    form = ReleaseForm(request.POST or None, instance=project)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, "release.updated", project)
        return redirect(request.path)
    return render(request, "releases/detail.html", {"form": form, "release": project})


@login_required
@require_http_methods(["GET", "POST"])
def task(request, task_id):
    item = get_object_or_404(ReleaseTask, pk=task_id, release__owner=request.user)
    form = TaskForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request.user, "release.task.updated", item)
        return redirect(f"/releases/{item.release_id}")
    return render(request, "form.html", {"form": form, "title": "Edit release task"})
