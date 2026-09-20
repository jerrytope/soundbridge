from decimal import Decimal, localcontext
from django.core.exceptions import ValidationError
from royalties.models import Calculation
from operations.services import audit

FORMULA = "gross=streams*rate; net=gross*(1-deduction/100); share=net*ownership/100; after_tax=share*(1-tax/100)"


def scenarios(data):
    result = {}
    with localcontext() as context:
        context.prec = 48
        for name in ("low", "midpoint", "high"):
            gross = Decimal(data["streams"]) * data[name + "_rate"]
            deduction = gross * data["deduction_percent"] / 100
            share = (gross - deduction) * data["share"] / 100
            tax = share * (data.get("tax_percent") or Decimal(0)) / 100
            if gross > Decimal("99999999999999.9999"):
                raise ValidationError("The estimate is too large.")
            result[name] = {
                key: format(value.quantize(Decimal(".0001")), "f")
                for key, value in {
                    "gross": gross,
                    "deductions": deduction,
                    "user_share_before_tax": share,
                    "tax": tax,
                    "amount": share - tax,
                }.items()
            }
    return result


def save_scenario(user, data):
    result = scenarios(data)
    inputs = {
        key: str(value)
        if isinstance(value, Decimal) or hasattr(value, "isoformat")
        else value
        for key, value in data.items()
    }
    row = Calculation.objects.create(
        owner=user,
        platform=data["platform"],
        streams=data["streams"],
        rate=data["midpoint_rate"],
        share=data["share"],
        currency=data["currency"],
        amount=result["midpoint"]["amount"],
        rate_source=data["rate_source"],
        rate_effective_date=data["rate_effective_date"],
        rate_version=data["rate_version"],
        formula=FORMULA,
        assumptions={
            "inputs": inputs,
            "scenarios": result,
            "excludes": "Composition royalties and any unentered contractual terms or taxes.",
            "exchange": "No currency conversion applied. All entered rates use the selected currency.",
            "source_type": "creator-supplied",
        },
    )
    audit(user, "calculation.saved", row)
    return row
