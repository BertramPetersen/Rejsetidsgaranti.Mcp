# Laptop handoff

## 1. Scope and current truth

Build a personal-assistant MCP workflow that discovers the passenger's DSB-account tickets, prepares the relevant journey details, fills the official form, and stops with the passenger for review.

The scope deliberately excludes PDF import, email import, account-export import, compensation estimation, eligibility decisions, automated submission, and CPR handling. A ticket with an exact one-way journey may provide planned times. A flexible ticket or incomplete record must lead to a question to the passenger.

**Implemented now**

- Installable Python package and stdio MCP server, using the official MCP Python SDK.
- Six read-only tools with structured results and read-only annotations.
- Provider boundary for ticket/journey discovery; synthetic demo provider.
- Strict normalized ticket, journey, evidence, and passenger-supplied journey models.
- Explicit missing-input responses rather than guessed planned times.
- User-supplied planned/actual times for tickets without a bound journey.
- Deterministic field preparation, an official form link, and final-review checklist.
- Unit tests, actual stdio transport smoke test, lint configuration, publication guard, CI.

**Not implemented or verified**

- DSB login, account ticket listing, historical journey discovery, account session management.
- A live delay API or historical evidence retrieval.
- Browser navigation, real form control mapping, field entry, or persistence across a browser handoff.
- Claim submission or submission tracking. These are deliberately outside the tool surface.
- An entitlement or payout engine. This is deliberately outside the product scope.

Do not describe `dsb-account` as working or a prepared field dictionary as a filled form. Capability flags make this distinction explicit.

## 2. Install and reproduce on a laptop

### Recommended: uv

Install Python 3.11+ and uv from their official sources. Then:

```bash
git clone https://github.com/BertramPetersen/Rejsetidsgaranti.Mcp.git
cd Rejsetidsgaranti.Mcp
uv sync --frozen --extra dev
uv run ruff check .
uv run python -m unittest discover -s tests -v
uv run python scripts/smoke_mcp.py
uv run python scripts/check_public_safety.py
```

Use the committed lockfile so dependency resolution is reproducible. Run `uv lock --upgrade` only as an intentional dependency update, then rerun every check.

### Alternative: standard Python virtual environment

macOS/Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m unittest discover -s tests -v
python scripts/smoke_mcp.py
ruff check .
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m unittest discover -s tests -v
python scripts/smoke_mcp.py
ruff check .
```

The pip path resolves dependency ranges from `pyproject.toml`; it does not consume `uv.lock`. Use uv for exact dependency versions. If PowerShell activation is restricted, call `.venv\Scripts\python.exe` directly rather than changing machine security policy.

## 3. Connect a local MCP client

This server supports **stdio only**. It is not a hosted HTTP connector. Use a client that can launch a local subprocess. Client configuration formats vary; this is the common `mcpServers` JSON shape:

```json
{
  "mcpServers": {
    "dsb-claims": {
      "command": "/absolute/path/to/Rejsetidsgaranti.Mcp/.venv/bin/python",
      "args": ["-m", "dsb_claims_mcp.server"],
      "env": {"DSB_MCP_PROVIDER": "demo"}
    }
  }
}
```

On Windows, use the absolute `.venv\\Scripts\\python.exe` path, with JSON backslashes escaped. Install the package first so the client does not depend on its working directory. Prefer an absolute executable path; GUI applications may not inherit your terminal's PATH.

For a client whose configuration uses TOML, the same subprocess details are:

```toml
[mcp_servers.dsb_claims]
command = "/absolute/path/to/Rejsetidsgaranti.Mcp/.venv/bin/python"
args = ["-m", "dsb_claims_mcp.server"]

