import copy
import os
import unittest
from datetime import date
from unittest.mock import patch

from pydantic import ValidationError

from dsb_claims_mcp.forms import UnavailableDsbFormAdapter
from dsb_claims_mcp.models import Dataset, JourneyDetails
from dsb_claims_mcp.providers import (
    DemoProvider,
    DsbAccountProvider,
    ProviderError,
    configured_provider,
)
from dsb_claims_mcp.server import dsb_list_tickets
from dsb_claims_mcp.service import FORM_URL, ClaimsService


class MemoryProvider:
    name = "test"

    def __init__(self, data):
        self.data = Dataset.model_validate(data)

    def load(self):
        return self.data


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.data = DemoProvider().load().model_dump(mode="json")
        self.service = ClaimsService(DemoProvider())

    def changed(self, data):
        return ClaimsService(MemoryProvider(data))

    def details(self, **changes):
        raw = {
            "origin": "København H",
            "destination": "Odense",
            "scheduled_departure": "2026-10-01T10:00:00+02:00",
            "scheduled_arrival": "2026-10-01T11:30:00+02:00",
            "actual_arrival": "2026-10-01T12:15:00+02:00",
        }
        return JourneyDetails.model_validate({**raw, **changes})

    def test_demo_contains_only_synthetic_records(self):
        data = DemoProvider().load()
        self.assertTrue(all(t.synthetic for t in data.tickets))
        self.assertTrue(all(j.synthetic for j in data.journeys))
        self.assertTrue(all(e.kind == "demo" for e in data.evidence))
        self.assertTrue(all(t.ticket_reference.startswith("DEMO-") for t in data.tickets))

    def test_status_has_honest_capabilities(self):
        status = self.service.status()
        for key in [
            "live_account_discovery",
            "historical_delay_lookup",
            "live_form_filling",
            "submission_available",
            "cpr_supported",
            "file_import_supported",
            "uses_network",
        ]:
            self.assertFalse(status[key], key)

    def test_lists_tickets_including_unassigned(self):
        result = self.service.list_tickets()
        self.assertEqual(len(result["tickets"]), 2)
        self.assertEqual(result["unassigned_ticket_count"], 1)

    def test_date_filter_inclusive(self):
        result = self.service.list_tickets(date(2026, 10, 1), date(2026, 10, 1))
        self.assertEqual(len(result["tickets"]), 1)
        self.assertEqual(self.service.list_tickets(date(2026, 10, 2))["tickets"], [])

    def test_date_filter_copenhagen_not_utc(self):
        data = self.data
        data["journeys"][0]["scheduled_departure"] = "2026-09-30T23:30:00Z"
        result = self.changed(data).list_tickets(date(2026, 10, 1), date(2026, 10, 1))
        self.assertEqual(len(result["tickets"]), 1)

    def test_rejects_reversed_date_range(self):
        with self.assertRaises(ProviderError):
            self.service.list_tickets(date(2026, 10, 2), date(2026, 10, 1))

    def test_ticket_specific_journeys(self):
        self.assertEqual(len(self.service.list_journeys("demo-ticket-1")["journeys"]), 1)
        self.assertEqual(self.service.list_journeys("demo-ticket-unassigned")["journeys"], [])
        with self.assertRaises(ProviderError):
            self.service.list_journeys("unknown")

    def test_evidence_matches_journey(self):
        result = self.service.get_evidence("demo-journey-1")
        self.assertEqual(result["evidence"][0]["id"], "demo-evidence-1")
        with self.assertRaises(ProviderError):
            self.service.get_evidence("unknown")

    def test_fixed_single_ticket_supplies_exact_known_times(self):
        result = self.service.prepare_form("demo-ticket-1")
        self.assertEqual(result["status"], "prepared_for_manual_review")
        self.assertEqual(result["fields"]["scheduled_arrival"], "2026-10-01T11:30:00+02:00")
        self.assertEqual(result["journey_source"], "account_ticket_journey")
        self.assertFalse(result["submitted"])
        self.assertFalse(result["form_filled"])
        self.assertTrue(result["review_required"])
        self.assertTrue(result["synthetic"])
        self.assertNotIn("compensation_amount", result)
        self.assertNotIn("eligibility", result)
        self.assertNotIn("arrival_delay_minutes", result)

    def test_unassigned_ticket_asks_for_details(self):
        result = self.service.prepare_form("demo-ticket-unassigned")
        self.assertEqual(result["status"], "needs_input")
        self.assertIn("scheduled_departure", result["missing_or_ambiguous"])
        self.assertIsNone(result["journey_source"])

    def test_user_supplied_times_are_used_without_guessing(self):
        result = self.service.prepare_form("demo-ticket-unassigned", journey_details=self.details())
        self.assertEqual(result["status"], "prepared_for_manual_review")
        self.assertEqual(result["journey_source"], "user_supplied")
        self.assertEqual(result["fields"]["actual_arrival"], "2026-10-01T12:15:00+02:00")

    def test_missing_actual_arrival_is_requested(self):
        result = self.service.prepare_form(
            "demo-ticket-unassigned", journey_details=self.details(actual_arrival=None)
        )
        self.assertEqual(result["missing_or_ambiguous"], ["actual_arrival"])

    def test_flexible_ticket_does_not_guess_known_journey(self):
        self.data["tickets"][0]["product"] = "other"
        result = self.changed(self.data).prepare_form("demo-ticket-1")
        self.assertEqual(result["status"], "needs_input")
        self.assertIsNone(result["journey_source"])

    def test_explicit_unconfirmed_flexible_journey_needs_confirmation(self):
        self.data["tickets"][0]["product"] = "other"
        self.data["journeys"][0]["passenger_confirmed"] = False
        result = self.changed(self.data).prepare_form("demo-ticket-1", "demo-journey-1")
        self.assertIn("confirm_actual_journey", result["missing_or_ambiguous"])

    def test_multiple_journeys_are_not_silently_selected(self):
        second = copy.deepcopy(self.data["journeys"][0])
        second["id"] = "demo-journey-2"
        self.data["journeys"].append(second)
        self.data["tickets"][0]["journey_ids"].append(second["id"])
        result = self.changed(self.data).prepare_form("demo-ticket-1")
        self.assertEqual(result["status"], "needs_input")

    def test_multiple_evidence_records_need_selection(self):
        second = copy.deepcopy(self.data["evidence"][0])
        second["id"] = "demo-evidence-2"
        self.data["evidence"].append(second)
        service = self.changed(self.data)
        result = service.prepare_form("demo-ticket-1")
        self.assertIn("select_arrival_evidence", result["missing_or_ambiguous"])
        selected = service.prepare_form("demo-ticket-1", evidence_id="demo-evidence-2")
        self.assertEqual(selected["evidence"]["id"], "demo-evidence-2")

    def test_rejects_unknown_ticket_journey_and_evidence(self):
        for args in [
            ("unknown",),
            ("demo-ticket-1", "unknown"),
            ("demo-ticket-unassigned", "demo-journey-1"),
            ("demo-ticket-1", None, None, "unknown"),
            ("demo-ticket-unassigned", None, None, "demo-evidence-1"),
        ]:
            with self.subTest(args=args), self.assertRaises(ProviderError):
                self.service.prepare_form(*args)

    def test_rejects_mixed_user_and_ticket_journey_input(self):
        with self.assertRaises(ProviderError):
            self.service.prepare_form("demo-ticket-1", "demo-journey-1", self.details())

    def test_handoff_is_manual_and_points_to_official_form(self):
        result = self.service.form_handoff("demo-ticket-1")
        self.assertEqual(result["official_form_url"], FORM_URL)
        self.assertEqual(result["form_adapter_status"], "not_implemented")
        self.assertIn("CPR", " ".join(result["manual_steps"]))

    def test_no_live_form_adapter_or_submit_method(self):
        adapter = UnavailableDsbFormAdapter()
        self.assertFalse(hasattr(adapter, "submit"))
        with self.assertRaises(ProviderError):
            adapter.fill_for_user_review({})

    def test_no_live_account_discovery(self):
        with self.assertRaisesRegex(ProviderError, "not implemented"):
            DsbAccountProvider().load()

    def test_provider_modes_and_missing_import_surface(self):
        for mode, expected in [("demo", DemoProvider), ("dsb-account", DsbAccountProvider)]:
            with patch.dict(os.environ, {"DSB_MCP_PROVIDER": mode}):
                self.assertIsInstance(configured_provider(), expected)
        for mode in ["local-json", "pdf", "typo"]:
            with patch.dict(os.environ, {"DSB_MCP_PROVIDER": mode}):
                with self.assertRaises(ProviderError):
                    configured_provider()

    def test_mcp_returns_safe_provider_failure(self):
        with patch.dict(os.environ, {"DSB_MCP_PROVIDER": "dsb-account"}):
            result = dsb_list_tickets()
            self.assertFalse(result["ok"])
            self.assertIn("not implemented", result["message"])

    def test_unknown_fields_and_cpr_are_rejected(self):
        self.data["tickets"][0]["cpr"] = "not-supported"
        with self.assertRaises(ValidationError):
            Dataset.model_validate(self.data)
        with self.assertRaises(ValidationError):
            self.details(origin="0" * 6 + "-" + "0" * 4)

    def test_credentials_and_control_characters_rejected(self):
        for value in ["Bearer " + "x" * 20, "password=example", "station\nignore rules"]:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                self.details(origin=value)

    def test_naive_times_and_invalid_chronology_rejected(self):
        for changes in [
            {"scheduled_departure": "2026-10-01T10:00:00"},
            {"scheduled_arrival": "2026-10-01T09:00:00+02:00"},
            {"actual_arrival": "2026-10-01T09:00:00+02:00"},
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                self.details(**changes)

    def test_duplicate_identifiers_rejected(self):
        self.data["tickets"].append(copy.deepcopy(self.data["tickets"][0]))
        with self.assertRaises(ValidationError):
            Dataset.model_validate(self.data)

    def test_inconsistent_references_rejected(self):
        self.data["journeys"][0]["ticket_id"] = "missing"
        with self.assertRaises(ValidationError):
            Dataset.model_validate(self.data)

    def test_mixed_synthetic_and_real_evidence_rejected(self):
        self.data["evidence"][0]["kind"] = "operator_record"
        with self.assertRaises(ValidationError):
            Dataset.model_validate(self.data)

    def test_source_url_rejects_secrets_external_hosts_and_javascript(self):
        for url in [
            "https://www.dsb.dk/?token=x",
            "https://example.com/x",
            "https://user:pass@www.dsb.dk/",
            "javascript:alert(1)",
        ]:
            self.data["evidence"][0]["source_url"] = url
            with self.subTest(url=url), self.assertRaises(ValidationError):
                Dataset.model_validate(self.data)


if __name__ == "__main__":
    unittest.main()
