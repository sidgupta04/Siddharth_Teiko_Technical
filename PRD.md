# Teiko Technical Take-Home
## Product Requirements Document

**Repository:** `sidgupta04/Siddharth_Teiko_Technical`  
**Primary language:** Python  
**Database:** SQLite  
**Dashboard:** Streamlit + Plotly  
**Testing:** pytest  
**Target environment:** GitHub Codespaces

---

# 1. Project Objective

Build a reproducible Python analytics application that:

1. loads immune-cell clinical trial data from `cell-count.csv`;
2. models the data in SQLite;
3. calculates immune-cell relative frequencies for every sample;
4. compares responders versus non-responders statistically;
5. answers the required subset-analysis questions;
6. exposes Parts 2–4 through an interactive dashboard;
7. runs reproducibly through the required Makefile commands.

The finished repository must work from a fresh GitHub Codespace with:

```bash
make setup
make pipeline
make dashboard
```

The implementation should prioritize:

- correctness;
- reproducibility;
- readable Python;
- simple architecture;
- sound SQL;
- sound statistical reasoning;
- automated test coverage;
- clear documentation of assumptions.

Do not overengineer the project.

---

# 2. User and Analytical Goal

The fictional user is Bob Loblaw, a drug developer at Loblaw Bio.

Bob wants to understand whether the drug candidate `miraclib` is associated with differences in immune-cell composition and whether immune-cell population frequencies differ between patients who respond to treatment and patients who do not.

The application should allow Bob to:

- inspect immune-cell relative frequencies for biological samples;
- compare responders and non-responders;
- identify statistically significant population differences;
- inspect baseline melanoma subsets;
- answer required project, response, gender, and B-cell questions;
- explore results interactively through a dashboard.

---

# 3. Source Data

The project uses:

```text
cell-count.csv
```

Each row represents one biological sample.

The dataset contains counts for five immune-cell populations:

```text
b_cell
cd8_t_cell
cd4_t_cell
nk_cell
monocyte
```

The assignment states that metadata includes fields such as:

```text
sample or sample_id
indication
treatment
time_from_treatment_start
response
gender
```

Part 4 additionally implies columns representing:

```text
subject
project
sample type
```

The exact source headers must be confirmed from the real CSV.

The implementation should use the actual dataset column names internally while exposing the output names required by the assignment.

The assignment contains at least one known naming ambiguity:

```text
sample
vs.
sample_id
```

---

# 4. Scope

## In Scope

The project must include:

- SQLite database creation;
- CSV loading;
- relational data modeling;
- input validation;
- immune-cell frequency calculation;
- responder/non-responder analysis;
- statistical testing;
- multiple-testing correction;
- Part 4 subset queries;
- interactive dashboard;
- Makefile;
- README;
- automated tests;
- reproducible pipeline.

## Out of Scope

Do not add unless clearly required:

- machine-learning classifier;
- React frontend;
- FastAPI backend;
- authentication;
- cloud infrastructure;
- ORM;
- Docker;
- mixed-effects longitudinal modeling;
- prediction API;
- complex deployment infrastructure.

The phrase "predicting response" should be interpreted as exploratory biomarker analysis rather than a requirement to train a predictive ML model.

---

# 5. High-Level Architecture

The intended architecture is:

```text
cell-count.csv
      │
      ▼
 load_data.py
      │
      ├── validate source data
      ├── initialize SQLite schema
      └── load normalized data
      │
      ▼
clinical_trial.db
      │
      ├── samples
      ├── cell_counts
      └── cell_frequencies
      │
      ▼
run_analysis.py
      │
      ├── responder cohort extraction
      ├── statistical analysis
      └── persist statistical results
      │
      ▼
clinical_trial.db
      │
      ▼
app.py
      │
      ▼
Streamlit dashboard
```

After the pipeline runs, SQLite should act as the analytical source of truth.

The dashboard should query the generated database rather than independently rebuilding the entire analysis from the CSV.

---

