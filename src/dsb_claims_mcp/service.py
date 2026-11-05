"""Form-detail preparation only. No eligibility inference or compensation calculation."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from .models import Dataset, Identifier, JourneyDetails
from .providers import ProviderError, TicketJourneyProvider

FORM_URL = "https://kc.dsb.dk/da-DK/webformularer/rejsetidsgaranti/soeg-dsb-basis-rejsetidsgaranti-v2/"
COPENHAGEN = ZoneInfo("Europe/Copenhagen")


class ClaimsService:
    def __init__(self, provider: TicketJourneyProvider):
        self.provider = provider

    def status(self) -> dict:
        return {
            "provider": self.provider.name,
            "mode": "read_only_preparation",
            "live_account_discovery": False,
            "historical_delay_lookup": False,
            "live_form_filling": False,
            "submission_available": False,
            "cpr_supported": False,
            "file_import_supported": False,
            "uses_network": False,
            "synthetic_by_default": self.provider.name == "demo",
            "notice": (
                "Unofficial scaffold. Tool results enter your MCP client's context. "
                "No PDFs or account exports are imported. Never enter CPR or credentials. "
                "No eligibility or compensation is inferred."
            ),
        }

    def _load(self) -> Dataset:
        return self.provider.load()

    def list_tickets(self, start_date: date | None = None, end_date: date | None = None) -> dict:
        if start_date and end_date and start_date > end_date:
            raise ProviderError("start_date must be on or before end_date")
        data = self._load()
        journey_by_id = {journey.id: journey for journey in data.journeys}
        tickets = []
        for ticket in data.tickets:
            departures = [
                journey_by_id[jid].scheduled_departure.astimezone(COPENHAGEN).date()
                for jid in ticket.journey_ids
            ]
            if start_date or end_date:
                if not any(
                    (start_date is None or d >= start_date) and (end_date is None or d <= end_date)
                    for d in departures
                ):
                    continue
            tickets.append(ticket.model_dump(mode="json"))
        return {
            "tickets": tickets,
            "provider": self.provider.name,
            "date_basis": "Journey departure date in Europe/Copenhagen; inclusive boundaries",
            "unassigned_ticket_count": sum(not t.journey_ids for t in data.tickets),
            "notice": (
                "Date filters exclude tickets with no known journey; unfiltered listing includes them"
            ),
        }

    def list_journeys(self, ticket_id: Identifier | None = None) -> dict:
        data = self._load()
        if ticket_id is not None and not any(t.id == ticket_id for t in data.tickets):
            raise ProviderError("Ticket not found in the configured data source")
        return {
            "journeys": [
                j.model_dump(mode="json")
                for j in data.journeys
                if ticket_id is None or j.ticket_id == ticket_id
            ],
            "notice": "A purchase or route alone does not establish which train the passenger took",
        }

    def get_evidence(self, journey_id: Identifier) -> dict:
        data = self._load()
        if not any(j.id == journey_id for j in data.journeys):
            raise ProviderError("Journey not found in the configured data source")
        return {
            "journey_id": journey_id,
            "evidence": [e.model_dump(mode="json") for e in data.evidence if e.journey_id == journey_id],
            "notice": (
                "Evidence adapter scaffold only. Source labels are not authenticated. "
                "No live or historical rail API is queried."
            ),
        }

    def prepare_form(
        self,
        ticket_id: Identifier,
        journey_id: Identifier | None = None,
        journey_details: JourneyDetails | None = None,
        evidence_id: Identifier | None = None,
    ) -> dict:
        data = self._load()
        ticket = next((t for t in data.tickets if t.id == ticket_id), None)
        if ticket is None:
            raise ProviderError("Ticket not found in the configured data source")
        if journey_details is not None and (journey_id is not None or evidence_id is not None):
            raise ProviderError("Provide either user journey details or stored journey/evidence IDs")
        candidates = [j for j in data.journeys if j.ticket_id == ticket.id]
        journey = next((j for j in candidates if j.id == journey_id), None) if journey_id else None
        if journey_id and journey is None:
            raise ProviderError("Journey not found for this ticket")
        # An exact bound single-ticket journey may supply times; flexible products must not.
        if journey is None and journey_details is None and ticket.product == "single":
            if len(candidates) == 1:
                journey = candidates[0]
        if evidence_id is not None and journey is None:
            raise ProviderError("Select a known journey before selecting evidence")
        fields = {"ticket_reference": ticket.ticket_reference}
        needed = []
        source = None
        evidence = None
        if journey_details is not None:
            fields.update(journey_details.model_dump(mode="json"))
            source = "user_supplied"
        elif journey is not None:
            if not journey.passenger_confirmed and ticket.product != "single":
                needed.append("confirm_actual_journey")
            fields.update(
                {
                    "origin": journey.origin,
                    "destination": journey.destination,
                    "train_number": journey.train_number,
                    "scheduled_departure": journey.scheduled_departure.isoformat(),
                    "scheduled_arrival": journey.scheduled_arrival.isoformat(),
                }
            )
            source = "account_ticket_journey"
            records = [e for e in data.evidence if e.journey_id == journey.id]
            if evidence_id:
                evidence = next((e for e in records if e.id == evidence_id), None)
                if evidence is None:
                    raise ProviderError("Evidence not found for this journey")
            elif len(records) == 1:
                evidence = records[0]
            elif len(records) > 1:
                needed.append("select_arrival_evidence")
            if evidence:
                fields["actual_arrival"] = evidence.actual_arrival.isoformat()
        else:
            needed.extend(["origin", "destination", "scheduled_departure", "scheduled_arrival"])
        if not fields.get("actual_arrival"):
            needed.append("actual_arrival")
        return {
            "status": "needs_input" if needed else "prepared_for_manual_review",
            "draft_only": True,
            "submitted": False,
            "form_filled": False,
            "synthetic": ticket.synthetic,
            "fields": fields,
            "journey_source": source,
            "evidence": evidence.model_dump(mode="json") if evidence else None,
            "missing_or_ambiguous": needed,
            "review_required": True,
            "notice": (
                "No eligibility or compensation has been inferred. Verify all details in the "
                "official form before submitting. Never submit synthetic data."
            ),
        }

    def form_handoff(
        self,
        ticket_id: Identifier,
        journey_id: Identifier | None = None,
        journey_details: JourneyDetails | None = None,
        evidence_id: Identifier | None = None,
    ) -> dict:
        draft = self.prepare_form(ticket_id, journey_id, journey_details, evidence_id)
        return {
            "official_form_url": FORM_URL,
            "form_scope": "DSB Basis Rejsetidsgaranti; the user must confirm the correct form",
            "source_checked_on": "2026-11-05",
            "form_adapter_status": "not_implemented",
            "draft": draft,
            "manual_steps": [
                "Review the ticket reference and journey details against your own records.",
                "Supply missing planned and actual times; never guess a train from a flexible ticket.",
                "Open the official form yourself and transfer the prepared details.",
                "Enter CPR, identity and banking fields only on the official site, never in this MCP.",
                "Verify every field and the official terms, then submit yourself if correct.",
                "Keep the confirmation privately. The MCP does not verify or track submission.",
            ],
            "warning": "No browser is opened, form filled, or claim submitted by this scaffold.",
        }
