# Rejsetidsgaranti MCP

An **unofficial, local-first Python MCP scaffold** for listing tickets from a DSB account, preparing journey details, and handing a DSB compensation form to the passenger for final verification.

**Today this is a tested development scaffold, not a working DSB integration.** The MCP protocol and synthetic end-to-end workflow work. Live DSB account discovery and browser form filling are explicit, unavailable adapters. It never submits claims.

## Product boundaries

- Tickets should come **only from the passenger's DSB account**. There is no PDF parser, email reader, or file-import feature.
- Use planned departure/arrival times from a ticket only when it contains an exact, bound one-way journey. Otherwise ask the passenger; never guess a train from a flexible ticket.
- Prepare the details for the official form. **Do not determine eligibility or estimate compensation.**
- The passenger enters CPR and other identity/banking details directly on DSB's site, reviews every field and the official terms, and submits personally.
- The bundled dataset is synthetic and must never be submitted to DSB.

## Quick start

Python 3.11+ and [uv](https://docs.astral.sh/uv/) are recommended:

```bash
git clone https://github.com/BertramPetersen/Rejsetidsgaranti.Mcp.git
cd Rejsetidsgaranti.Mcp
uv sync --frozen --extra dev
uv run python -m unittest discover -s tests -v
uv run python scripts/smoke_mcp.py
uv run ruff check .
uv run dsb-claims-mcp
```

The last command starts a stdio server and waits for an MCP client. That is expected, not a hang. Use Ctrl+C to stop it. See **[the comprehensive laptop handoff](docs/HANDOFF.md)** for client configuration, exact test prompts, architecture, implementation priorities, and acceptance criteria.

## Tools

| Tool | Implemented behavior |
| --- | --- |
| `dsb_status` | Reports provider, privacy boundaries, and which integrations are actually implemented. |
| `dsb_list_tickets` | Lists ticket references from the provider; optional inclusive Copenhagen departure dates. |
| `dsb_list_journeys` | Lists exact known journeys, optionally for a selected ticket. |
| `dsb_get_delay_evidence` | Lists provider-supplied arrival evidence. No live/history API is queried. |
| `dsb_prepare_claim_form` | Builds form fields from a selected ticket journey or user-supplied details; reports missing input. |
| `dsb_get_form_handoff` | Returns the official form URL, fields, and manual review checklist. Does not open/fill the form. |

All tools are read-only and use structured MCP results. `DSB_MCP_PROVIDER=demo` is the default. `DSB_MCP_PROVIDER=dsb-account` deliberately returns an actionable “not implemented” result when data is requested. There are no password, cookie, CPR, or account-export inputs.

## Why the account adapter is a stub

No documented public DSB account or claim-submission API has been verified. Account ticket availability can depend on purchase channel. DSB's website terms restrict systematic searching/copying without permission. This repository does not reverse-engineer endpoints, scrape accounts, or assume that a successful login authorizes automated access.

Before implementing live account discovery, establish an authorized access method and applicable terms. Before implementing browser form filling, inspect the current official form, map observed controls, and keep the final review and submission with the passenger. See [sources and constraints](docs/SOURCES.md) and [security boundaries](SECURITY.md).

## What has been tested

The repository includes domain/security unit tests and a real stdio MCP client/server smoke test. CI is configured for Python 3.11, 3.12, and 3.13. A passing synthetic test is **not** evidence that DSB login, account ticket retrieval, or form selectors work. The handoff records exactly which checks were run and which integrations remain untested.

The existing repository license is preserved. This project is not affiliated with or endorsed by DSB.