# 6. Suggested Repository Structure

A reasonable target structure is:

```text
Siddharth_Teiko_Technical/
│
├── AGENTS.md
├── PRD.md
├── cell-count.csv
├── load_data.py
├── run_analysis.py
├── app.py
├── Makefile
├── requirements.txt
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── database.py
│   ├── validation.py
│   ├── frequencies.py
│   ├── statistics.py
│   └── queries.py
│
└── tests/
    ├── conftest.py
    ├── test_load_data.py
    ├── test_frequencies.py
    ├── test_statistics.py
    ├── test_queries.py
    └── test_pipeline.py
```

This structure is not mandatory.

Prefer simplicity over creating unnecessary files or abstractions.

---

# 7. Part 1 — Data Management

The repository must contain:

```text
load_data.py
```

in the repository root.

The following command must work with no arguments:

```bash
python load_data.py
```

It must create a SQLite database file with a `.db` extension in the repository root.

Recommended filename:

```text
clinical_trial.db
```

The script must not require:

- command-line arguments;
- `python -m`;
- manual configuration.

---

# 8. Relational Database Design

Use a normalized structure with at least:

```text
samples
cell_counts
```

## 8.1 `samples`

One row per biological sample.

Conceptual schema:

```sql
sample_id TEXT PRIMARY KEY
subject_id TEXT
project TEXT
indication TEXT
treatment TEXT
sample_type TEXT
time_from_treatment_start REAL
response TEXT
gender TEXT
```

Exact field names should match the real dataset.

Additional useful metadata columns from the source may also be retained.

## 8.2 `cell_counts`

One row per:

```text
sample × immune-cell population
```

Conceptual schema:

```sql
sample_id TEXT NOT NULL
population TEXT NOT NULL
count INTEGER NOT NULL

PRIMARY KEY (sample_id, population)

FOREIGN KEY (sample_id)
REFERENCES samples(sample_id)
```

Allowed populations:

```text
b_cell
cd8_t_cell
cd4_t_cell
nk_cell
monocyte
```

Example:

```text
sample_id | population  | count
--------------------------------
S001      | b_cell      | 120
S001      | cd8_t_cell  | 250
S001      | cd4_t_cell  | 300
S001      | nk_cell     | 80
S001      | monocyte    | 250
```

---

# 9. Cell-Count Normalization

The CSV likely stores immune-cell populations as columns:

```text
sample | b_cell | cd8_t_cell | cd4_t_cell | nk_cell | monocyte
```

The database should represent these measurements as rows:

```text
sample | population | count
```

This simplifies:

- SQL aggregation;
- plotting;
- grouping;
- statistical analysis;
- future support for additional populations.

Do not over-normalize unrelated metadata into unnecessary tables.

---

# 10. Loader Behavior

`load_data.py` must:

1. locate `cell-count.csv`;
2. validate required source fields;
3. initialize or recreate the SQLite database;
4. create required tables;
5. insert sample metadata;
6. reshape the five immune-cell columns into long form;
7. insert cell-count rows;
8. create any required Part 2 database view;
9. commit changes;
10. close database resources cleanly;
11. print a concise success summary.

Example output:

```text
Loaded 120 samples
Loaded 600 cell-count records
Created clinical_trial.db
```

Actual counts will depend on the dataset.

---

# 11. Idempotency

Repeated execution must not duplicate records.

For example:

```bash
python load_data.py
python load_data.py
```

must produce the same final database contents as running the loader once.

Preferred behavior:

```text
rebuild the SQLite database from the CSV on each execution
```

The CSV remains the authoritative raw source.

---

# 12. Input Validation

At minimum validate:

- required metadata fields exist;
- all five population columns exist;
- sample identifiers are present;
- sample identifiers are unique where expected;
- cell counts are numeric;
- cell counts are non-negative;
- time values can be interpreted consistently;
- malformed source structure fails clearly.

Do not silently replace malformed values with guessed defaults.

Example error:

```text
ValueError: Missing required column: response
```

