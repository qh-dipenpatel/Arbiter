#!/usr/bin/env bash
# vault_search_hook.sh
# Author: Dipen Patel
# Date: 2026-09-08
# Scope: Claude Code UserPromptSubmit hook. Runs vector search against the vault
#        before every prompt and injects matching chunks as a <vault_context> block.
#        Claude sees the context without spending a turn deciding whether to search.
# Requires: CLAUDE_DOTFILES and ARBITER_KNOWLEDGE env vars (set by install.sh).

QUERY_SCRIPT="${CLAUDE_DOTFILES}/rag/query_index.py"
INDEX_PATH="${ARBITER_KNOWLEDGE}/.rag_index"
MIN_SCORE="0.40"
TOP="3"
MIN_PROMPT_CHARS=25

# Bail early if env vars or files are missing — never block the prompt
if [ -z "${CLAUDE_DOTFILES:-}" ] || [ -z "${ARBITER_KNOWLEDGE:-}" ]; then
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

# Skip skill invocations — /start, /ticket, /close, etc. manage their own context
if echo "$PROMPT" | grep -qE '^\s*/[a-zA-Z]'; then
    exit 0
fi

# Run vector search
RESULTS=$(python3 "$QUERY_SCRIPT" "$PROMPT" \
    --top "$TOP" \
    --min-score "$MIN_SCORE" \
    --index "$INDEX_PATH" 2>/dev/null)

if [ -z "$RESULTS" ] || echo "$RESULTS" | grep -q '"error"'; then
    exit 0
fi

RESULT_COUNT=$(echo "$RESULTS" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(len(data))
except:
    print(0)
" 2>/dev/null)

if [ "${RESULT_COUNT:-0}" -eq 0 ]; then
    exit 0
fi

# Format results as a compact context block.
# [V] = VERIFIED (decisions, RCA), [D] = DOCUMENTED (tickets, system map), [O] = OBSERVED (meetings)
echo "$RESULTS" | python3 -c "
import sys, json

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
        lines.append(f\"{icon} {score:.2f}  {file_}\")
        lines.append(f\"  {excerpt}\")
        lines.append('')
    lines.append('</vault_context>')
    print('\n'.join(lines))
except:
    sys.exit(0)
" 2>/dev/null

exit 0
