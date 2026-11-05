"""Minimal normalized data contract. Never import raw account pages or identity documents."""

from __future__ import annotations

import re
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

_CPR_LIKE = re.compile(r"(?<!\d)\d{6}[- ]?\d{4}(?!\d)")
_SECRET_LIKE = re.compile(r"(?i)(bearer\s|password\s*[:=]|gh[pousr]_|sk-[a-z0-9]{16})")


def safe_text(value: str) -> str:
    """Defense in depth, not a universal PII detector. No CPR field is supported."""
    if _CPR_LIKE.search(value) or _SECRET_LIKE.search(value):
        raise ValueError("CPR-like values and credentials are not accepted")
    if any(ord(char) < 32 for char in value):
        raise ValueError("control characters are not accepted")
    return value


Identifier = Annotated[
    str,
    StringConstraints(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"),
    AfterValidator(safe_text),
]
Label = Annotated[str, StringConstraints(min_length=1, max_length=120), AfterValidator(safe_text)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Ticket(StrictModel):
    id: Identifier
    ticket_reference: Identifier
    product: Literal["single", "orange", "orange_fri", "commuter", "other"]
    purchase_channel: Literal["dsb_app", "dsb_website", "station", "other", "unknown"]
    # This is a reference, not proof that a ticket belongs to a particular account or journey.
    journey_ids: list[Identifier] = Field(default_factory=list, max_length=100)
    synthetic: bool = False


class Journey(StrictModel):
    id: Identifier
    ticket_id: Identifier
    origin: Label
    destination: Label
    train_number: Identifier | None = None
    scheduled_departure: AwareDatetime
    scheduled_arrival: AwareDatetime
    service: Literal["dsb_mainline", "s_train", "international", "other", "unknown"]
    # Unreserved tickets may require the passenger to confirm which train was taken.
    passenger_confirmed: bool = False
    synthetic: bool = False

    @model_validator(mode="after")
    def chronological(self) -> Journey:
        if self.scheduled_arrival <= self.scheduled_departure:
            raise ValueError("scheduled arrival must follow departure")
        return self


class DelayEvidence(StrictModel):
    id: Identifier
    journey_id: Identifier
    kind: Literal["passenger_report", "operator_record", "demo"]
    # Arrival at the journey's final destination, not a departure delay or intermediate stop.
    actual_arrival: AwareDatetime
    captured_at: AwareDatetime
    source_label: Label
    source_url: str | None = Field(default=None, max_length=300)
    # No arbitrary pasted text, credentials, screenshots, names, or identity fields.

    @model_validator(mode="after")
    def safe_source(self) -> DelayEvidence:
        if self.captured_at < self.actual_arrival:
            raise ValueError("evidence capture cannot precede actual arrival")
        if self.source_url is not None:
            safe_text(self.source_url)
            parts = urlsplit(self.source_url)
            if (
                parts.scheme != "https"
                or not parts.hostname
                or parts.username
                or parts.password
                or parts.query
                or parts.fragment
                or parts.port not in (None, 443)
                or parts.hostname not in {"dsb.dk", "www.dsb.dk", "labs.rejseplan.dk"}
            ):
                raise ValueError("source URL must be a public approved HTTPS URL without query")
        return self


class Dataset(StrictModel):
    schema_version: Literal[1] = 1
    tickets: list[Ticket] = Field(max_length=500)
    journeys: list[Journey] = Field(max_length=1000)
    evidence: list[DelayEvidence] = Field(max_length=2000)

    @model_validator(mode="after")
    def consistent(self) -> Dataset:
        for items in (self.tickets, self.journeys, self.evidence):
            if len({item.id for item in items}) != len(items):
                raise ValueError("duplicate identifiers are not allowed")
        tickets = {t.id: t for t in self.tickets}
        journeys = {j.id: j for j in self.journeys}
        for ticket in self.tickets:
            if len(set(ticket.journey_ids)) != len(ticket.journey_ids):
                raise ValueError("duplicate journey references are not allowed")
            for jid in ticket.journey_ids:
                if jid not in journeys or journeys[jid].ticket_id != ticket.id:
                    raise ValueError("ticket/journey references must agree")
        for journey in self.journeys:
            if journey.ticket_id not in tickets:
                raise ValueError("journey references an unknown ticket")
            if journey.id not in tickets[journey.ticket_id].journey_ids:
                raise ValueError("journey must be listed on its ticket")
            if journey.synthetic != tickets[journey.ticket_id].synthetic:
                raise ValueError("ticket and journey synthetic markers must agree")
        for evidence in self.evidence:
            if evidence.journey_id not in journeys:
                raise ValueError("evidence references an unknown journey")
            journey = journeys[evidence.journey_id]
            if evidence.actual_arrival < journey.scheduled_departure:
                raise ValueError("actual arrival cannot precede scheduled departure")
            if (evidence.kind == "demo") != journey.synthetic:
                raise ValueError("demo evidence is only valid for synthetic journeys")
        return self


class JourneyDetails(StrictModel):
    """Journey details explicitly supplied by the passenger, not guessed from a flexible ticket."""

    origin: Label
    destination: Label
    train_number: Identifier | None = None
    scheduled_departure: AwareDatetime
    scheduled_arrival: AwareDatetime
    actual_arrival: AwareDatetime | None = None

    @model_validator(mode="after")
    def chronological(self) -> JourneyDetails:
        if self.scheduled_arrival <= self.scheduled_departure:
            raise ValueError("scheduled arrival must follow departure")
        if self.actual_arrival and self.actual_arrival < self.scheduled_departure:
            raise ValueError("actual arrival cannot precede scheduled departure")
        return self