A sample whose five cell counts sum to zero should also be handled explicitly because relative frequency would be undefined.

---

# 13. Part 1 Test Requirements

Automated tests must cover:

### Database creation

Valid source data creates a `.db` file.

### Schema

Required tables exist.

### Sample count

The number of rows in `samples` matches the number of source samples.

### Cell-count row count

For N samples:

```text
cell_counts rows = N × 5
```

### Normalization

Every sample has exactly five population records.

### Foreign-key correctness

Every cell-count record belongs to a valid sample.

### Duplicate protection

No duplicate:

```text
sample_id + population
```

pairs exist.

### Idempotency

Loading twice does not double row counts.

### Missing required column

Invalid input fails clearly.

### Negative cell count

Negative counts are rejected.

### Duplicate sample identifier

Duplicate sample identifiers are rejected or explicitly handled.

---

# 14. Part 2 — Relative Cell Frequencies

Bob's first analytical question is:

> What is the frequency of each cell type in each sample?

For each sample:

```text
total_count =
b_cell
+ cd8_t_cell
+ cd4_t_cell
+ nk_cell
+ monocyte
```

For each population:

```text
percentage =
population_count / total_count × 100
```

---

# 15. Required Part 2 Output

Each row represents:

```text
one sample × one population
```

Required columns:

```text
sample
total_count
population
count
percentage
```

Example:

```text
sample | total_count | population | count | percentage
-------------------------------------------------------
S001   | 1000        | b_cell     | 100   | 10.00
S001   | 1000        | cd8_t_cell | 250   | 25.00
S001   | 1000        | cd4_t_cell | 300   | 30.00
S001   | 1000        | nk_cell    | 75    | 7.50
S001   | 1000        | monocyte   | 275   | 27.50
```

---

# 16. Frequency Storage

Preferred implementation:

```text
cell_frequencies
```

as a SQLite view.

Conceptual fields:

```text
sample
total_count
population
count
percentage
```

A database view is preferred because these values are derived from source counts and do not need to be duplicated.

A materialized table is acceptable if it results in a simpler or more reliable implementation.

---

# 17. Part 2 Validation

For every valid sample:

```text
sum(population percentages) ≈ 100
```

Use floating-point tolerance.

Samples with:

```text
total_count = 0
```

must not cause division-by-zero failures.

Preferred behavior is to reject such records during validation with a clear error.

---

# 18. Part 2 Test Requirements

Automated tests must cover:

### Total count

For:

```text
10 + 20 + 30 + 20 + 20
```

verify:

```text
total_count = 100
```

### Percentage

For:

```text
b_cell = 10
total_count = 100
```

verify:

```text
percentage = 10.0
```

### Five frequency rows

Each sample creates exactly five frequency rows.

### Percentages sum to 100

Within floating-point tolerance.

### Output fields

Verify availability of:

```text
sample
total_count
population
count
percentage
```

### Zero total

Zero-total samples are handled explicitly.

---

# 19. Part 3 — Responder Analysis

Required cohort:

```text
indication = melanoma
treatment = miraclib
sample_type = PBMC
response ∈ {yes, no}
```

Filtering should be robust to reasonable capitalization differences.

For example:

```text
Melanoma
melanoma
```

should be treated equivalently during cohort selection.

Original stored values do not need to be modified solely for display purposes.

---

# 20. Part 3 Analysis Variable

The primary responder comparison must use:

```text
relative frequency percentage
```

from Part 2.

Do not use raw cell counts as the primary comparison.

For each immune-cell population compare:

```text
responder percentages
vs.
non-responder percentages
```

---

# 21. Part 3 Visualization

Display responder versus non-responder relative-frequency distributions using boxplots.

Use:

```text
Plotly
```

The visualization should clearly identify:

- immune-cell population;
- response group;
- relative frequency percentage.

Acceptable designs include:

- one figure containing all five populations;
- faceted boxplots;
- an interactive population selector.

Useful hover details may include:

