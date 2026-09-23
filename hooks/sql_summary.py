"""
Author: Dipen Patel
Date: 2026-09-23
Scope: summarize what data a SQL statement pulls, for the Databricks approval prompt
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created. Standard library only; handles plain SELECT. Anything else
              (CTE, subquery, multiple statements) is reported as unparsed, never guessed.

Not a hook. Imported by pre-tool-bash-databricks-ask.py.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from phi_patterns import phi_column

AGGREGATE_FUNCS = re.compile(r'\b(?:count|sum|avg|min|max|approx_count_distinct)\s*\(', re.IGNORECASE)
WRITE_VERBS = re.compile(r'^\s*(?:insert|update|delete|merge|drop|create|alter|truncate|replace|grant|revoke)\b', re.IGNORECASE)
IDENT = re.compile(r'`[^`]+`|[A-Za-z_][\w]*')
TABLE_REF = re.compile(r'\b(?:from|join)\s+((?:`[^`]+`|[\w]+)(?:\.(?:`[^`]+`|[\w]+)){0,2})', re.IGNORECASE)
SELECT_SHAPE = re.compile(
    r'^\s*select\s+(?:distinct\s+)?(?P<cols>.+?)\s+from\s+(?P<rest>.+?)\s*;?\s*$',
    re.IGNORECASE | re.DOTALL,
)
CLAUSE = r'\b(?:where|group\s+by|having|order\s+by|limit)\b'
MAX_SHOWN = 12
PROD_CATALOG = re.compile(r'(?:^|[_\-])prod(?:$|[_\-])', re.IGNORECASE)


@dataclass
class SqlSummary:
    parsed: bool
    modifies_data: bool = False
    tables: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    all_columns: bool = False
    filter: str = ""
    aggregated: bool = False
    limit: str = ""
    phi_columns: list[str] = field(default_factory=list)


def _strip_comments(sql: str) -> str:
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.DOTALL)
    return re.sub(r'--[^\n]*', ' ', sql).strip()


def _split_top_level(text: str) -> list[str]:
    """Split on commas not inside parentheses."""
    parts, depth, current = [], 0, []
    for ch in text:
        depth += ch == '('
        depth -= ch == ')'
        if ch == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    parts.append(''.join(current).strip())
    return [p for p in parts if p]


def _clause(rest: str, name: str) -> str:
    match = re.search(rf'\b{name}\b\s+(.+?)(?={CLAUSE}|$)', rest, re.IGNORECASE | re.DOTALL)
    return ' '.join(match.group(1).split()) if match else ""


def _phi_identifiers(*texts: str) -> list[str]:
    found = {tok.strip('`') for text in texts for tok in IDENT.findall(text) if phi_column(tok.strip('`'))}
    return sorted(found)


def summarize_sql(sql: str) -> SqlSummary:
    sql = _strip_comments(sql)
    body = sql.rstrip(';').strip()
    if WRITE_VERBS.match(body):
        return SqlSummary(parsed=False, modifies_data=True, tables=TABLE_REF.findall(body))
    match = SELECT_SHAPE.match(body)
    if not match or ';' in body or re.match(r'^\s*with\b', body, re.IGNORECASE) \
            or re.search(r'\(\s*select\b', body, re.IGNORECASE):
        return SqlSummary(parsed=False, tables=TABLE_REF.findall(body))
    cols = _split_top_level(match.group('cols'))
    rest = match.group('rest')
    where = _clause(rest, 'where')
    limit = _clause(rest, 'limit')
    return SqlSummary(
        parsed=True,
        tables=TABLE_REF.findall(body),
        columns=cols,
        all_columns=any(c == '*' or c.endswith('.*') for c in cols),
        filter=where,
        aggregated=bool(AGGREGATE_FUNCS.search(match.group('cols')) or _clause(rest, r'group\s+by')),
        limit=limit.split()[0] if limit else "",
        phi_columns=_phi_identifiers(match.group('cols'), where),
    )


def _column_line(s: SqlSummary) -> str:
    if s.all_columns:
        return "ALL columns (*), cannot rule out PHI"
    shown = ", ".join(s.columns[:MAX_SHOWN])
    return shown + (f" (+{len(s.columns) - MAX_SHOWN} more)" if len(s.columns) > MAX_SHOWN else "")


def _tables_line(s: SqlSummary) -> str:
    tables = ", ".join(s.tables) or "unknown"
    prod = any(PROD_CATALOG.search(t.split('.')[0]) for t in s.tables if t.count('.') == 2)
    return tables + ("  ⚠ PRODUCTION catalog" if prod else "")


def format_sql_summary(s: SqlSummary) -> list[str]:
    """Lines for the approval prompt. Parsed facts only; never inferred."""
    tables = _tables_line(s)
    if s.modifies_data:
        return ["  ⚠ MODIFIES DATA (write statement)", f"  Tables:   {tables}"]
    if not s.parsed:
        return ["  Could not parse, review the SQL below.", f"  Tables seen: {tables}"]
    phi = "⚠ " + ", ".join(s.phi_columns) + " requested" if s.phi_columns else "no known PHI columns requested"
    if s.all_columns and not s.phi_columns:
        phi = "⚠ unknown (ALL columns requested)"
    shape = "aggregated" if s.aggregated else "row level (not aggregated)"
    return [
        f"  Tables:   {tables}",
        f"  Columns:  {_column_line(s)}",
        f"  Filter:   {s.filter or 'none (whole table)'}",
        f"  Shape:    {shape}, " + (f"LIMIT {s.limit}" if s.limit else "⚠ no LIMIT"),
        f"  PHI:      {phi}",
    ]
