#!/usr/bin/env bash
# Trigger: PreCompact — all (no matcher)
# Scope: every context window compression event
# Action: write checkpoint reminder to Claude Code's debug log before compaction fires
# On result: exit 0 always — never blocks; stdout goes to debug log only, NOT to Claude's context or user terminal
# Note: PreCompact hooks cannot inject into Claude's context (feature request #43733 closed)
# Note: the only user-visible PreCompact signal is exit 2 + stderr, which hard-blocks compaction
# If filter: none — PreCompact fires rarely; spawn cost is negligible

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