```text
sample ID
population
percentage
timepoint
```

where appropriate.

---

# 22. Statistical Methodology

Use a:

```text
two-sided Mann–Whitney U test
```

for the responder versus non-responder comparison for each immune-cell population.

This is appropriate because:

- the distributions may not be normal;
- clinical datasets may have modest sample sizes;
- the comparison involves two groups.

For each population report:

```text
population
responder_n
non_responder_n
responder_median
non_responder_median
u_statistic
p_value
adjusted_p_value
significant
```

Additional descriptive statistics may be included.

---

# 23. Multiple-Testing Correction

Five immune-cell populations means five hypothesis tests.

Apply:

```text
Benjamini-Hochberg false discovery rate correction
```

across the five raw p-values.

Expose both:

```text
p_value
adjusted_p_value
```

Use:

```text
adjusted_p_value < 0.05
```

as the primary significance criterion.

Do not report a population as statistically significant solely because its unadjusted p-value is below 0.05 if the corrected value is not.

---

# 24. Statistical Result Persistence

Persist the Part 3 results in SQLite.

Recommended table:

```text
population_statistics
```

Conceptual schema:

```sql
population TEXT PRIMARY KEY
responder_n INTEGER
non_responder_n INTEGER
responder_median REAL
non_responder_median REAL
u_statistic REAL
p_value REAL
adjusted_p_value REAL
significant INTEGER
```

The dashboard should be able to read completed Part 3 results from the database.

---

# 25. Repeated-Measurement Limitation

The dataset may contain multiple samples from the same subject at different timepoints.

If so, treating all samples as fully independent is a statistical limitation.

The assignment does not explicitly require longitudinal modeling.

Therefore:

- perform the literal requested analysis;
- document repeated observations as a limitation if present;
- do not introduce a mixed-effects model unless clearly justified.

---

# 26. Prediction Interpretation

The assignment mentions the broader goal of predicting response but does not explicitly restrict Part 3 to baseline samples.

Therefore the default required responder analysis should not silently add:

```text
time_from_treatment_start = 0
```

An optional dashboard control may allow:

```text
all timepoints
baseline only
```

but the baseline-only version must remain supplemental.

---

# 27. Part 3 Test Requirements

Automated tests must cover:

### Correct cohort

Include only:

```text
melanoma
miraclib
PBMC
response yes/no
```

### Wrong indication exclusion

Non-melanoma samples are excluded.

### Wrong treatment exclusion

Non-miraclib samples are excluded.

### Wrong sample type exclusion

Non-PBMC samples are excluded.

### Case-insensitive filtering

Reasonable capitalization differences do not alter cohort membership.

### Correct response grouping

Responder and non-responder records are separated correctly.

### Five populations

Statistical output contains all five populations.

### Mann–Whitney calculation

Use deterministic toy data and verify results against:

```python
scipy.stats.mannwhitneyu
```

### Benjamini-Hochberg correction

Verify adjusted p-values against a known example.

### Significance rule

Verify:

```text
significant =
adjusted_p_value < 0.05
```

### Persistence

`population_statistics` contains one row per population.

---

# 28. Part 4 — Baseline Melanoma Subset

The required Part 4 baseline cohort is:

```text
indication = melanoma
sample_type = PBMC
time_from_treatment_start = 0
treatment = miraclib
```

This cohort should be represented in reusable query logic.

---

# 29. Samples by Project

Within the Part 4 base cohort, calculate:

```text
sample count grouped by project
```

Conceptually:

```sql
GROUP BY project
COUNT(*)
```

Output:

```text
project
sample_count
```

This is a biological sample count, not a unique subject count.

---

# 30. Subjects by Response

Within the same Part 4 base cohort, calculate:

```text
COUNT(DISTINCT subject_id)
```

grouped by:

```text
response
```

Example:

```text
response | subject_count
------------------------
yes      | N
no       | N
```

The assignment explicitly asks for subjects, not samples.

---

# 31. Subjects by Gender

