#!/usr/bin/env python3
"""
Author: Dipen Patel
Date: 2026-09-23
Scope: merge Arbiter's settings.json template into ~/.claude/settings.json without
       destroying the user's own settings
Ticket: none (Arbiter is not Jira tracked)
ChangeLog:
  2026-09-23  Created. Replaces the sed overwrite in install.sh, which discarded every
              user key (hooks, permissions, env, model, plugins, statusLine).

Rules:
  - Placeholders ($CLAUDE_DOTFILES, $ARBITER_KNOWLEDGE, $QH_SCRIPTS) are substituted inside
    parsed JSON strings, so paths with quotes or backslashes cannot break the JSON.
  - hooks: Arbiter owned hook groups (any command whose file name is an Arbiter hook) are
    removed, including stale paths from a moved repo, then the template groups are added.
    User hook groups are kept untouched.
  - permissions allow/ask/deny and additionalDirectories: union, order preserved.
  - env: ARBITER_KNOWLEDGE, ARBITER_CODE_DIR, CLAUDE_DOTFILES set (GUI launched editors do
    not load the shell profile). Other env keys kept.
  - Any other key: user value wins; template adds keys the user does not have.
  - Unreadable existing file: backed up by the caller, merge starts from {} and says so.
  - Write is atomic (temp file + os.replace) and goes through symlinks to the real file.

Usage: merge_settings.py TEMPLATE TARGET REPO_DIR VAULT_DIR SCRIPTS_DIR CODE_DIR
"""

from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile

LIST_PERMISSION_KEYS = ("allow", "ask", "deny", "additionalDirectories")


def substitute(node: object, values: dict[str, str]) -> object:
    """Replace placeholders in every string of a parsed JSON tree."""
    if isinstance(node, str):
        for key, value in values.items():
            node = node.replace(key, value)
        return node
    if isinstance(node, list):
        return [substitute(item, values) for item in node]
    if isinstance(node, dict):
        return {k: substitute(v, values) for k, v in node.items()}
    return node


def hook_basenames(hooks: dict) -> set[str]:
    names = set()
    for groups in hooks.values():
        for group in groups:
            for hook in group.get("hooks", []):
                names.add(command_basename(hook.get("command", "")))
    return names - {""}


def command_basename(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    return os.path.basename(parts[0]) if parts else ""


def merge_hooks(user: dict, template: dict) -> dict:
    """Drop Arbiter owned groups from the user's hooks, then append the template's."""
    owned = hook_basenames(template)
    merged: dict[str, list] = {}
    for event, groups in user.items():
        kept = [g for g in groups
                if not any(command_basename(h.get("command", "")) in owned for h in g.get("hooks", []))]
        if kept:
            merged[event] = kept
    for event, groups in template.items():
        merged.setdefault(event, []).extend(groups)
    return merged


def union(first: list, second: list) -> list:
    return first + [item for item in second if item not in first]


def merge(user: dict, template: dict, env: dict[str, str]) -> dict:
    result = dict(user)
    for key, value in template.items():
        if key not in ("hooks", "permissions", "env"):
            result.setdefault(key, value)
    result["hooks"] = merge_hooks(user.get("hooks") or {}, template.get("hooks") or {})
    perms = dict(user.get("permissions") or {})
    for key, value in (template.get("permissions") or {}).items():
        if key in LIST_PERMISSION_KEYS:
            perms[key] = union(perms.get(key) or [], value)
        else:
            perms.setdefault(key, value)
    result["permissions"] = perms
    result["env"] = {**(user.get("env") or {}), **(template.get("env") or {}), **env}
    return result


def load_user(target: str) -> dict:
    if not os.path.exists(target):
        return {}
    try:
        with open(target) as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        print(f"  Existing {target} is not valid JSON; starting from empty (backup kept).", file=sys.stderr)
        return {}


def write_atomic(target: str, data: dict) -> None:
    real = os.path.realpath(target)
    os.makedirs(os.path.dirname(real), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(real), prefix=".settings.", suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, real)


def main(argv: list[str]) -> int:
    if len(argv) != 7:
        print(__doc__.strip().splitlines()[-1], file=sys.stderr)
        return 2
    template_path, target, repo_dir, vault_dir, scripts_dir, code_dir = argv[1:]
    with open(template_path) as fh:
        template = json.load(fh)
    template = substitute(template, {
        "$CLAUDE_DOTFILES": repo_dir, "$ARBITER_KNOWLEDGE": vault_dir, "$QH_SCRIPTS": scripts_dir})
    env = {"ARBITER_KNOWLEDGE": vault_dir, "ARBITER_CODE_DIR": code_dir, "CLAUDE_DOTFILES": repo_dir}
    write_atomic(target, merge(load_user(target), template, env))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
