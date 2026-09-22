#!/usr/bin/env bash
# Trigger: PreToolUse — Write|Edit|MultiEdit
# Scope: file_path in Write/Edit/MultiEdit tool_input; checks against ARBITER_CODE_DIR
# Action: block writes to the read-only code reference directory
# On block: prints JSON with permissionDecision:deny + permissionDecisionReason, then exit 0
# If filter: none — Write|Edit|MultiEdit matcher limits scope; path check is O(1)

# Feature disabled if ARBITER_CODE_DIR not configured
if [ -z "${ARBITER_CODE_DIR:-}" ]; then
    exit 0
fi

# Read full stdin payload; parse file_path with Python to handle JSON safely
PAYLOAD=$(cat)

FILE_PATH=$(echo "$PAYLOAD" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('tool_input', {}).get('file_path', ''))
except Exception:
    print('')
" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Normalize paths with symlink resolution. Both sides use realpath for consistent comparison;
# Python os.path.realpath handles non-existent paths on macOS where GNU realpath -m is unavailable.
CODE_DIR_NORM="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$ARBITER_CODE_DIR" 2>/dev/null || echo "$ARBITER_CODE_DIR")"
FILE_PATH_NORM="$(python3 -c "import os,sys; print(os.path.realpath(sys.argv[1]))" "$FILE_PATH" 2>/dev/null || echo "$FILE_PATH")"

# Add trailing slash to CODE_DIR to prevent prefix false-positives (e.g. /code vs /codebackup)
CODE_DIR_PREFIX="${CODE_DIR_NORM%/}/"

if [[ "$FILE_PATH_NORM/" == "$CODE_DIR_PREFIX"* ]] || [[ "$FILE_PATH_NORM" == "$CODE_DIR_NORM" ]]; then
    python3 -c "
import json
result = {
    'hookSpecificOutput': {
        'permissionDecision': 'deny',
        'permissionDecisionReason': 'Write blocked: target path is under ARBITER_CODE_DIR (read-only RAG source). Work in your dev directory instead.'
    }
}
print(json.dumps(result))
"
fi

exit 0