Within the same Part 4 base cohort, calculate:

```text
COUNT(DISTINCT subject_id)
```

grouped by:

```text
gender
```

Example:

```text
gender | subject_count
----------------------
male   | N
female | N
```

This should also count unique subjects rather than sample rows.

---

# 32. Final B-Cell Question

The final question is separate from the Part 4 base cohort:

> Considering Melanoma males of all sample and treatment types, what is the average number of B cells for responders at time=0?

Required filters:

```text
indication = melanoma
gender = male
response = yes
time_from_treatment_start = 0
```

Do not additionally restrict:

```text
treatment = miraclib
```

Do not additionally restrict:

```text
sample_type = PBMC
```

because the assignment explicitly specifies:

```text
all sample and treatment types
```

Calculate:

```text
AVG(b_cell count)
```

and display the result using exactly two decimal places:

```text
XX.XX
```

---

# 33. Part 4 Test Requirements

Automated tests must cover:

### Base cohort filters

Verify all required filters:

```text
melanoma
miraclib
PBMC
time = 0
```

### Samples by project

Verify biological samples are counted correctly.

### Response subject counts

Verify unique subjects are counted rather than raw sample rows.

Fixture data should include at least one subject with multiple relevant rows so an incorrect `COUNT(*)` implementation can be detected.

### Gender subject counts

Again verify unique subject counting.

### B-cell special query

Verify required filters:

```text
melanoma
male
response=yes
time=0
```

### Include non-miraclib treatment

A qualifying responder on another treatment must contribute to the B-cell mean.

### Include non-PBMC sample

A qualifying non-PBMC sample must also contribute.

These tests protect against accidentally reusing the earlier Part 4 cohort.

### Decimal formatting

The final displayed answer uses two decimal places.

---

# 34. Interactive Dashboard

Use:

```text
Streamlit
```

for the dashboard.

Use:

```text
Plotly
```

for interactive charts.

The dashboard must read from:

```text
clinical_trial.db
```

produced by the data pipeline.

It should not require users to manually preprocess or reload the CSV after the pipeline has completed.

---

# 35. Dashboard Section 1 — Data Overview

Display:

- total number of samples;
- Part 2 relative-frequency data;
- sample-level filtering or search;
- population counts and percentages.

Optional simple filters may include:

```text
sample
indication
treatment
timepoint
```

The primary requirement is that the Part 2 summary data be available interactively.

---

# 36. Dashboard Section 2 — Response Analysis

Display:

- Part 3 cohort definition;
- responder sample count;
- non-responder sample count;
- responder versus non-responder boxplots;
- statistical result table;
- raw p-values;
- adjusted p-values;
- significance status.

Include a concise methodological explanation such as:

```text
Two-sided Mann–Whitney U tests were performed for each immune-cell
population. P-values were adjusted across the five tests using
Benjamini-Hochberg false discovery rate correction.
```

Avoid causal claims.

Prefer wording such as:

```text
"differed between groups"
"associated with response"
```

rather than:

```text
"caused response"
```

---

# 37. Dashboard Section 3 — Baseline Subset Analysis

Display:

- Part 4 baseline melanoma/miraclib/PBMC cohort;
- sample counts by project;
- unique subjects by response;
- unique subjects by gender;
- final baseline B-cell average.

The B-cell result should clearly state that it uses:

```text
all sample and treatment types
```

for baseline male melanoma responders.

---

# 38. Dashboard Error Handling

If the SQLite database does not exist, show a clear error such as:

```text
Database not found.
Run `make pipeline` before starting the dashboard.
```

The dashboard should not silently recreate the data pipeline.

---

# 39. Makefile Requirements

The repository root must contain:

```text
Makefile
```

with exactly these targets:

```text
setup
pipeline
dashboard
```

---

# 40. `make setup`

Installs all project dependencies.

Example:

```bash
pip install -r requirements.txt
```

It must work in GitHub Codespaces.

---

# 41. `make pipeline`

