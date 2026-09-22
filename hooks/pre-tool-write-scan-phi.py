#!/usr/bin/env python3
"""
Trigger: PreToolUse — Write|Edit|MultiEdit
Scope: text content being written to disk by Write, Edit, and MultiEdit tools
Action: scan content for PHI patterns (MRN, SSN, DOB, patient identifiers); block if found
On block: prints JSON with permissionDecision:deny + permissionDecisionReason, then exit 0
If filter: none — Write|Edit|MultiEdit matcher already limits scope; PHI scan is fast
"""

import json
import re
import sys


PHI_PATTERNS = [
    (r'\bMRN[:\s#\-]*\d{5,10}\b', 'MRN'),
    (r'\b(?:SSN|social[\s_]security(?:[\s_]number)?)[,:\s][^.\n\d]{0,25}\d{3}[-\s]\d{2}[-\s]\d{4}\b', 'SSN'),
    (r'\b(?:DOB|date[\s_]of[\s_]birth|birth[\s_]date|born)[:\s]+\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b', 'DOB'),
    (r'\b(?:patient|member|pt)[\s_]?id[:\s]+\d+\b', 'PATIENT_ID'),
    (r'\bNPI[:\s]+\d{10}\b', 'NPI'),
    (r'\b(?:insurance[\s_]?id|policy[\s_]?number|subscriber[\s_]?id)[:\s]+[A-Za-z0-9\-]{6,20}\b', 'INSURANCE_ID'),
]

COMPILED = [(re.compile(pat, re.IGNORECASE), label) for pat, label in PHI_PATTERNS]


def extract_content(payload: dict) -> list[str]:
    tool = payload.get('tool_name', '')
    inp = payload.get('tool_input', {})
    texts = []
    if tool == 'Write':
        content = inp.get('content', '')
        if content:
            texts.append(content)
    elif tool == 'Edit':
        new_str = inp.get('new_string', '')
        if new_str:
            texts.append(new_str)
    elif tool == 'MultiEdit':
        for edit in inp.get('edits', []):
            new_str = edit.get('new_string', '')
            if new_str:
                texts.append(new_str)
    return texts


def scan_for_phi(texts: list[str]) -> list[str]:
    found = set()
    for text in texts:
        for pattern, label in COMPILED:
            if pattern.search(text):
                found.add(label)
    return sorted(found)


def main() -> None:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except Exception:
        sys.exit(0)

    texts = extract_content(payload)
    if not texts:
        sys.exit(0)

    findings = scan_for_phi(texts)
    if not findings:
        sys.exit(0)

    types_str = ', '.join(findings)
    result = {
        'hookSpecificOutput': {
            'permissionDecision': 'deny',
            'permissionDecisionReason': f'PHI detected in write content: {types_str}. Remove PHI before writing to disk.',
        }
    }
    print(json.dumps(result))
    sys.exit(0)


main()
