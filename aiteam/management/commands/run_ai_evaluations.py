from django.core.management.base import BaseCommand, CommandError
from aiteam.evaluations import EvaluationsUnavailable, run


class Command(BaseCommand):
    help = (
        "Run the active AI evaluation cases against the configured model. "
        "This calls the provider and costs money, so run it deliberately."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--fail-on-regression",
            action="store_true",
            help="Exit non-zero when any case fails, for use in a release gate.",
        )

    def handle(self, **options):
        try:
            result = run()
        except EvaluationsUnavailable as problem:
            raise CommandError(str(problem))
        for row in result.results.select_related("case"):
            mark = "PASS" if row.passed else "FAIL"
            self.stdout.write(f"{mark} {row.case.slug} {row.detail}".rstrip())
        summary = f"{result.passed} passed, {result.failed} failed, model {result.model}, prompts {result.prompt_version}."
        if result.failed and options["fail_on_regression"]:
            raise CommandError(summary)
        self.stdout.write(self.style.SUCCESS(summary))
