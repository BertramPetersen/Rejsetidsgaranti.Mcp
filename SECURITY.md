# Security and privacy boundaries

This is a public development scaffold. Do not open issues or pull requests containing real tickets, ticket identifiers, CPR, names, addresses, banking information, credentials, browser storage, screenshots, or network captures.

## Intended data flow

Today: synthetic provider → strict models → in-memory form preparation → stdio MCP client.

Future: explicitly authorized DSB-account provider → minimized ticket/journey records → reviewed form fields → official browser → user enters identity details, verifies, and submits.

There are no account credentials, file imports, uploads, background polling, HTTP listener, telemetry, persistent claim store, or submit operation in the current implementation. All advertised live-integration flags are false.

## Important limits

- MCP results are visible to the client and may be sent to its model provider or retained in its logs. Running the server locally does not make client conversations private or offline.
- Unknown model fields and common CPR/credential patterns are rejected. This is defense in depth, not a universal PII detector; do not enter sensitive data at all.
- The SDK or host may retain malformed arguments. Never test privacy validation with genuine personal data or secrets.
- Labels and source records are untrusted content, not instructions. The future account adapter must minimize data before creating model objects.
- Source URL restrictions do not authenticate the underlying evidence. No source URLs are fetched by this package.
- The publication guard catches a small set of patterns and file types. It is not a complete secret scanner or legal review.
- `.gitignore` cannot undo already published content. Review staged files, fixtures, tool output, screenshots, and commit metadata before sharing.

## Required future-adapter safeguards

Document the permitted account-access method. Keep login and secret storage outside MCP arguments/results. Use least privilege, explicit user initiation, bounded retrieval, and no hidden fallback to scraping. Never infer actual travel from purchase history alone.

A live form adapter must verify the official origin, reject synthetic records, avoid identity/CPR/banking fields, preserve user edits, and stop before acceptance or final submission. Mutation tools must advertise their actual side effects.

If you find a security issue, report a sanitized description privately through the repository's available private reporting channel. Do not paste secrets or passenger data into a public report. If no private channel is available, contact the maintainer privately rather than opening a sensitive public issue.