Runs the complete data pipeline sequentially without manual intervention.

Expected flow:

```text
python load_data.py
python run_analysis.py
```

At completion, `clinical_trial.db` should contain:

- source sample metadata;
- normalized cell counts;
- relative frequencies;
- Part 3 statistical results.

Repeated execution should produce equivalent results.

---

# 42. `make dashboard`

Starts the local dashboard server.

Expected behavior:

```bash
streamlit run app.py
```

It must consume the database generated by:

```bash
make pipeline
```

---

# 43. Dependencies

Keep the dependency set small.

Likely required packages:

```text
pandas
numpy
scipy
statsmodels
streamlit
plotly
pytest
```

Use Python's standard:

```text
sqlite3
```

library unless a concrete need for another database layer emerges.

---

# 44. Testing Strategy

Tests should use:

- temporary directories;
- temporary SQLite databases;
- synthetic fixture data;
- deterministic inputs.

Tests must not:

- modify the real `cell-count.csv`;
- depend on the generated production database;
- launch Streamlit browser sessions.

Core analytical logic and query helpers should be testable independently from presentation code.

---

# 45. Synthetic Test Fixture Requirements

Create a compact synthetic fixture that includes cases such as:

```text
S1 subject_1 melanoma miraclib PBMC   time=0 yes male
S2 subject_2 melanoma miraclib PBMC   time=0 no  female
S3 subject_3 melanoma other    PBMC   time=0 yes male
S4 subject_4 melanoma miraclib tissue time=0 yes male
S5 subject_5 melanoma miraclib PBMC   time=7 yes male
S6 subject_6 lung     miraclib PBMC   time=0 yes male
```

The fixture should also include:

- at least one repeated subject where useful;
- known cell counts that make expected percentages easy to calculate;
- data that exposes incorrect cohort filtering.

---

# 46. Pipeline Integration Test

At least one integration test should exercise the analytical pipeline end to end using synthetic data.

It should verify:

1. CSV loading;
2. database creation;
3. normalized cell counts;
4. frequency calculations;
5. statistical analysis;
6. statistics persistence;
7. Part 4 query outputs.

The integration test does not need to launch Streamlit.

---

# 47. Dashboard Testing

Avoid brittle browser-level UI tests.

Where practical, separate dashboard data-access helpers from Streamlit rendering.

Examples:

```text
get_frequency_data()
get_statistics()
get_project_counts()
get_response_subject_counts()
get_gender_subject_counts()
get_bcell_average()
```

These helpers should be testable independently.

---

# 48. Code Quality Requirements

The implementation should:

- use clear functions;
- avoid excessively large scripts;
- use descriptive names;
- use type hints where helpful;
- use parameterized SQL for values;
- use context managers for database connections;
- avoid duplicated cohort-filtering logic;
- avoid hidden global state;
- fail clearly on invalid input;
- remain understandable to another engineer.

Prefer simple functions over unnecessary classes or frameworks.

---

# 49. README Requirements

The final `README.md` must include:

## Project overview

Explain what the project analyzes.

## Setup

```bash
make setup
```

## Run pipeline

```bash
make pipeline
```

## Run dashboard

```bash
make dashboard
```

## Dashboard link

Include the deployed dashboard URL if available.

If using GitHub Codespaces, explain how to access the forwarded Streamlit port.

## Methodology

Explain:

- database design;
- relative-frequency calculation;
- Part 3 cohort definition;
- Mann–Whitney U test;
- Benjamini-Hochberg correction;
- significance threshold.

## Assumptions

Document interpretation decisions caused by ambiguous assignment wording.

## Limitations

Document relevant analytical limitations, including repeated patient measurements if applicable.

---

# 50. Implementation Milestones

The project should be implemented across five logical milestones.

---

# 51. Milestone 1 — Part 1: Data Management

Suggested commit message:

```text
feat: load clinical trial data into sqlite
```

Scope:

