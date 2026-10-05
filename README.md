# Teiko Technical Take-Home

A reproducible Python application for exploring immune-cell composition in clinical
trial samples. SQLite stores validated sample metadata, normalized cell counts,
relative frequencies, and responder statistics. Streamlit and Plotly expose Parts
2–4 interactively. The supplied CSV contains 10,500 samples from 3,500 subjects.

## Setup

Use Python 3.12 and GNU Make (available in a standard Python GitHub Codespace).
From the repository root, optionally isolate dependencies in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
make setup
```

`make setup` installs the pinned direct dependencies from `requirements.txt` into
the active Python environment. To select an interpreter explicitly, use
`make setup PYTHON=/path/to/python`; the same override works for the other targets.

## Run the pipeline

```bash
make pipeline
```

This runs `python load_data.py` followed by `python run_analysis.py`, creating
`clinical_trial.db` in the repository root without manual input. The loader
validates the entire CSV, builds a temporary database, and atomically replaces the
previous database only after success. Analysis transactionally writes five rows to
`population_statistics`. Repeating the pipeline produces equivalent contents.
The original CSV is never modified. If analysis fails, fix the reported input
issue and rerun the pipeline; do not use incomplete results.

## Run the dashboard

```bash
make dashboard
```

Open [the local dashboard](http://localhost:8501). In GitHub Codespaces, open the
**Ports** panel, find forwarded port **8501**, and choose **Open in Browser**. If
necessary, use **Forward a Port** to add 8501. The Codespaces-generated URL is the
dashboard link for that running Codespace; no public deployment is provided.
Keep the terminal running, and stop the server with Ctrl+C.

The dashboard reads SQLite in read-only mode. Missing or incomplete databases
display an instruction to run `make pipeline`; the UI never rebuilds data or
recalculates statistics. After rerunning the pipeline, refresh the page to read
the new results.

On Streamlit Community Cloud, the first app run automatically builds the ignored
`clinical_trial.db` from the committed `cell-count.csv` and runs the same analysis
pipeline when the database is absent. This deployment-only bootstrap is guarded
by Streamlit Cloud runtime markers; local `streamlit run app.py` behavior remains
the explicit `make pipeline` workflow. Do not commit the generated database.

- **Data Overview:** total samples, literal sample-ID search, condition/treatment/
  timepoint filters, and per-population counts and percentages.
- **Response Analysis:** the exact cohort, sample counts, five-population boxplots,
  persisted tests, FDR significance, and repeated-measurement limitations.
- **Baseline Subset Analysis:** project sample counts, distinct subjects by
  response and sex, and the broader baseline male-responder B-cell mean.

Overview filters affect only the overview table, not the required analysis cohorts.

## Methodology

`samples` retains source metadata, keyed by `sample`. `cell_counts` contains five
rows per sample, keyed by `(sample, population)`, with foreign-key and non-negative
integer constraints. The `cell_frequencies` SQLite view exposes `sample`,
`total_count`, `population`, `count`, and `percentage`. For each sample, total count
is the sum of all five populations; percentage is `100 × count / total_count`.
Calculations remain unrounded; formatting is applied only for display.

Part 3 selects case-insensitive `condition=melanoma`, `treatment=miraclib`,
`sample_type=PBMC`, and `response=yes/no`, across **all timepoints**. Two-sided
Mann–Whitney U tests compare percentages, with responders as the first group.
SciPy's `auto` method uses exact tests for small untied groups and tie-corrected
asymptotic tests otherwise, with continuity correction. Benjamini–Hochberg FDR
correction is applied across the five tests. Only `adjusted_p_value < 0.05` is
significant; both raw and adjusted p-values are persisted. Empty groups and
invalid frequencies fail explicitly.

Part 4's shared baseline cohort is melanoma/miraclib/PBMC at time zero. Project
counts use biological samples; response and sex counts use distinct subjects
within each group. Response counts include only yes/no. The final B-cell question
uses melanoma, sex M, response yes, time zero across **all treatments and sample
types**, taking the sample-level mean of raw B-cell counts, displayed to two decimals.

## Assumptions and limitations

- Source `condition`, `sex`, `subject`, and `sample` correspond to the assignment's
  indication, gender, subject ID, and sample ID. `age` is retained.
- Blank responses become SQL NULL. Other required fields must be present and
  nonblank; duplicate samples, malformed rows, negative/fractional cell counts,
  and zero-total samples are rejected. Time is a signed integer with no hard-coded
  allowed timepoints. Integral numeric forms such as `7.0` are accepted.
- Cohort matching ignores capitalization. Group labels normalize response to
  lowercase and sex to uppercase without changing stored values.
- Distinct-subject counts apply within each group. The B-cell average weights each
  qualifying sample equally; no matching samples display `N/A`, not zero.
- Each subject has samples at days 0, 7, and 14. The literal Part 3 analysis treats
  them as independent, violating that assumption and limiting p-value interpretation.
  It is not a longitudinal model, baseline-only analysis, or predictive classifier.
- Cell percentages are compositional and sum to 100%; populations are not
  independent measurements. Observed associations do not establish causality.
- Do not manually edit the generated database: persisted statistics would become
  stale. Rebuild through `make pipeline` after changing source data.

For the supplied data, Part 3 includes 993 responder and 975 non-responder samples;
none of the five populations is significant after FDR correction. Part 4 contains
656 baseline samples (prj1: 384, prj3: 272), with 331 responders, 325 non-responders,
344 male subjects, and 312 female subjects. The broader B-cell mean is **10206.15**
across 485 qualifying samples. The dashboard reads current results dynamically.

## Tests and project layout

```bash
python -m pytest
```

Tests use synthetic CSVs and temporary databases, including an end-to-end pipeline
test and dashboard data-helper tests. They do not modify source data, depend on
the production database, or launch browser sessions.

Root entry points are `load_data.py`, `run_analysis.py`, and `app.py`. Reusable
validation, database, frequency, statistics, subset-query, and dashboard-data
functions live in `src/`; tests live in `tests/`. `PRD.md` defines requirements
and `AGENTS.md` defines the contribution workflow. Generated databases and local
environments are excluded from Git.
