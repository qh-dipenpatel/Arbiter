# Coding Standards

> **How these standards files relate:** This file is the **Python and SQL formatting detail**: idioms, structure, examples. `technical-standards.md` is the **numbered rule registry** (cross-referenced by skill chains and memory). `pipeline-standards.md` is the **pipeline architecture detail** (medallion layers, contracts). When a skill cites a rule by number, look in technical-standards.md, not here.

These standards apply to every file in every project. They exist so that code
written by any AI tool (Claude, Cursor, or any other) looks identical. The
reviewer sets the bar, not the writer. The standard is optimized for the
reviewer.

**The bar:** code that reads like prose. You follow the logic top to bottom
without decoding mechanics. Every name tells you what it is. Every function
does one job. Nothing is there without a reason.

**Voice standard for all written text in code** (comments, docstrings,
markdown cells in notebooks, and doc files) follows `claude-dotfiles/standards/voice-standard.md`
without exception. Plain English, active voice, no emojis,
conclusion first. Write the way a person talks, not the way a textbook reads.

---

## Foundational Rules (all languages)

These apply everywhere. No exceptions.

- **No dead code.** Every line has a reason to exist. Commented-out code is
  deleted, not left in place.
- **No hardcoded values.** Table names, paths, dates, thresholds, IDs go in
  config or named constants. Code is portable. Change config, not code.
- **No unapproved libraries.** Every dependency must appear in the spec before
  it appears in code. AI cannot invent a dependency mid-build.
- **No secrets in code.** Credentials go in Azure Key Vault or environment
  variables only.
- **No PHI in code artifacts.** No patient data in logs, comments, test data,
  or variable names. Ever.
- **Logical flow.** Code reads top to bottom. Execution path is visible without
  jumping. No surprises.
- **Security first.** Input validation at system boundaries. Least-privilege
  access. Sensitive fields never logged.

---

## Documentation Rules (all projects)

Every repo has a `docs/` folder at the root. Documentation ships with code and
is version-controlled with it. AI reads `docs/` before writing code in that
repo.

**Structure:**
```
repo/
  docs/
    README.md                   -- repo overview and entry point
    data_dictionary.md          -- column names, types, business meaning
    pipeline_overview.md        -- end-to-end flow and architecture
    modules/
      [module_name].md          -- one doc per major functional area
  pipelines/
    [module_name].py
```

**Rules:**
- One doc per major functional area, not one per file.
- `data_dictionary.md` defines every non-obvious column: name, source system,
  data type, business meaning, valid values.
- Documentation is written at the same time as the code, not after. When AI
  writes a module, it also produces the corresponding doc file in the same
  output. A module without a doc file is an incomplete task.
- Docs update in the same PR as the code. A code change without a doc update
  is an incomplete PR.

**Reference pattern in code:**
```python
# See: docs/modules/bronze_ingestion.md
```

Repo-relative path only. Never a personal vault path.

**Module doc template:** every `docs/modules/[name].md` follows this shape:

```markdown
# [Module Name]

**Ticket:** [JIRA-ID]
**Last updated:** YYYY-MM-DD

## What this does
[One paragraph. Plain English. What the module produces and for whom.]

## Why it exists
[The problem it solves. Reference the ticket or spec if the reasoning lives there.]

## Inputs
[What goes in: parameters, source tables, config values.]

## Outputs
[What comes out: tables written, DataFrames returned, files produced.]

## Key decisions
[Non-obvious design choices. Why this approach and not another one.
Each decision in one sentence.]
```

---

## Security Rules (all languages)

These rules apply to every file, every language, every pipeline.

### SQL Injection

Never build SQL by joining strings from external input. This is the most
common and most dangerous vulnerability in data pipelines.

```python
# BAD -- SQL injection risk. An attacker controls table_name.
df = spark.sql(f"SELECT * FROM {table_name}")

# GOOD -- validate against a known allowlist before any dynamic SQL
ALLOWED_TABLES: frozenset[str] = frozenset({"encounters", "patients", "social_history"})
if table_name not in ALLOWED_TABLES:
    raise ValueError(f"Table not permitted: {table_name}")
df = spark.sql(f"SELECT * FROM {table_name}")

# BETTER -- use the DataFrame API instead of SQL strings when possible
df = spark.table("encounters").filter(col("patient_id") == patient_id)
```

Rules:
- Never use `f"...{user_input}..."` inside `spark.sql()` without allowlist validation
- Prefer the DataFrame API over SQL strings for programmatic queries
- Every dynamic value used in a query must come from a validated constant or config,
  not from external input directly

### Input Validation

Validate all external inputs at the system boundary before they touch any query,
table write, or file operation. Internal values that come from your own config or
constants do not need validation.

