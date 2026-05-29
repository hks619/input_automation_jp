# input_automation_jp — RMS Exposure Preparation Tool

A Streamlit web app that converts ceding-company ("cedent") exposure data into
**RMS RiskLink-ready, tab-separated `.txt` exposure files**, with first-class
support for Japanese cedent renewals.

It replaces a manual Excel + SQL workflow. The analyst's job is *conditioning*
messy/aggregated cedent data into clean, RMS-coded, location-level records.
This tool makes that fast, repeatable, and **auditable**.

---

## Workflow

1. **Download** the blank multi-sheet Excel template.
2. **Fill** the template offline with cedent data (aggregated exposure +
   distribution/"split" tables).
3. **Upload** the filled template.
4. **Geoprocess** — match cedent attribute values to RMS scheme codes
   (occupancy, construction, secondary modifiers) and resolve geography.
5. **Exposure-process** — apply the split tables to disaggregate aggregated
   exposure into individual location-level records.
6. **Validate & download** the tab-separated `.txt`, audit log, and
   reconciliation report (as a zip).

A separate tab handles the **CEDE → Risk Modeler / Data Bridge
franchise-deductible** problem (pre-import transformations + post-import SQL).

---

## Local setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud deploy

1. Push this repo to GitHub.
2. On <https://streamlit.io/cloud>, point a new app at `app.py`.
3. No secrets required by default.

## Where to put RMS code lists

Drop the analyst-supplied lookup files into `config/`:

- `config/occ_scheme.yaml` — valid `OCCSCHEME` + `OCCTYPE` codes.
- `config/bldg_scheme.yaml` — valid `BLDGSCHEME` + `BLDGCLASS` codes.
- `config/secondary_modifiers.yaml` — secondary-modifier code lists +
  default mapping keys.
- `config/japan_postal_to_cresta.yaml` — postal-code → CRESTA / prefecture.
- `config/defaults.yaml` — peril rule, currency, pruning threshold, line ending.
- `config/mappings/<cedent_id>.yaml` — per-cedent confirmed value mappings
  (written by the app, reused on renewal).

Empty stubs are provided. The tool flags any unmapped value as a hard error.

---

## Repository layout

```
.
├── app.py                      # Streamlit entry / navigation
├── pages/                      # one module per workflow step + CEDE tab + settings
├── core/
│   ├── schema.py               # template sheets + output headers (single source of truth)
│   ├── template_builder.py     # generates the blank .xlsx
│   ├── parser.py               # reads & structurally validates the uploaded template
│   ├── geoprocess.py           # value matching + geography resolution
│   ├── splitter.py             # disaggregation engine
│   ├── txt_writer.py           # tab-separated .txt output
│   ├── validation.py           # checks + reconciliation
│   ├── audit.py                # audit log
│   └── cede/                   # CEDE franchise-deductible module
├── config/                     # RMS code lists, postal→CRESTA, defaults
├── sample_data/                # example filled template + example output .txt
├── tests/                      # pytest (splitter value-preservation, parser, writer, validation)
├── requirements.txt
└── README.md
```

---

## Assumptions in effect (Section 13 of spec)

These are the stated defaults. Change them in `config/defaults.yaml` or
the Settings page. Every run logs which assumptions were active.

| # | Assumption | Default | Where to override |
|---|---|---|---|
| 1 | RMS code lists are analyst-supplied | empty stubs ship in `config/` | `config/occ_scheme.yaml`, `config/bldg_scheme.yaml`, `config/secondary_modifiers.yaml` |
| 2 | WS coverage values mirror EQ unless a WS source is provided | mirror EQ | `config/defaults.yaml: peril_rule` |
| 3 | Single currency per portfolio | `JPY` | `config/defaults.yaml: default_currency` |
| 4 | `SITELIM` repeated whole, not divided | repeat whole | `config/defaults.yaml: sitelim_rule` |
| 5 | Japan zone column is `CRESTA`; postal→zone lookup is analyst-supplied | `CRESTA` | `config/japan_postal_to_cresta.yaml` |
| 6 | Occ/Cons/BH/YB splits are independent (cross-product) | independent | hard-coded; revisit if joint distributions are needed |
| 7 | CEDE module generates SQL/scripts only (no live DB connection) | scripts only | `config/defaults.yaml: cede_live_db` |
| 8 | Secondary-modifier mapping is keyed by (occupancy, construction, LOB) | composite key | `config/secondary_modifiers.yaml` |

---

## Testing

```bash
pytest -q
```

The splitter tests assert **value- and count-preservation** — the
non-negotiable correctness property of the disaggregation engine.