- project structure needed for Part 1;
- dependency file;
- SQLite schema;
- validation;
- root `load_data.py`;
- sample loading;
- normalized cell-count loading;
- idempotent database recreation;
- Part 1 tests.

Completion criteria:

```bash
python load_data.py
```

successfully creates the database.

Part 2–4 analysis and dashboard functionality are not part of this milestone.

---

# 52. Milestone 2 — Part 2: Relative Cell Frequencies

Suggested commit message:

```text
feat: calculate per-sample cell population frequencies
```

Scope:

- total cell count;
- relative-frequency calculation;
- `cell_frequencies` view or table;
- frequency query helper;
- Part 2 tests.

Completion criteria:

The backend can produce the exact required Part 2 summary fields.

Part 3, Part 4, and dashboard functionality are not part of this milestone.

---

# 53. Milestone 3 — Part 3: Responder Statistical Analysis

Suggested commit message:

```text
feat: add responder statistical analysis
```

Scope:

- melanoma/miraclib/PBMC cohort;
- responder/non-responder grouping;
- Mann–Whitney U testing;
- Benjamini-Hochberg correction;
- descriptive statistics;
- `population_statistics`;
- `run_analysis.py`;
- Part 3 tests.

Completion criteria:

```bash
python run_analysis.py
```

populates the required Part 3 statistical results.

Part 4 and dashboard functionality are not part of this milestone.

---

# 54. Milestone 4 — Part 4: Baseline Subset Analysis

Suggested commit message:

```text
feat: add baseline melanoma subset analysis
```

Scope:

- baseline melanoma/miraclib/PBMC cohort;
- samples by project;
- unique subjects by response;
- unique subjects by gender;
- final B-cell average;
- Part 4 tests.

Completion criteria:

All Part 4 questions can be answered programmatically from the database.

Dashboard functionality is not part of this milestone.

---

# 55. Milestone 5 — Dashboard and Reproducible Workflow

Suggested commit message:

```text
feat: add dashboard and reproducible project workflow
```

Scope:

- Streamlit dashboard;
- Plotly visualizations;
- Part 2 display;
- Part 3 display;
- Part 4 display;
- `Makefile`;
- `make setup`;
- `make pipeline`;
- `make dashboard`;
- completed README;
- pipeline integration test;
- dashboard data-helper tests.

Completion criteria:

From a clean environment:

```bash
make setup
make pipeline
pytest
make dashboard
```

works successfully.

---

# 56. Definition of Done

The project is complete when all conditions below are satisfied.

## Part 1

- `python load_data.py` works without arguments;
- a `.db` file is created in the repository root;
- source samples are correctly represented;
- every sample has five normalized cell-count rows;
- repeated execution is safe;
- Part 1 tests pass.

## Part 2

- total cell counts are correct;
- relative frequencies are correct;
- required summary fields are available;
- percentages sum to approximately 100%;
- Part 2 tests pass.

## Part 3

- the correct melanoma/miraclib/PBMC cohort is used;
- responders and non-responders are compared;
- all five populations are analyzed;
- boxplot-ready data exists;
- Mann–Whitney U tests are correct;
- adjusted p-values are reported;
- significant populations are identified using adjusted p-values;
- Part 3 tests pass.

## Part 4

- baseline cohort filtering is correct;
- samples by project are correct;
- response subject counts are correct;
- gender subject counts are correct;
- final B-cell calculation includes all sample and treatment types;
- B-cell result is displayed to two decimal places;
- Part 4 tests pass.

## Dashboard

- Parts 2–4 are displayed;
- charts are interactive;
- statistical results are understandable;
- dashboard reads the pipeline-created database.

## Reproducibility

From a fresh GitHub Codespace:

```bash
make setup
make pipeline
make dashboard
```

works without manual intervention.

## Testing

```bash
pytest
```

passes.

## Documentation

`README.md` includes:

- project overview;
- setup instructions;
- pipeline instructions;
- dashboard instructions;
- dashboard link or Codespaces access instructions;
- methodology;
- assumptions;
- limitations.
