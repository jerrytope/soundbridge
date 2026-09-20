import csv
import json
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from royalties.forms import ScenarioForm, ManualIncomeForm
from royalties.scenarios import save_scenario, scenarios
from royalties.models import Calculation, ManualIncome, RoyaltyTransaction
from operations.services import audit


@login_required
@require_http_methods(["GET", "POST"])
def calculator(request):
    form = ScenarioForm(request.POST or None)
    result = None
    if request.method == "POST" and form.is_valid():
        try:
            if request.POST.get("action") == "save":
                from billing.services import EntitlementRequired, check

                try:
                    check(
                        request.user,
                        "saved_calculations",
                        Calculation.objects.filter(owner=request.user).count(),
                        "Saved royalty scenarios",
                    )
                except EntitlementRequired as limited:
                    raise ValidationError(limited.message)
                row = save_scenario(request.user, form.cleaned_data)
                return redirect(f"/royalties/calculations/{row.pk}")
            result = scenarios(form.cleaned_data)
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "royalties/scenarios.html",
        {"form": form, "result": result, "currency": form.data.get("currency", "")},
    )


@login_required
@require_http_methods(["GET", "POST"])
def calculation(request, calculation_id):
    row = get_object_or_404(Calculation, pk=calculation_id, owner=request.user)
    if request.method == "POST":
        audit(request.user, "calculation.deleted", row)
        row.delete()
        return redirect("/royalties")
    if request.GET.get("export") == "json":
        payload = {
            "id": str(row.pk),
            "platform": row.platform,
            "currency": row.currency,
            "amount": str(row.amount),
            "rate_source": row.rate_source,
            "rate_effective_date": str(row.rate_effective_date),
            "rate_version": row.rate_version,
            "formula": row.formula,
            "assumptions": row.assumptions,
        }
        response = HttpResponse(
            json.dumps(payload, indent=2), content_type="application/json"
        )
        response["Content-Disposition"] = 'attachment; filename="royalty-scenario.json"'
        response["Cache-Control"] = "no-store"
        return response
    others = Calculation.objects.filter(owner=request.user).exclude(pk=row.pk)[:50]
    compare = (
        Calculation.objects.filter(
            owner=request.user, pk=request.GET.get("compare")
        ).first()
        if request.GET.get("compare")
        else None
    )
    return render(
        request,
        "royalties/calculation.html",
        {"calculation": row, "compare": compare, "others": others},
    )


@login_required
@require_http_methods(["GET", "POST"])
def manual_income(request, income_id=None):
    row = (
        get_object_or_404(ManualIncome, pk=income_id, owner=request.user)
        if income_id
        else None
    )
    if row and request.method == "POST" and request.POST.get("action") == "delete":
        audit(request.user, "income.deleted", row)
        row.delete()
        return redirect("/royalties/income")
    form = ManualIncomeForm(request.POST or None, instance=row)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.save()
        audit(request.user, "income.saved", item)
        return redirect("/royalties/income")
    return render(
        request,
        "royalties/income.html",
        {
            "form": form,
            "item": row,
            "page_obj": Paginator(
                ManualIncome.objects.filter(owner=request.user).order_by("-date", "pk"),
                30,
            ).get_page(request.GET.get("page")),
        },
    )


@login_required
def summaries(request):
    dimensions = {
        "source": "statement__source",
        "work": "work",
        "platform": "platform",
        "territory": "territory",
        "category": "category",
        "period": "statement__period_start",
    }
    selected = request.GET.get("group", "source")
    if selected not in dimensions:
        selected = "source"
    from django.db.models import Sum

    imported = (
        RoyaltyTransaction.objects.filter(statement__owner=request.user)
        .values(dimensions[selected], "currency")
        .annotate(total=Sum("amount"))
        .order_by(dimensions[selected], "currency")
    )
    manual_dimension = {"period": "date"}.get(selected, selected)
    manual = (
        ManualIncome.objects.filter(owner=request.user)
        .values(manual_dimension, "currency")
        .annotate(total=Sum("amount"))
        .order_by(manual_dimension, "currency")
    )
    rows = [
        {
            "origin": "Statement",
            "group": row[dimensions[selected]] or "Unknown",
            "currency": row["currency"],
            "amount": row["total"],
        }
        for row in imported
    ]
    rows += [
        {
            "origin": "Manual entry",
            "group": row[manual_dimension] or "Unknown",
            "currency": row["currency"],
            "amount": row["total"],
        }
        for row in manual
    ]
    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="income-summary.csv"'
        response["Cache-Control"] = "no-store"
        writer = csv.writer(response)
        writer.writerow(["origin", selected, "currency", "amount"])
        for row in rows:
            writer.writerow(
                [
                    safe_cell(row["origin"]),
                    safe_cell(row["group"]),
                    row["currency"],
                    str(row["amount"]),
                ]
            )
        return response
    return render(
        request,
        "royalties/summary.html",
        {"rows": rows, "dimensions": dimensions, "selected": selected},
    )


def safe_cell(value):
    text = str(value)
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@")) else text


def education(request):
    return render(request, "royalties/education.html")
