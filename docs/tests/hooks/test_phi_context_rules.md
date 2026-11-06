---
doc_type: test
catalog_type: code_doc
doc_role: test
indexable: true
indexed: null
repo: "Arbiter"
source_file: "tests/hooks/test_phi_context_rules.py"
status: ACTIVE
last_updated: 2026-11-06
scores: []
covers: ["hooks/phi_patterns.py"]
tags: [phi, context-rules, performance]
links: []
---

## Purpose

Tests the PHI context rules: name anchors, clue pairs, the pairing window, and the chunked scan. {src:tests/hooks/test_phi_context_rules.py:4} Every value comes from `fake_phi.py` and is built at run time, so no sample record sits in this file. {src:tests/hooks/test_phi_context_rules.py:7}

## Dependencies

Imports `fake_phi` and `clean_corpus` from the same folder, and from `hooks/phi_patterns.py` the names `CHUNK_SIZE`, `CONTEXT_WINDOW`, `CLINICAL_TERMS`, `Finding`, `Level`, `scan_for_phi`, `scan_levels` and `strongest_level`. {src:tests/hooks/test_phi_context_rules.py:19-34} Source under test: [phi_patterns](../../hooks/phi_patterns.md). Uses `unittest` and `time`.

Run: `python3 -m unittest discover -s tests/hooks -p 'test_*.py'`. {src:tests/hooks/test_phi_context_rules.py:9}

## Behavior

37 tests in seven classes. Expected results are three constants: a name finding at deny, a context finding at ask, and a lone clue finding at warn. {src:tests/hooks/test_phi_context_rules.py:36-38}

`NameAnchors` protects the name rule:

- A name label with a value denies, and a last name then first name after an anchor denies. {src:tests/hooks/test_phi_context_rules.py:test_p01_name_label_with_value_denies} {src:tests/hooks/test_phi_context_rules.py:test_p02_last_first_after_anchor_denies}
- The anchor and the value on different lines give the same result as one line. {src:tests/hooks/test_phi_context_rules.py:test_p15_anchor_and_value_on_different_lines}
- Upper case text, extra spaces and tabs still deny, and a spaced out upper case address is still flagged as an address. {src:tests/hooks/test_phi_context_rules.py:test_p16_upper_case_extra_spaces_and_tabs}
- A JSON style name field is found. {src:tests/hooks/test_phi_context_rules.py:test_json_style_value}
- The older `scan_for_phi` function does not see the name rule. {src:tests/hooks/test_phi_context_rules.py:test_scan_for_phi_does_not_see_the_name_rule}
- Headings, placeholders, SQL column names and class names are quiet. {src:tests/hooks/test_phi_context_rules.py:test_headings_and_placeholders_are_quiet} {src:tests/hooks/test_phi_context_rules.py:test_sql_and_class_names_are_quiet}

`ClueCombinations` protects the pair rule. Two different kinds of clue close together give ask:

- A titled name with a clinical phrase, a street part with a clinical term, a name with an event date, an age and sex phrase with a clinical phrase, an age in years with a clinical term, and a name with a diagnosed phrase. {src:tests/hooks/test_phi_context_rules.py:test_p03_title_name_with_clinical_phrase_asks} {src:tests/hooks/test_phi_context_rules.py:test_p05_street_part_with_clinical_term_asks} {src:tests/hooks/test_phi_context_rules.py:test_p11_name_with_event_date_asks} {src:tests/hooks/test_phi_context_rules.py:test_p12_age_sex_with_clinical_phrase_asks} {src:tests/hooks/test_phi_context_rules.py:test_p13_age_yo_with_clinical_term_asks} {src:tests/hooks/test_phi_context_rules.py:test_p14_name_with_diagnosed_phrase_asks}
- An unlabeled phone alone only warns. With a clinical term the strongest level is ask and a context finding is present. {src:tests/hooks/test_phi_context_rules.py:test_p07_unlabeled_phone_alone_only_warns} {src:tests/hooks/test_phi_context_rules.py:test_p08_phone_with_clinical_term_asks}
- A titled name, an age and sex phrase, or an event date alone only warns. {src:tests/hooks/test_phi_context_rules.py:test_lone_clues_only_warn}
- A street alone and a clinical phrase alone are quiet. {src:tests/hooks/test_phi_context_rules.py:test_lone_street_and_clinical_terms_are_quiet}
- Two clues of the same kind do not pair. An event date is not its own second clue. {src:tests/hooks/test_phi_context_rules.py:test_same_kind_twice_does_not_pair} {src:tests/hooks/test_phi_context_rules.py:test_event_word_is_not_its_own_second_clue}
- A pair in upper case still asks. {src:tests/hooks/test_phi_context_rules.py:test_p16_upper_case_pair_still_asks}