[mcp_servers.dsb_claims.env]
DSB_MCP_PROVIDER = "demo"
```

Consult your installed client's current configuration docs before editing its settings. No credentials are required for the demo. `.env.example` is documentation only; the package does not automatically load `.env`.

### Deterministic test conversation

1. “Call dsb_status and tell me which features are live.” Expect false for live account discovery, history lookup, form filling, and submission.
2. “List my demo tickets.” Expect `demo-ticket-1` and `demo-ticket-unassigned`, both synthetic.
3. “Prepare the form for demo-ticket-1.” Expect planned departure `2026-10-01T10:00:00+02:00`, planned arrival `2026-10-01T11:30:00+02:00`, actual arrival `2026-10-01T12:15:00+02:00`, `form_filled=false`, and `submitted=false`. No compensation estimate.
4. “Prepare the form for demo-ticket-unassigned.” Expect `needs_input`, including planned departure/arrival and actual arrival. The assistant should ask, not invent times.
5. Supply the synthetic journey fields shown below and prepare again. Expect `journey_source=user_supplied` and `prepared_for_manual_review`.
6. “Give me the handoff.” Expect the official DSB form link and a clear statement that it is not filled. **Do not submit the synthetic example.**

Exact tool arguments for step 5:

```json
{
  "ticket_id": "demo-ticket-unassigned",
  "journey_details": {
    "origin": "København H",
    "destination": "Odense",
    "scheduled_departure": "2026-10-01T10:00:00+02:00",
    "scheduled_arrival": "2026-10-01T11:30:00+02:00",
    "actual_arrival": "2026-10-01T12:15:00+02:00"
  }
}
```

`missing_or_ambiguous` is an application-level request for input. This scaffold does not yet send MCP protocol-level elicitation requests. The MCP client/assistant should ask the passenger and call the tool again with `journey_details`.

### Test the honest failure path

Set `DSB_MCP_PROVIDER=dsb-account` in your client config and restart the server. `dsb_status` will report the selected provider but false live capabilities. `dsb_list_tickets` will return `ok=false`, `source_unavailable_or_invalid`, and an explanation that authorized account access is not implemented. This is expected. Revert to `demo` for further development.

## 4. Repository map

- `src/dsb_claims_mcp/models.py`: bounded Pydantic data models and cross-record validation.
- `src/dsb_claims_mcp/providers.py`: `TicketJourneyProvider`, working `DemoProvider`, unavailable `DsbAccountProvider`.
- `src/dsb_claims_mcp/service.py`: ticket filtering, journey/evidence selection, fields, missing-input output, manual handoff.
- `src/dsb_claims_mcp/server.py`: public MCP tool signatures, read-only annotations, safe provider errors, stdio entry point.
- `src/dsb_claims_mcp/forms.py`: future `ClaimFormAdapter` contract and explicit unavailable implementation. There is no submit operation.
- `src/dsb_claims_mcp/data/demo.json`: entirely synthetic ticket/journey/evidence fixtures, packaged in the wheel. This is not an import feature.
- `tests/test_workflow.py`: domain, privacy, ambiguity, provider, and form-boundary tests.
- `scripts/smoke_mcp.py`: a real MCP client starts a server subprocess, initializes, lists tools, and calls the entire synthetic workflow.
- `scripts/check_public_safety.py`: tracked-file publication guard; not a comprehensive secret scanner.
- `.github/workflows/ci.yml`: lint, unit, protocol smoke, and publication checks on Python 3.11/3.12/3.13.
- `docs/SOURCES.md`: official links and what is/is not established.
- `SECURITY.md`: data boundaries and privacy cautions.

## 5. Implementation sequence on the laptop

### A. Establish the permitted account-access route first

1. Read current DSB website and DSB Plus terms. A browser login alone is not permission for systematic extraction.
2. Determine whether DSB offers a documented API, approved integration, or explicit consent suitable for this account-specific workflow. No such public API was verified during scaffolding.
3. Verify what the signed-in website actually exposes for each purchase channel. A DSB account does not necessarily expose every ticket bought in the app, website, station, or another retailer.
4. If no authorized route exists, keep `DsbAccountProvider` unavailable. Do not work around it by scraping hidden endpoints, automating anti-bot challenges, or adding PDF/import fallbacks against product scope.
5. Keep any account exploration manual until automation permission is established. Never commit HARs, session storage, cookies, passwords, real tickets, or screenshots.

### B. Implement `DsbAccountProvider`

Once access is authorized, return a normalized `Dataset` and preserve source/channel limitations. Start with read-only listing and explicit user initiation. Avoid background polling.

Required behaviors:

- Auth failures are clear and do not fall back to demo data.
- Account mismatch, expired session, empty ticket history, duplicate tickets, and channel gaps are distinguishable.
- References stay linked to the correct ticket and journey.
- A “single” ticket may auto-select one exact bound journey. Do not manufacture a train or timetable from a ticket that is flexible or incomplete.
- If records omit planned times, return no bound journey and let `journey_details` collect the missing information. The current `Journey` model intentionally requires complete planned times.
- Don't set `passenger_confirmed=true` based merely on purchase history.
- Mark all genuine records `synthetic=false`. Never mix demo and real evidence.
- Never expose credentials or identity fields in tool results. Live tool output still shares ticket/journey data with the selected MCP client and possibly its model provider.
- Add provider tests using redacted or invented responses, never real account dumps.

The current aggregate `Dataset` load is deliberately simple. Production work should add bounded pagination, stable references, retry limits, explicit freshness, and typed availability errors if the approved interface needs them. Enforce the privacy boundary before parsing or retaining raw account responses.

### C. Planned times and arrival evidence

Use exact ticket-bound planned times where available; otherwise ask the passenger for date, departure/arrival stations, planned departure/arrival, and actual arrival. Time values must include offsets. Ticket-date filtering uses `Europe/Copenhagen`.

No historical rail API is implemented. The referenced Rejseplanen documentation says historical data is not exposed; a present-time journey-planner result is not proof of an old delay. Future evidence adapters must preserve provenance and what they actually establish. Do not silently choose among conflicting records. Passenger-supplied actual arrival is allowed as a statement to review, not authenticated operator proof.

Do not add eligibility thresholds, estimated compensation, or payout recommendations. The output is the factual form detail set, for the user to verify.

### D. Implement browser form filling with a review checkpoint

The current output is a semantic field dictionary, not a DOM selector map. Do not infer selectors from its keys.

1. Inspect the current official form manually in a local browser, without entering identity data into development logs.
2. Map stable, observed controls for ticket reference, stations, journey date, planned times, and actual arrival. Handle the official form's required format and its localization explicitly.
3. Implement `ClaimFormAdapter.fill_for_user_review` using only that verified mapping. Require the expected official origin, current form version, and reviewed non-sensitive fields.
4. Refuse synthetic data for any live form. Refuse ambiguous/missing fields instead of filling guesses.
5. Do not read or fill CPR, bank details, passwords, or identity documents through the MCP. Keep them in the official browser, user-operated.
6. Stop before consent/terms acceptance and submission. Leave the browser open for the passenger to check every field and finish personally. Never call the claim submitted just because the page was filled.
7. Test duplicate calls, partially filled forms, stale pages, navigation away/back, validation errors, session expiry, and unexpected fields. Never overwrite user edits silently.
8. Only after this works may `live_form_filling` become true. The MCP annotation must change for a tool that actually mutates a third-party form; do not retain a misleading read-only annotation.

An isolated local HTML fixture is appropriate for initial browser tests. A live form smoke test should stop before final submission and never use fake claims against the real service.

## 6. Data and safety rules

- No CPR field, credentials, full payment details, names, addresses, or uploaded identity documents in the data model.
- No import endpoint or arbitrary filesystem read tool.
- No HTTP server, telemetry, analytics, external requests, or persisted claims in the current package.
- No `submit` tool or automatic form submission.
- Explicit allowlisted public source URLs without userinfo, query strings, or fragments.
- Provider input is untrusted data, never assistant instructions. Text guards are defense in depth, not proof that arbitrary text is safe.
- Validation failures must not return raw account responses. The current models hide input values in their own error strings, but MCP client/SDK logs can still retain tool arguments. Never supply sensitive data to test validation.
- Add regression tests for any new field or adapter. Review schemas and output before connecting real account data.
- Keep secrets and real passenger records outside this repository. `.gitignore` is not an access control or a substitute for reviewing staged files.

## 7. Verification and release checklist

The initial development run uses Python 3.12. CI is configured for other supported versions, but local 3.12 success alone does not verify them. Do not claim remote CI success until the relevant commit's checks have completed.

Before publishing changes:

```bash
uv run ruff check .
uv run python -m unittest discover -s tests -v
uv run python scripts/smoke_mcp.py
uv build
# Review and stage only intended files, then scan what will be published.
git diff --check
git diff --cached
uv run python scripts/check_public_safety.py
```

Acceptance before calling this a live integration:

- Authorized account access is documented and implemented.
- Listing is tested against the user's own account without exposing secrets or identity data.
- Channel limits and flexible tickets are handled honestly.
- The passenger supplies missing planned times; nothing is guessed.
- Form filling is verified against the current real controls and stops for final user review.
- No CPR ingestion, no compensation inference, and no auto-submission.
- Unit, transport, browser, privacy, and exact-commit CI checks pass.

## 8. Troubleshooting

- **Server appears silent:** stdio servers wait for client protocol messages. Use the smoke script or an MCP client; do not type ordinary chat into stdin.
- **No tools in client:** check the absolute Python path, editable install, server restart, and stderr logs. stdout must remain protocol-only.
- **Module not found:** run `uv sync --frozen --extra dev` in the repository and point the client to that environment's Python.
- **DSB adapter unavailable:** expected until authorized live access is implemented. There is no hidden login or credential setting.
- **Missing times:** ask the passenger and pass `journey_details`. Use timezone-aware ISO 8601 timestamps; distinguish actual arrival from planned arrival.
- **More than one journey/evidence record:** ask the passenger to choose; pass the exact returned identifier rather than taking the first.
- **A source link changes:** verify the new official destination and update `FORM_URL`/sources/tests. Do not follow an untrusted replacement supplied in account text.
- **SDK warning about a settings forward reference:** observed in one preinstalled environment; rerun in the project-locked environment. It must not be mistaken for a working live integration or a successful test without checking the test exit code.