```python
# External boundary -- validate here
def load_client_data(source_path: str, table_name: str) -> DataFrame:
    if not source_path.startswith(ALLOWED_SOURCE_PREFIX):
        raise ValueError(f"Source path not permitted: {source_path}")
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table not permitted: {table_name}")
    return spark.read.format("delta").load(source_path)
```

### Credentials and Secrets

No credentials, API keys, tokens, passwords, or connection strings in code.
Ever. Not even in comments. Use Azure Key Vault or environment variables only.

```python
# BAD
DB_PASSWORD = "mypassword123"

# GOOD
DB_PASSWORD = dbutils.secrets.get(scope="kv-scope", key="db-password")
```

Never print a credential value to terminal output, including while debugging.
To check whether an env var or Keychain secret is set, use presence checks only.
`${VAR:+SET}` is the only safe form: it prints SET when the variable is set and
nothing when unset. `${VAR:-DEFAULT}` is NOT a presence check: `:-` substitutes
DEFAULT only when the variable is unset, so when it IS set it prints the raw
value. Never use `security find-generic-password -w` to inspect a key; to confirm
a key authenticates, read it into a variable and make a real API call that prints
only the HTTP status.

```bash
# BAD: leaks the value whenever the variable is set
echo "${API_KEY:+SET}${API_KEY:-UNSET}"

# GOOD: presence only, never prints the value
echo "${API_KEY:+SET}"
[ -z "${API_KEY:-}" ] && echo "unset"
```

### PHI and Sensitive Data

PHI never appears in log output, error messages, variable values printed to
console, or comments. If a field contains patient data, log the count or the
field name only. Never the value.

```python
# BAD -- PHI in log
logging.info("Processing patient %s born %s", mrn, date_of_birth)

# GOOD -- count only
logging.info("Processing %d patient records", record_count)
```

### No Unsafe File Formats

Never read or write pickle files. Pickle can execute arbitrary code on load.
Use Delta, Parquet, or CSV instead.

```python
# BAD
df = pd.read_pickle("data.pkl")

# GOOD
df = spark.read.format("delta").load(path)
```

---

## Python Standards

**Baseline:** PEP 8 + CLAUDE.md coding rules. This section covers decisions
not resolved by the standard alone.

### Names

| What | Pattern | Example |
|---|---|---|
| Function | `verb_noun` snake_case | `load_encounters()`, `filter_active_patients()` |
| Variable | descriptive snake_case | `encounter_date`, `patient_id` |
| DataFrame | `_df` suffix, descriptive | `raw_encounters_df`, `active_patients_df` |
| Boolean | `is_` or `has_` prefix | `is_valid`, `has_encounters` |
| Constant | UPPER_SNAKE_CASE | `MAX_RETRY_COUNT`, `BRONZE_TABLE_NAME` |
| Module/file | snake_case | `bronze_ingestion.py`, `schema_registry.py` |

No abbreviations in names. `load_patient_encounters()` not `load_pe()`.
Exception: `df` suffix on DataFrames is the standard abbreviation.

**Naming diagnostic (Ousterhout, Chapter 14):** If a name is hard to write,
the function probably does too much. Naming difficulty is a design signal.
Split the function and the name becomes obvious.

### No Classes in Pipeline Code

Functions in focused modules. No classes unless the spec for that ticket
explicitly requires a class pattern (Slatkin, Item 50). Classes add inheritance
complexity that pipeline code does not need. If you feel the urge to write a
class, the module probably needs to be split into two modules instead.

### Constants and Enums

Named constants for all values that could change. No magic numbers or strings
inline in code.

For values that can only take a specific set of options, use Enum, not a
string constant. A string can be misspelled silently. An Enum cannot.

```python
from enum import Enum

class WriteMode(Enum):
    OVERWRITE = "overwrite"
    APPEND    = "append"
    MERGE     = "merge"

# Correct usage
write_bronze(df, BRONZE_TABLE, WriteMode.OVERWRITE)
```

**Config externalization nuance (Ousterhout):** Externalize values that
legitimately vary by client or environment: table names, source paths,
thresholds. Do not externalize everything just because you can. Over-configured
systems shift complexity to whoever has to set the values. Config should have
a clear owner and a clear reason.

### Type Hints

Required on every function signature. Write the signature **before** the body.
Deciding what goes in and what comes out is a design step, not an afterthought.
No exceptions.

```python
def load_encounters(path: str, start_date: str) -> DataFrame:

def validate_schema(df: DataFrame, expected_cols: list[str]) -> bool:

def write_bronze(df: DataFrame, table_name: str, mode: str = "append") -> None:
```

### Docstrings