`WindowLogic` protects the pairing distance:

- A pair with a gap of half the context window asks. A pair with a gap of twice the window is not paired and only warns. {src:tests/hooks/test_phi_context_rules.py:test_inside_window_asks} {src:tests/hooks/test_phi_context_rules.py:test_far_apart_is_not_paired}
- The clinical term list holds between 35 and 45 entries. {src:tests/hooks/test_phi_context_rules.py:test_clinical_list_is_generic_and_about_forty}

`NegativeGuards` protects against false alarms. These are quiet: headings, class and column names, clinical identifiers alone, a phrase about years of support, a year old item without a sex word, and the whole clean corpus. {src:tests/hooks/test_phi_context_rules.py:test_n01_headings} {src:tests/hooks/test_phi_context_rules.py:test_n02_class_and_column_names} {src:tests/hooks/test_phi_context_rules.py:test_n06_clinical_identifiers_alone} {src:tests/hooks/test_phi_context_rules.py:test_n08_years_of_support} {src:tests/hooks/test_phi_context_rules.py:test_year_old_without_sex_is_quiet} {src:tests/hooks/test_phi_context_rules.py:test_clean_corpus_stays_quiet}

`ChunkedScan` protects the split of large input into chunks:

- A name label and a clue pair that straddle a chunk boundary are still found. {src:tests/hooks/test_phi_context_rules.py:test_name_label_across_a_chunk_boundary} {src:tests/hooks/test_phi_context_rules.py:test_pair_across_a_chunk_boundary}
- A payload placed after three chunks of filler is not skipped. {src:tests/hooks/test_phi_context_rules.py:test_payload_past_the_first_chunk_is_not_skipped}
- Clean input twice the chunk size finishes under 5 seconds. {src:tests/hooks/test_phi_context_rules.py:test_large_clean_input_finishes} {src:tests/hooks/test_phi_context_rules.py:39}

`BoundedMatching` protects against slow pattern matching. Each input must scan in under 5 seconds: long runs of capitalized words after an anchor or a title, a long run of numbers before an age phrase, and long repeated separator, event date and clinical phrase runs, each repeated 3000 times. {src:tests/hooks/test_phi_context_rules.py:test_long_capitalized_runs} {src:tests/hooks/test_phi_context_rules.py:test_long_separator_and_event_runs} {src:tests/hooks/test_phi_context_rules.py:39-40}

`SourceFilesStayFake` protects the scaffolding: this test file and `fake_phi.py` produce no findings when scanned. {src:tests/hooks/test_phi_context_rules.py:test_this_file_and_builders_are_quiet}

What a failure means: a context rule now misses a name or pair (a possible leak), flags plain engineering text, pairs clues across too large a gap, loses a match at a chunk edge, or slows down enough to stall a hook.

## Diagram

<!-- Simple unit tests, no diagram needed. -->

## Notes

The speed tests use a wall clock limit of 5 seconds, so a heavily loaded machine could fail them without a real regression. {src:tests/hooks/test_phi_context_rules.py:39} Test names with a `p` or `n` number prefix refer to numbered cases in a rule list that is not in this file. {unverified} Baseline behavior is covered separately in [test_phi_baseline](test_phi_baseline.md).
