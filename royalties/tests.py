"""Royalty estimation and statement ingestion tests.

These mirror src/domain.test.js so the ported rules keep producing the same
results and the same messages.
"""

from decimal import Decimal

from django.test import TestCase

from apiv1.tests import make_user
from royalties import services
from royalties.models import Statement


class EstimateTests(TestCase):
    def test_multiplies_streams_rate_and_share(self):
        self.assertEqual(services.estimate(250000, "0.0032", 60), Decimal("480.0000"))

    def test_full_ownership(self):
        self.assertEqual(services.estimate(1000, "0.004", 100), Decimal("4.0000"))

    def test_uses_decimal_arithmetic(self):
        # 0.1 + 0.2 style drift would show here if floats were used.
        self.assertEqual(services.estimate(3, "0.1", 100), Decimal("0.3000"))

    def test_rejects_negative_streams(self):
        with self.assertRaises(services.StatementError):
            services.estimate(-1, "0.003", 100)

    def test_rejects_share_above_one_hundred(self):
        with self.assertRaises(services.StatementError):
            services.estimate(100, "0.003", 101)

    def test_rejects_non_numeric_input(self):
        with self.assertRaises(services.StatementError):
            services.estimate("many", "0.003", 100)


class StatementTests(TestCase):
    def test_normalises_supported_rows(self):
        rows = services.normalize_statement(
            services.parse_csv(
                "track,platform,amount,currency\nNight Drive,Spotify,25.50,USD\n"
            )
        )
        self.assertEqual(rows[0]["track"], "Night Drive")
        self.assertEqual(rows[0]["amount"], Decimal("25.5000"))
        self.assertEqual(rows[0]["currency"], "USD")

    def test_accepts_negative_adjustments(self):
        rows = services.normalize_statement(
            services.parse_csv(
                "track,platform,amount,currency\nOld Song,Spotify,-3.10,USD\n"
            )
        )
        self.assertEqual(rows[0]["amount"], Decimal("-3.1000"))

    def test_rejects_unsupported_currency_with_row_number(self):
        with self.assertRaises(services.StatementError) as problem:
            services.normalize_statement(
                services.parse_csv(
                    "track,platform,amount,currency\nA,Spotify,1.00,JPY\n"
                )
            )
        self.assertIn("Row 2", str(problem.exception))

    def test_rejects_missing_column(self):
        with self.assertRaises(services.StatementError):
            services.normalize_statement(
                services.parse_csv("track,platform\nA,Spotify\n")
            )

    def test_rejects_empty_file(self):
        with self.assertRaises(services.StatementError):
            services.normalize_statement(
                services.parse_csv("track,platform,amount,currency\n")
            )

    def test_fingerprint_detects_a_repeat_import(self):
        text = "track,platform,amount,currency\nA,Spotify,1.00,USD\n"
        first = services.fingerprint(
            services.normalize_statement(services.parse_csv(text))
        )
        second = services.fingerprint(
            services.normalize_statement(services.parse_csv(text))
        )
        self.assertEqual(first, second)


class SecureImportTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)

    def _batch(
        self,
        text="track,platform,amount,currency\nA,Spotify,25.50,USD\n",
        name="statement.csv",
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from royalties.imports import upload

        return upload(self.user, SimpleUploadedFile(name, text.encode()))

    def _process(self, batch):
        from unittest.mock import patch
        from royalties.imports import process

        with patch("royalties.imports.scan"):
            process(batch.pk)
        batch.refresh_from_db()
        return batch

    def test_scanner_unavailable_never_imports(self):
        from royalties.imports import process
        from django.test import override_settings

        batch = self._batch()
        with override_settings(MALWARE_SCANNER=""):
            process(batch.pk)
        batch.refresh_from_db()
        self.assertEqual(batch.state, "quarantined")
        self.assertFalse(Statement.objects.exists())
        self.assertIn("scanner", batch.error)

    def test_review_and_confirmation_keep_currencies_separate(self):
        from royalties.imports import confirm

        batch = self._process(
            self._batch(
                "track,platform,amount,currency\nA,Spotify,25.50,USD\nB,Boomplay,-3.10,NGN\n"
            )
        )
        self.assertEqual(batch.state, "review")
        self.assertFalse(Statement.objects.exists())
        statement = confirm(
            self.user, batch.pk, batch.mapping, "Distributor", None, None
        )
        confirm(self.user, batch.pk, batch.mapping, "Distributor", None, None)
        self.assertEqual(statement.transactions.count(), 2)
        self.assertEqual(
            statement.totals(), {"USD": Decimal("25.5000"), "NGN": Decimal("-3.1000")}
        )
        self.assertIn(b"track,platform", bytes(statement.original_csv))

    def test_duplicate_filename_change_is_refused(self):
        from django.core.exceptions import ValidationError

        self._batch()
        with self.assertRaises(ValidationError):
            self._batch(name="renamed.csv")

    def test_bad_row_and_unknown_fields(self):
        from royalties.imports import normalize
        from django.core.exceptions import ValidationError

        batch = self._process(
            self._batch("track,platform,amount,currency\nA,Spotify,NaN,USD\n")
        )
        with self.assertRaisesMessage(ValidationError, "Row 2"):
            normalize(batch, batch.mapping)

    def test_correction_and_deletion_reconcile_totals(self):
        from royalties.imports import confirm

        batch = self._process(
            self._batch("track,platform,amount,net,currency\nA,Spotify,25,20,USD\n")
        )
        statement = confirm(
            self.user, batch.pk, batch.mapping, "Distributor", None, None
        )
        mapping = {**batch.mapping, "amount": "net"}
        confirm(self.user, batch.pk, mapping, "Distributor", None, None)
        self.assertEqual(statement.totals()["USD"], Decimal("20.0000"))
        self.assertEqual(batch.revisions.count(), 2)
        self.client.post(f"/royalties/imports/{batch.pk}", {"action": "delete"})
        self.assertFalse(Statement.objects.exists())
        self.assertFalse(self.user.import_batches.exists())

    def test_foreign_account_cannot_review_or_export(self):
        from royalties.imports import confirm

        batch = self._process(self._batch())
        row = confirm(self.user, batch.pk, batch.mapping, "Distributor", None, None)
        self.client.force_login(make_user("other@example.com"))
        self.assertEqual(
            self.client.get(f"/royalties/imports/{batch.pk}").status_code, 404
        )
        self.assertEqual(
            self.client.get(f"/royalties/statements/{row.pk}/export").status_code, 404
        )


class CalculatorViewTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_login(self.user)
        self.data = {
            "platform": "Spotify",
            "streams": "1000",
            "low_rate": "0.002",
            "midpoint_rate": "0.003",
            "high_rate": "0.004",
            "share": "50",
            "deduction_percent": "10",
            "tax_percent": "20",
            "currency": "USD",
            "market": "Nigeria",
            "period_start": "2026-01-01",
            "period_end": "2026-01-31",
            "rate_source": "My statement",
            "rate_effective_date": "2026-01-01",
            "rate_version": "statement-1",
        }

    def test_saves_versioned_range_and_breakdown(self):
        response = self.client.post(
            "/royalty-calculator", {**self.data, "action": "save"}
        )
        self.assertEqual(response.status_code, 302)
        row = self.user.calculations.get()
        self.assertEqual(row.amount, Decimal("1.0800"))
        self.assertEqual(row.assumptions["scenarios"]["low"]["amount"], "0.7200")
        self.assertEqual(row.assumptions["scenarios"]["high"]["amount"], "1.4400")
        self.assertEqual(row.rate_source, "My statement")
        self.assertEqual(str(row.rate_effective_date), "2026-01-01")
        self.assertEqual(
            self.client.get(
                f"/royalties/calculations/{row.pk}?export=json"
            ).status_code,
            200,
        )

    def test_order_and_finite_validation(self):
        for value in ["NaN", "Infinity", "0.001"]:
            response = self.client.post(
                "/royalty-calculator",
                {**self.data, "high_rate": value, "action": "save"},
            )
            self.assertEqual(response.status_code, 200)
            self.assertFalse(self.user.calculations.exists())

    def test_estimate_does_not_enter_actual_income(self):
        self.client.post("/royalty-calculator", {**self.data, "action": "save"})
        self.assertEqual(services.totals(list(self.user.statements.all())), {})