Docstrings are interface documentation. They tell the caller what a function
does without reading the body. Every function called from outside its own module
gets a docstring. This is not a comment. It is the contract.

Short one-liner for functions whose name and signature are almost self-evident.
Multi-line Google style (PEP 257) for functions with non-trivial parameters or
behavior.

```python
def load_encounters(path: str, start_date: str) -> DataFrame:
    """Load raw encounter records from Delta path filtered by start date."""


def compute_eligibility_window(
    encounter_date: str,
    lookback_days: int,
) -> tuple[str, str]:
    """
    Compute the eligibility assessment window for a procedure candidate.

    Args:
        encounter_date: ISO date string of the qualifying encounter.
        lookback_days: Number of days to look back from encounter date.

    Returns:
        Tuple of (window_start, window_end) as ISO date strings.

    See: docs/modules/eligibility_logic.md
    """
```

### Comments

Default: no comments. The code and names say **what**. Inline comments say
**why**, but only when the why is non-obvious to any developer reading the
code six months later.

**The Pinker test (Sense of Style, Chapter 2):** Before writing a comment,
ask: does this show the reader something the code cannot show on its own?
If no, delete it.

```python
# Use OVERWRITE not APPEND: schema may drift between runs, overwrite
# resets the Delta log and prevents schema conflict errors.
df.write.format("delta").mode("overwrite").saveAsTable(table_name)
```

For complex logic, reference the docs folder instead of writing the explanation
inline:

```python
# See: docs/modules/eligibility_logic.md
result_df = compute_eligibility_window(encounter_date, lookback_days=90)
```

Never narrate what the code already shows:
```python
# BAD: load the DataFrame from the path
df = spark.read.format("delta").load(path)

# GOOD: nothing -- the line is self-explanatory
df = spark.read.format("delta").load(path)
```

### Function Structure

One function, one job. If you cannot name the function in three words or fewer,
it is doing too much. Split it until the name is obvious.

**40 lines is the ceiling, not the target.** Do not fragment a function just to
hit a line count. A function is as long as its single job requires.
(Ousterhout, Chapter 18: excessive fragmentation creates shallow functions that
are harder to follow than deeper ones.)

```python
def load_raw_encounters(path: str) -> DataFrame:
    """Load raw encounter records from Delta source."""
    return spark.read.format("delta").load(path)


def filter_active_encounters(df: DataFrame) -> DataFrame:
    """Keep only encounters with active status."""
    return df.filter(col("status") == "active")


def write_bronze_encounters(df: DataFrame, table_name: str) -> None:
    """Write validated encounter records to Bronze Delta table."""
    (
        df.write
        .format("delta")
        .mode("overwrite")
        .option("mergeSchema", "true")
        .saveAsTable(table_name)
    )
```

### File Structure

Every Python file follows this order:

```python
# ── File Header ───────────────────────────────────────────────────────────────
# Author:     [YOUR NAME]
# Date:       YYYY-MM-DD
# Scope:      [what this file does in one sentence]
# Ticket:     [JIRA-ID]
# ChangeLog:
#   YYYY-MM-DD  [INITIALS]  Initial implementation

# ── Imports ───────────────────────────────────────────────────────────────────
# Standard library first, then third-party, then internal. One blank line
# between groups.
import logging
from datetime import date

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, lit

from config import BRONZE_SCHEMA, TABLE_NAMES

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_RETRY_COUNT: int = 3
DEFAULT_WRITE_MODE: str = "overwrite"

# ── Functions ─────────────────────────────────────────────────────────────────
# Helper functions first, main logic last.

def load_raw_encounters(path: str) -> DataFrame:
    ...

def filter_active_encounters(df: DataFrame) -> DataFrame:
    ...

def write_bronze_encounters(df: DataFrame, table_name: str) -> None:
    ...

# ── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    ...

if __name__ == "__main__":
    main()
```

---

## PySpark / Databricks Standards

### Write Step by Step

Name every intermediate DataFrame. Each name tells you what the data is at
that point. Never chain more than three operations without assigning a name.

```python
# GOOD -- you can read the data lineage top to bottom
raw_df          = load_raw_encounters(source_path)
validated_df    = validate_schema(raw_df, expected_columns)
active_df       = filter_active_encounters(validated_df)
write_bronze_encounters(active_df, BRONZE_TABLE)

# BAD -- you cannot see what is happening at each step
write_bronze_encounters(
    filter_active_encounters(
        validate_schema(load_raw_encounters(source_path), expected_columns)
    ),
    BRONZE_TABLE
)
```

### Delta Write Rules

Always explicit. Never rely on defaults.

