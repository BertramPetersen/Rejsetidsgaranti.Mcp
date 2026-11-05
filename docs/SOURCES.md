# Verified starting points and constraints

Research date: **2026-11-05**. Recheck before implementing or testing live access; terms, forms, and APIs can change.

## Official DSB Basis form

https://kc.dsb.dk/da-DK/webformularer/rejsetidsgaranti/soeg-dsb-basis-rejsetidsgaranti-v2/

This is the official form URL used by the manual handoff. Its existence does not establish a public submission API or stable automation selectors. No live form fields were filled by this scaffold. The user must confirm that the selected form fits their claim.

## DSB website terms

https://www.dsb.dk/om-dsb/virksomheden/forretningsbetingelser/betingelser-for-brug-af-dsbdk/

These terms restrict systematic website searching/copying without permission. Do not interpret access to an account as blanket permission to scrape it. Establish an authorized route before implementing automated ticket discovery.

## DSB Plus terms / ticket availability

https://www.dsb.dk/om-dsb/virksomheden/forretningsbetingelser/brug-af-dsb-plus/

Account and ticket access can depend on purchase channel. Do not promise that all tickets can be listed from one account surface. Test and document the specific approved channel's behavior.

## Rejseplanen data coverage

https://labs.rejseplan.dk/hc/en-us/articles/24750139021341-Oversigt-over-udstillede-data

The documentation states that historical data is not exposed. A live planner lookup is not automatically evidence for a past arrival delay. No Rejseplanen API integration is included.

## Unknowns, not assumptions

- No documented public DSB account-ticket API was verified.
- No documented public DSB claim-submission API was verified.
- Account authorization and terms for automated discovery are unresolved.
- Form DOM selectors and live browser behavior are unimplemented and unverified.
- The scaffold makes no claim about eligibility, compensation, deadlines, or entitlement.
