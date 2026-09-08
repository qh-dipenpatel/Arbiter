#!/usr/bin/env bash
# scrub-secrets.sh — PostToolUse hook wrapper: detects and redacts credentials in Bash output.
# Author: DJP
# Date: 2026-08-11
# Scope: Claude Code PostToolUse hook on Bash. Fires after every Bash call before result is used by model.
# Implementation: delegates to scrub-secrets.py in the same directory (avoids stdin conflict with heredoc).

exec python3 "$(dirname "$0")/scrub-secrets.py"
