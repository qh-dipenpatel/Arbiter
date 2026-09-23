#!/usr/bin/env bash
# Trigger: UserPromptSubmit — all (no matcher)
# Scope: user prompts longer than 25 chars, excluding skill invocations (/command)
# Action: vector search vault, inject matching chunks as <vault_context> block
# On result: exit 0 always — never blocks; vault context injected via stdout
# PHI: excerpts matching shared PHI patterns (phi_patterns.py) are withheld, never injected
# If filter: none — prompt content is not available at if-evaluation time

HOOKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HOOKS_DIR/.." && pwd)"

QUERY_SCRIPT="${REPO_DIR}/rag/query_index.py"
INDEX_PATH="${ARBITER_KNOWLEDGE}/.rag_index"
MIN_SCORE="0.40"
TOP="3"
MIN_PROMPT_CHARS=25

# Bail early if env vars or files are missing — never block the prompt
if [ -z "${ARBITER_KNOWLEDGE:-}" ]; then
    exit 0
fi

if [ ! -f "$QUERY_SCRIPT" ] || [ ! -d "$INDEX_PATH" ]; then
    exit 0
fi

# Read JSON payload from Claude Code (fields: session_id, transcript_path, prompt)
INPUT=$(cat)
PROMPT=$(echo "$INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('prompt', ''))
except:
    print('')
" 2>/dev/null)

# Skip prompts that are too short to be meaningful
if [ "${#PROMPT}" -lt "$MIN_PROMPT_CHARS" ]; then
    exit 0
fi

# Skip skill invocations — /start, /ticket, /close, etc. manage their own context.
# First line only: a later line starting with a path must not skip the search.
if printf '%s\n' "$PROMPT" | head -n 1 | grep -qE '^\s*/[a-zA-Z]'; then
    exit 0
fi

# Run vector search
RESULTS=$(python3 "$QUERY_SCRIPT" "$PROMPT" \
    --top "$TOP" \
    --min-score "$MIN_SCORE" \
    --index "$INDEX_PATH" 2>/dev/null)

if [ -z "$RESULTS" ]; then
    exit 0
fi

# Validate JSON and count results via Python. grep-based '"error"' check is avoided because
# any vault document mentioning "error" (RCAs, error-handling notes) triggers a false positive.
RESULT_COUNT=$(echo "$RESULTS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        print(0)
    else:
        print(len(data))
except Exception:
    print(0)
" 2>/dev/null)

if [ "${RESULT_COUNT:-0}" -eq 0 ]; then
    exit 0
fi

# Format results as a compact context block.
# [V] = VERIFIED (decisions, RCA), [D] = DOCUMENTED (tickets, system map), [O] = OBSERVED (meetings)
echo "$RESULTS" | python3 -c "
import sys, json
sys.path.insert(0, sys.argv[1])
from phi_patterns import scan_for_phi, scan_structured

TIER_ICONS = {1: '[V]', 2: '[D]', 3: '[O]'}

try:
    results = json.load(sys.stdin)
    if not results:
        sys.exit(0)
    lines = ['<vault_context>']
    for r in results:
        icon = TIER_ICONS.get(r.get('tier', 2), '[D]')
        score = r.get('score', 0)
        file_ = r.get('file', '')
        excerpt = r.get('excerpt', '')[:200].strip()
        if scan_for_phi([excerpt]) + scan_structured([excerpt]):
            excerpt = '[excerpt withheld: PHI pattern detected in vault file, review and clean it]'
        lines.append(f\"{icon} {score:.2f}  {file_}\")
        lines.append(f\"  {excerpt}\")
        lines.append('')
    lines.append('</vault_context>')
    print('\n'.join(lines))
except Exception:
    sys.exit(0)
" "$HOOKS_DIR" 2>/dev/null

exit 0
