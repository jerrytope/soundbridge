import csv
from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from royalties.models import ImportBatch, Statement
from royalties import imports
from royalties.money_views import safe_cell
from operations.services import audit


@login_required
@require_http_methods(["GET", "POST"])
def upload(request):
    error = ""
    if request.method == "POST":
        if request.POST.get("action") == "remove":
            statement = get_object_or_404(
                Statement, pk=request.POST.get("id"), owner=request.user
            )
            audit(request.user, "statement.deleted", statement)
            statement.delete()
            return redirect("/royalty-upload")
        if request.FILES.get("statement"):
            try:
                batch = imports.upload(request.user, request.FILES["statement"])
                return redirect(f"/royalties/imports/{batch.pk}")
            except ValidationError as problem:
                error = problem.messages[0]
    return render(
        request,
        "royalties/imports.html",
        {
            "error": error,
            "batches": request.user.import_batches.order_by("-created_at")[:100],
            "legacy_statements": request.user.statements.filter(
                import_batch__isnull=True
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def review(request, batch_id):
    batch = get_object_or_404(ImportBatch, pk=batch_id, owner=request.user)
    if request.method == "POST" and request.POST.get("action") == "delete":
        audit(request.user, "statement.upload.deleted", batch)
        if batch.statement_id:
            batch.statement.delete()
        else:
            batch.delete()
        return redirect("/royalty-upload")

    class MappingForm(forms.Form):
        source = forms.CharField(max_length=120)
        period_start = forms.DateField(
            required=False, widget=forms.DateInput(attrs={"type": "date"})
        )
        period_end = forms.DateField(
            required=False, widget=forms.DateInput(attrs={"type": "date"})
        )

        def clean(self):
            data = super().clean()
            if (
                data.get("period_start")
                and data.get("period_end")
                and data["period_start"] > data["period_end"]
            ):
                self.add_error("period_end", "Period ends before it starts.")
            return data

    initial = {
        **batch.mapping,
        "source": batch.statement.source if batch.statement_id else "",
    }
    if batch.statement_id:
        initial.update(
            period_start=batch.statement.period_start,
            period_end=batch.statement.period_end,
        )
    form = MappingForm(request.POST or None, initial=initial)
    for field in imports.FIELDS:
        form.fields[field] = forms.ChoiceField(
            choices=[("", "Unknown / not supplied")]
            + [(column, column) for column in batch.columns],
            required=field in imports.REQUIRED,
        )
    preview = None
    if (
        request.method == "POST"
        and batch.state in ("review", "imported")
        and form.is_valid()
    ):
        mapping = {field: form.cleaned_data[field] for field in imports.FIELDS}
        try:
            preview = imports.normalize(batch, mapping)
            if request.POST.get("action") == "confirm":
                imports.confirm(
                    request.user,
                    batch.pk,
                    mapping,
                    form.cleaned_data["source"],
                    form.cleaned_data["period_start"],
                    form.cleaned_data["period_end"],
                )
                messages.success(
                    request, "Mapping confirmed and income totals updated."
                )
                return redirect(request.path)
        except ValidationError as problem:
            form.add_error(None, problem)
    rows = batch.statement.transactions.all() if batch.statement_id else []
    return render(
        request,
        "royalties/review.html",
        {
            "batch": batch,
            "form": form,
            "preview": preview[:50] if preview else None,
            "page_obj": Paginator(rows, 50).get_page(request.GET.get("page")),
        },
    )


@login_required
def export(request, statement_id):
    statement = get_object_or_404(Statement, pk=statement_id, owner=request.user)
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="normalized-statement.csv"'
    response["Cache-Control"] = "no-store"
    writer = csv.writer(response)
    writer.writerow(["source", "period_start", "period_end"] + imports.FIELDS)
    for row in statement.transactions.all():
        writer.writerow(
            [safe_cell(statement.source), statement.period_start, statement.period_end]
            + [
                safe_cell(getattr(row, key))
                if isinstance(getattr(row, key), str)
                else getattr(row, key)
                for key in imports.FIELDS
            ]
        )
    return response
