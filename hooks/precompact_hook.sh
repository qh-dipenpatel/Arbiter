#!/usr/bin/env bash
# precompact_hook.sh
# Author: Dipen Patel
# Date: 2026-09-08
# Scope: Claude Code PreCompact hook. Fires before context window compression.
#        Reminds Claude to checkpoint session state before compacting so nothing is lost.

cat <<'EOF'
<precompact_warning>
CONTEXT WINDOW COMPRESSION IMMINENT.

Before compacting: run /save to checkpoint session state to vault.
If /save is not possible, write a brief summary of:
  - What was decided this session
  - What work was done (files created or changed, commands run)
  - What is still pending

After /save or summary: proceed with compaction.
</precompact_warning>
EOF

exit 0
