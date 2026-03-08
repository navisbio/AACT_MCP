# Privacy Policy

## Disclaimer

This is an independent, third-party wrapper for the [AACT database](https://aact.ctti-clinicaltrials.org). It is **not** affiliated with, endorsed by, or maintained by the Clinical Trials Transformation Initiative ([CTTI](https://ctti-clinicaltrials.org)) or Duke University. AACT is a publicly available relational database that aggregates data from ClinicalTrials.gov — see the [AACT case study](https://connects.ctti-clinicaltrials.org/show/57.pdf) for background.

## Data Collection

This MCP server does **not** collect, store, or transmit any personal data. It acts as a read-only bridge between Claude and the publicly available AACT database.

## Database Access

- All queries are **read-only** (SELECT only). No data can be written, modified, or deleted.
- The server connects to the AACT database hosted by the Clinical Trials Transformation Initiative (CTTI) at Duke University.
- Your AACT credentials (username and password) are used only to authenticate with the AACT database and are never logged, stored, or transmitted elsewhere.

## What Data Flows Where

| Data | Destination | Purpose |
|------|-------------|---------|
| AACT credentials | `aact-db.ctti-clinicaltrials.org` | Database authentication |
| SQL queries | AACT database | Retrieve clinical trial data |
| Query results | Claude (via MCP) | Display to user |

## Third-Party Services

- **AACT Database**: Operated by CTTI. See their [terms of use](https://aact.ctti-clinicaltrials.org/terms).
- No analytics, telemetry, or tracking services are used.

## Data Retention

Query results are buffered in server memory during the session for pagination and are discarded when the server process exits. No data is written to disk.

## Contact

For privacy questions, contact: jonas.walheim@navis-bio.com