```python
df.write \
    .format("delta") \
    .mode("overwrite")                  \
    .option("mergeSchema", "true")      \
    .option("overwriteSchema", "false") \
    .saveAsTable(table_name)
```

- `mergeSchema` is always set explicitly. Schema does not auto-evolve without it.
- Write mode (`overwrite`, `append`, `merge`) is always explicit. Never inferred.

### Notebook as Atomic Stage

One notebook per pipeline stage. Each notebook does exactly one job.
Business logic lives in Python modules in `lib/`. The notebook imports from
`lib/` and calls the functions for that stage. No business logic in notebook cells.

---

## SQL Standards

**Baseline:** ANSI SQL. This section covers formatting and conventions.

### Keywords

All SQL keywords UPPERCASE.

```sql
SELECT, FROM, WHERE, INNER JOIN, LEFT OUTER JOIN, GROUP BY, ORDER BY,
HAVING, CASE, WHEN, THEN, ELSE, END, DECLARE, CAST, CONVERT,
BETWEEN, AND, OR, IN, IS NOT NULL, COUNT, ISNULL, DISTINCT
```

### Table Aliases

No AS keyword for table aliases. Alias is a meaningful lowercase abbreviation
based on the business concept, not the full table name.

```sql
FROM encounters e
FROM patients p
FROM patient_encounters pe
FROM social_history sh
FROM raw_social_history rsh
```

Table name initials are not acceptable. Use the concept name.

### Column Aliases

Always use AS. All AS keywords align vertically within the SELECT block.

```sql
SELECT
      encounter_date                    AS EncounterDate
    , patient_id                        AS PatientId
    , provider_name                     AS ProviderName
    , CASE
          WHEN status = 'A' THEN 'Active'
          ELSE 'Inactive'
      END                               AS StatusLabel
    , COUNT(1)                          AS MessageCount
```

Alias format depends on intent:

**Reporting or display query:** output is read by a person. Use CamelCase
aliases with brackets to preserve case:

```sql
SELECT
      encounter_date                    AS [EncounterDate]
    , patient_id                        AS [PatientId]
    , COUNT(1)                          AS [MessageCount]
```

**Pipeline or ETL query:** alias is the target column name. Use snake_case.
No brackets needed:

```sql
SELECT
      encounter_date                    AS encounter_date
    , patient_id                        AS patient_id
    , COUNT(1)                          AS record_count
```

Platform note: Databricks SQL uses backticks not brackets for quoted identifiers
(`` `EncounterDate` `` not `[EncounterDate]`). The rule is the same, the
character differs by platform.

### Leading Commas

Comma at the start of each column line, no space between comma and column name.
First column has no comma.

```sql
SELECT
      first_column
    , second_column
    , third_column
```

### CASE Statement

```sql
CASE
    WHEN condition_one = 'A' THEN
        'Value One'
    WHEN condition_one = 'B' THEN
        'Value Two'
    ELSE
        'Other'
END                               AS AliasName
```

- CASE on its own line
- WHEN indented 4 spaces, condition on same line
- THEN value on next line, indented 8 spaces from CASE
- ELSE on its own line, indented 4 spaces
- END on its own line, followed by AS alias aligned with SELECT list

### WHERE Clause

First condition on same line as WHERE. Each AND indented 2 spaces.

```sql
WHERE e.client_environment_id = @ClientEnvironmentId
  AND e.create_date BETWEEN @StartDate AND @EndDate
  AND e.quarantine_ind = 0
```

### JOIN

Always explicit join type. Never bare JOIN.

```sql
FROM encounters e
INNER JOIN patients p
    ON p.patient_id = e.patient_id
LEFT OUTER JOIN social_history sh
    ON sh.patient_id = e.patient_id
```

### Variable Declaration

```sql
DECLARE @StartDate   DATE = (SELECT FORMAT(GETDATE() - 2, 'MM-dd-yyyy'))
DECLARE @EndDate     DATE = (SELECT FORMAT(GETDATE(), 'MM-dd-yyyy'))
```

- DECLARE UPPERCASE
- @PascalCase variable names
- Aligned AS when declared in a block
- Grouped at top of script before first query

### Semicolons

Every statement ends with a semicolon. No exceptions. In Databricks, semicolons
are required when multiple SQL statements run in the same cell. Consistent use
in T-SQL prevents silent errors when statements are combined.

### All AI-Generated SQL Follows This Standard

This standard applies to every SQL statement AI writes: validation queries, QA
scripts, pipeline SQL, ad-hoc checks. There is no such thing as a "quick query"
that skips the standard.

---

## Open Decisions

| Decision | Default applied | Override when |
|---|---|---|
| Docs folder granularity | One doc per major functional area | Revisit when first repo is set up |
