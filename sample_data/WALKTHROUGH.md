# End-to-end walkthrough

This folder contains a small, hand-traceable dummy dataset so you can step
through every page of the tool and watch the `.txt` file get built.

## Files in this folder

| File | What it is | Where to use it in the app |
|---|---|---|
| `walkthrough_filled_template.xlsx` | A filled-in input template with one EXP_EQ row and 2-way splits across all four dimensions. | Upload on **Step 2**. |
| `walkthrough_expected_output.txt` | The reference RMS RiskLink `.txt` you should end up with on **Step 6**. Compare against the one you generate. | Compare on **Step 6**. |
| `walkthrough_loc_cede.csv` | Sample CEDE location table — 4 rows, 2 of which use franchise (`FR`) deductibles. | Upload on the **CEDE** tab, Stage 1. |
| `build_walkthrough.py` | The script that generates the three files above. Re-run it if you tweak values. | — |

## The walkthrough dataset

One aggregated cell to disaggregate. All values in JPY.

**`Account_Group`**: 1 row — `ACC-DEMO-001` / `LOB=RESID` / cedent `CED-DEMO`.

**`EXP_EQ`**: 1 row — Tokyo Marunouchi, postcode `100-0001`.
- `NUMBLDGS = 100`
- `BLDG = 1,000,000,000`
- `CONT = 200,000,000`
- `BI = 50,000,000`
- `SITELIM = 2,000,000,000`

**Four splits**, all for `LOB=RESID`:
- **Occ** — Apartment 60% (`OCCTYPE 311`) · SFD 40% (`OCCTYPE 300`)
- **Cons** — RC 70% (`BLDGCLASS 311`) · Wood 30% (`BLDGCLASS 100`)
- **BH** — 3 storeys 60% · 8 storeys 40%
- **YB** — 2005 50% · 1985 50%

Cross-product: **2 × 2 × 2 × 2 = 16 output rows**.

## Hand-check one row

Combination: Apartment × RC × 3 storeys × 2005.

```
proportion = 0.60 × 0.70 × 0.60 × 0.50 = 0.126

EQCV1VAL (BLDG) = 1,000,000,000 × 0.126 = 126,000,000
EQCV2VAL (CONT) =   200,000,000 × 0.126 =  25,200,000
EQCV3VAL (BI)   =    50,000,000 × 0.126 =   6,300,000
NUMBLDGS        = round(100 × 0.126)    = 13   (Σ across all 16 rows = 100)
```

Open `walkthrough_expected_output.txt` and look for the row where
`OCCTYPE=311`, `BLDGCLASS=311`, `NUMSTORIES=3`, `YEARBUILT=2005` — those
four numbers should match.

## Step-by-step in the app

1. **Step 1 — Download Template.** Just confirms the blank template downloads.
2. **Step 2 — Upload Filled Template.** Upload `walkthrough_filled_template.xlsx`. You should see 0 errors and previews of all six sheets.
3. **Step 3 — Geoprocess.**
   - **Occupancy:** "Apartment" auto-suggests `311`, "Single family dwelling" auto-suggests `300`. Click **Confirm** on each.
   - **Construction:** "Reinforced concrete" → `311`, "Wood frame" → `100`. Click **Confirm** on each.
   - **Geography:** postcode `100-0001` resolves to Tokyo / `JP_13` from the stub lookup.
   - Click **Save mappings for this cedent** so renewals pre-fill.
4. **Step 4 — Split & Disaggregate.** Click **Run splitter**. You should see **16 records**, 0 pruned, no rebasing (shares already sum to 100%).
5. **Step 5 — Validate.** Every check should be green. TIV recon table should show in == out per ACCNTNUM.
6. **Step 6 — Generate Output.** Download the `.txt`. Open it in a text editor and compare line-by-line to `walkthrough_expected_output.txt` — they should match (header order, tab separation, every row).

   Also download the **zip bundle** — it contains the `.txt`, the audit log
   (Markdown + JSON), and the reconciliation report.

## CEDE walkthrough

On the **CEDE** tab, Stage 1:
1. Cedent identifier: `CED-DEMO`.
2. Upload `walkthrough_loc_cede.csv` as `LocCede`.
3. Leave `LossCede` empty — the tool will detect the missing loss table and emit a dummy-loss INSERT.

Expected:
- 2 `FR` rows flagged, 2 `FR → S` conversions.
- "Dummy loss added: yes."
- Stage-1 SQL has an `INSERT INTO LossCede ...` and an
  `UPDATE LocCede SET DedTxt1 = CONCAT(..., '_FR'), DedType1 = 'S' WHERE DedType1 = 'FR';`.

Stages 2 and 3 just generate SQL with whatever DB names you type in.
