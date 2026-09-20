from django.db import migrations


def mark_samples(apps, schema_editor):
    Opportunity = apps.get_model("network", "Opportunity")
    Opportunity.objects.filter(
        slug__in=["sync", "writing", "live"], verification_state="unverified"
    ).update(is_sample=True)


class Migration(migrations.Migration):
    dependencies = [("network", "0004_opportunity_is_sample_and_more")]
    operations = [migrations.RunPython(mark_samples, migrations.RunPython.noop)]
