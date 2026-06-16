# Pipeline Standards

**What this is:** The team's rule book for pipeline architecture — the layered medallion design, write semantics, layer boundaries, ingestion patterns, schema lineage. Read by every Tier 5 skill in Step 0 alongside `technical-standards.md`.

**Audience:** You and Claude. Companion to `technical-standards.md`. Will be the source document when pipeline standards are lifted into a team-facing version under S-57.

**When it updates:** When a pipeline pattern proves itself across a second client, or when a correction generates the same fix twice, harden it. Rules stay in the team's language.

---

## The Frame

Every pipeline at Acme Healthcare AI Solutions delivers data that a clinician will read. A wrong record is worse than a missing record. A pipeline that drops the wrong patient silently is worse than one that fails loudly. Every rule below exists to make failures loud, recoverable, and explainable.

---

## Layer Boundaries

**Rule 1 — Raw, Bronze, Silver each have one responsibility.** Raw lands source data unchanged. Bronze standardizes and validates. Silver shapes the data for the product. A skill proposing a change states which layer it touches. Mixing responsibilities across layers is the most common cause of pipelines that work in dev and break in production.

**Rule 2 — Use "layer" not "stage" in all docs and folder names.** Memory `[feedback_use_layers_not_stages]`. Drift in vocabulary becomes drift in the mental model.

**Rule 3 — Raw is append-only and immutable.** No deletes, no updates, no overwrites. Every load is an append. The Raw layer is the source of truth for what arrived and when. If the source needs correction, the Raw record stands — the correction happens in Bronze.

**Rule 4 — Indicator columns live on Bronze and Silver, never on Raw.** `quarantine_ind`, `delete_ind`, `process_ind`, `filter_ind` are Bronze/Silver concerns. Raw is the immutable ledger. See memory `[feedback_indicator_columns_layer]`.

**Rule 5 — Source-bound ingestion, not product-bound.** Raw tables serve all products. Never name an ingestion path after a product (no `raw_[procedure]` — it is `raw_[client]` and [PROCEDURE]-specific logic starts at Bronze). See memory `[feedback_source_bound_ingestion]`.

---

## Write Semantics

**Rule 6 — Every write mode is stated explicitly at the call site.** No defaults. `mode("append")`, `mode("overwrite")` with `replaceWhere`, or `MERGE INTO` with explicit match conditions. A write without an explicit mode is rejected at QA.

**Rule 7 — `overwrite` without `replaceWhere` replaces the entire table.** Know this every time you write it. If the intent is partition-level replacement, `replaceWhere` is required. Tier 5 skills are extra careful here.

**Rule 8 — Idempotency at every layer.** Every layer survives a rerun without producing duplicates or wrong totals. The pipeline can be replayed from any starting point without breaking downstream. Design states the idempotency mechanism: append + deduplication key, MERGE with match condition, or `replaceWhere` on a partition.

**Rule 9 — Null handling is explicit at every join, filter, and `withColumn`.** Joins state what happens to null keys. Filters state what happens to null values. `withColumn` states the null behavior of the expression. Implicit null handling is the most common cause of patients silently disappearing from the output.

---

## Ingestion Patterns

**Rule 10 — Ingestion notebooks contain no DDL.** No `CREATE TABLE`. No `CREATE SCHEMA`. No `ALTER`. Provisioning is a separate setup script. Cell 6 of an ingestion notebook is DESCRIBE checks only. See memory `[feedback_ingestion_notebook_no_ddl]`, `[feedback_pipelines_must_not_create_schemas]`.

**Rule 11 — One pipeline YAML drives all layers.** One YAML per client, all layers configured in it. Job parameters are two only: environment + config_path. See memory `[feedback_pipeline_yaml_all_layers]`.

**Rule 12 — Master schema is separate from data schemas.** `file_registry`, `ingestion_runs`, `table_metrics`, and similar metadata tables live in `{client}_master`, never in `raw_*` or `bronze_*`. See memory `[feedback_master_schema_separate]`.

**Rule 13 — Pipeline handles compressed files transparently.** ZIP, GZ, or any other compression is extracted by the pipeline. Never asking the user to extract manually. The Azure SDK does this in the notebook. See memory `[feedback_pipeline_handle_zips]`.

**Rule 14 — Connect to the existing pipeline framework.** All new work integrates with the existing YAML framework. No parallel systems. See memory `[feedback_connect_to_existing_pipeline]`.

---

## Schema Lineage and Integrity

**Rule 15 — Schema lineage from source through Silver.** Every Silver column traces back to a specific Raw column (or a documented derivation). The chain is explicit and verifiable. When a Silver field is wrong, the trace is how the diagnosis starts.

**Rule 16 — Verify the Silver schema before any change, not the Raw view.** Pipelines use `silver_std_*` tables; Raw `_vw` columns differ. Memory `[feedback_verify_silver_not_raw]`. The STATUSNAME incident (2026-04-22) is the canonical case.

**Rule 17 — End-to-end layer validation before any fix.** Always trace Raw → Bronze → Silver → Output. Never assume the data flows cleanly between layers. Memory `[feedback_end_to_end_layer_validation]`.

**Rule 18 — Patient data integrity is non-negotiable.** Missing data is acceptable. Wrong patient data is never acceptable. Semi-join every source branch, verify the MRN key on every join. Memory `[feedback_patient_data_integrity]`.

**Rule 19 — Anchor column varies by view.** [CLIENT] views use five different patient-ID column names. Run dual-anchor profiling before configuring any join. Memory `[feedback_orphan_check_per_rule_anchor]`.

---

## Validation and QA

**Rule 20 — Validator must use independent logic.** Never copy pipeline SQL into the validator. Raw-to-final-output analysis only. Test sharing implementation has zero detection power. Memory `[feedback_validator_independent_logic]`.

**Rule 21 — Accuracy validation targets raw columns only.** Raw validation rules always target source views (e.g., `chn_dev`). Silver comparison is a separate workstream. Memory `[feedback_accuracy_validation_raw_only]`.

**Rule 22 — Use `CURRENT_DATE()` for historical date upper bounds.** Never hardcoded year. Memory `[feedback_current_date_upper_bound_validation]`.

**Rule 23 — `PROCCODE` is internal IMG-prefix codes, not CPT.** Never group with CPT in any analysis. Memory `[feedback_proccode_not_cpt]`.

**Rule 24 — pandas strips leading zeros from MRN columns.** Use `dtype=str` on any MRN read. Memory `[feedback_pandas_mrn_dtype_str]`.

---

## Cross-Client Design

**Rule 25 — Every architecture choice must work across all clients and interface types.** No one-client special cases without writing down the constraint. Memory `[feedback_design_for_all_clients]`.

**Rule 26 — Cost-aware Delta Share.** Delta Share costs money per query. The new architecture persists Raw locally with hash-based delta detection. Memory `[feedback_zero_copy_no_accumulation]`.

**Rule 27 — Tables before logic.** DDL first, notebooks second. Structures before processes. Memory `[feedback_tables_before_logic]`.

---

## When This File Updates

When a pipeline pattern proves itself across two clients, harden it. When a correction generates the same fix twice, harden it. Memory slugs are the audit trail back to the source incident. Rules stay in the team's language.
