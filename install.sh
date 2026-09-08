#!/usr/bin/env bash
# install.sh — One-button setup for Arbiter
# Run once after cloning. Safe to re-run: backs up files, skips already-done steps.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
CREDS_SCRIPT="$CLAUDE_DIR/credentials.sh"
KC_PREFIX="claude-dotfiles"
OS="$(uname -s)"   # Darwin | Linux | MINGW* | CYGWIN*

# ── Formatting ───────────────────────────────────────────────────────────────
BOLD='\033[1m'
RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
CYAN='\033[0;36m'

header() { echo -e "\n${BOLD}── $1 ──${RESET}"; }
ok()     { echo -e "  ${GREEN}✓${RESET}  $1"; }
note()   { echo -e "  ${YELLOW}→${RESET}  $1"; }
dim()    { echo -e "  ${DIM}$1${RESET}"; }
info()   { echo -e "  ${CYAN}$1${RESET}"; }

# ── Plain text prompt ────────────────────────────────────────────────────────
ask() {
  local prompt="$1"
  local default="${2:-}"
  local result
  if [ -n "$default" ]; then
    read -rp "  $prompt [$default]: " result
    echo "${result:-$default}"
  else
    read -rp "  $prompt: " result
    echo "$result"
  fi
}

# ── Cross-platform credential read ──────────────────────────────────────────
cred_read() {
  local service="${KC_PREFIX}-$1"
  case "$OS" in
    Darwin)
      security find-generic-password -a "$USER" -s "$service" -w 2>/dev/null || echo ""
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        secret-tool lookup service "$service" account "$USER" 2>/dev/null || echo ""
      else
        # Fallback: read from encrypted secrets file
        local secrets_file="$CLAUDE_DIR/.secrets"
        if [ -f "$secrets_file" ]; then
          grep "^${service}=" "$secrets_file" 2>/dev/null | cut -d= -f2- || echo ""
        else
          echo ""
        fi
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      cmdkey /list | grep -o "claude-dotfiles-$1" &>/dev/null \
        && powershell -Command "(Get-StoredCredential -Target '${service}').GetNetworkCredential().Password" 2>/dev/null \
        || echo ""
      ;;
    *) echo "";;
  esac
}

# ── Cross-platform credential write ──────────────────────────────────────────
cred_store() {
  local service="$1"
  local value="$2"
  if [ -z "$value" ]; then
    note "Skipped (empty): ${service}"
    return
  fi
  local key="${KC_PREFIX}-${service}"
  case "$OS" in
    Darwin)
      security add-generic-password -a "$USER" -s "$key" -w "$value" -U 2>/dev/null
      ok "Keychain (macOS): ${service}"
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        printf '%s' "$value" | secret-tool store --label="$key" service "$key" account "$USER" 2>/dev/null
        ok "Secret Service (Linux): ${service}"
      else
        # Fallback: append to mode-600 secrets file (line-based key=value)
        local secrets_file="$CLAUDE_DIR/.secrets"
        touch "$secrets_file" && chmod 600 "$secrets_file"
        # Remove any existing entry for this key, then append
        grep -v "^${key}=" "$secrets_file" > "${secrets_file}.tmp" 2>/dev/null || true
        echo "${key}=${value}" >> "${secrets_file}.tmp"
        mv "${secrets_file}.tmp" "$secrets_file"
        ok "Secrets file (Linux fallback): ${service}"
        note "Install secret-tool for better security: sudo apt install libsecret-tools"
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      cmdkey /generic:"$key" /user:"$USER" /pass:"$value" &>/dev/null
      ok "Credential Manager (Windows): ${service}"
      ;;
    *)
      note "Unknown OS — credential storage not supported. Token for ${service} not stored."
      ;;
  esac
}

# ── Hidden token prompt (credential-store-aware) ──────────────────────────────
ask_secret() {
  local prompt="$1"
  local service="$2"
  local result existing masked

  existing=$(cred_read "$service")

  if [ -n "$existing" ]; then
    masked="****${existing: -4}"
    read -rsp "  $prompt [stored: ${masked}, Enter to keep]: " result
    echo "" >&2
    if [ -z "$result" ]; then echo "$existing"; else echo "$result"; fi
  else
    read -rsp "  $prompt [Enter to skip]: " result
    echo "" >&2
    echo "$result"
  fi
}

# ── Connection method chooser ────────────────────────────────────────────────
# Sets global CONNECTION_CHOICE to "mcp", "api", or "skip"
CONNECTION_CHOICE=""
choose_connection() {
  local service="$1"
  local has_mcp="$2"   # "yes" or "no"
  local result

  echo ""
  info "How to connect $service:"
  if [ "$has_mcp" = "yes" ]; then
    echo "    m) MCP / browser OAuth   No token needed. Browser opens on first use."
    echo "    a) API token             Enter your token now, stored in Keychain."
  fi
  echo "    s) Skip                  Add later by re-running install.sh."
  echo ""

  while true; do
    if [ "$has_mcp" = "yes" ]; then
      read -rp "  Choice [m/a/s]: " result
      result=$(echo "$result" | tr '[:upper:]' '[:lower:]')
      case "$result" in
        m) CONNECTION_CHOICE="mcp";  return;;
        a) CONNECTION_CHOICE="api";  return;;
        s) CONNECTION_CHOICE="skip"; return;;
        *) echo "  Enter m, a, or s.";;
      esac
    else
      read -rp "  Choice [a/s]: " result
      result=$(echo "$result" | tr '[:upper:]' '[:lower:]')
      case "$result" in
        a) CONNECTION_CHOICE="api";  return;;
        s) CONNECTION_CHOICE="skip"; return;;
        *) echo "  Enter a or s.";;
      esac
    fi
  done
}

# cred_store is now cred_store — defined above with cross-platform support

# ── Backup + symlink ─────────────────────────────────────────────────────────
backup() {
  local path="$1"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    mv "$path" "$path.bak.$(date +%Y%m%d%H%M%S)"
    note "Backed up: $(basename "$path")"
  fi
}

symlink() {
  local src="$1"
  local dest="$2"
  backup "$dest"
  if [ -L "$dest" ] && [ "$(readlink "$dest")" = "$src" ]; then
    ok "Already linked: $(basename "$dest")"
  else
    ln -sf "$src" "$dest"
    ok "Linked: $(basename "$dest")"
  fi
}

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Arbiter: Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  What this does:"
echo "    1.  Collect your identity and folder preferences"
echo "    2.  Create your knowledge vault with all subfolders"
echo "    3.  Install Claude Code config (symlinks to ~/.claude)"
echo "    4.  Write your identity into CLAUDE.md"
echo "    5.  Connect each service: MCP browser auth or API token"
echo "    6.  Generate credentials loader (Keychain, no tokens in files)"
echo "    7.  Configure MCP servers"
echo "    8.  Add environment variables to your shell profile"
echo ""
echo "  Read docs/prerequisites.md before continuing."
echo "  Press Enter to accept defaults shown in [brackets]."
echo ""
echo "  Built by Dipen Patel. Questions? Contact Dipen via Slack or Email."
echo ""
read -rp "  Ready? Press Enter to continue (or Ctrl-C to exit): "
echo ""

# ── Detect existing setup ────────────────────────────────────────────────────
INSTALL_MODE="fresh"          # fresh | migrate | clean
DETECTED_PREFIX=""
DETECTED_VAULT=""
DETECTED_NAME=""
CUSTOM_SKILLS=()
BACKUP_DIR=""

_count_files() { ls "$1"/*.md 2>/dev/null | wc -l | tr -d ' '; }

if [ -d "$CLAUDE_DIR" ] && [ "$(ls -A "$CLAUDE_DIR" 2>/dev/null)" ]; then
  EXISTING_COMMANDS=0
  EXISTING_MEMORIES=0

  [ -d "$CLAUDE_DIR/commands" ] && EXISTING_COMMANDS=$(_count_files "$CLAUDE_DIR/commands")
  EXISTING_MEMORIES=$(find "$CLAUDE_DIR/projects" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

  # Detect prefix from *-ticket.md filename
  TICKET_FILE=$(ls "$CLAUDE_DIR/commands/"*-ticket.md 2>/dev/null | head -1 || echo "")
  [ -n "$TICKET_FILE" ] && DETECTED_PREFIX=$(basename "$TICKET_FILE" | sed 's/-ticket\.md//')

  # Detect existing vault path from any known env var patterns
  for _v in QH_KNOWLEDGE DT_KNOWLEDGE DP_KNOWLEDGE SF_KNOWLEDGE; do
    if [ -n "${!_v:-}" ]; then
      DETECTED_VAULT="${!_v}"
      break
    fi
  done

  # Try to read name from existing CLAUDE.md
  if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    DETECTED_NAME=$(grep -m1 "^\*\*Name:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Name:\*\* //' | tr -d '\r' || echo "")
  fi

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  Existing Claude Code setup found"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""
  printf "  %-22s %s\n" "Commands found:"    "$EXISTING_COMMANDS files"
  printf "  %-22s %s\n" "Memory files:"      "$EXISTING_MEMORIES files"
  [ -n "$DETECTED_PREFIX" ] && printf "  %-22s %s\n" "Detected prefix:"  "$DETECTED_PREFIX"
  [ -n "$DETECTED_NAME" ]   && printf "  %-22s %s\n" "Detected name:"    "$DETECTED_NAME"
  [ -n "$DETECTED_VAULT" ]  && printf "  %-22s %s\n" "Existing vault:"   "$DETECTED_VAULT"
  echo ""
  echo "  What would you like to do?"
  echo ""
  echo "    m) Migrate   Keep your memory and vault, bring custom skills into the"
  echo "                 new dotfiles structure, install new skills alongside them"
  echo "    c) Clean     Wipe ~/.claude/ and start completely fresh"
  echo ""
  echo "  Either way, your existing ~/.claude/ is backed up first."
  echo ""

  while true; do
    read -rp "  Choice [m/c]: " _choice
    _choice=$(echo "$_choice" | tr '[:upper:]' '[:lower:]')
    case "$_choice" in
      m) INSTALL_MODE="migrate"; break;;
      c) INSTALL_MODE="clean";   break;;
      *) echo "  Enter m or c.";;
    esac
  done

  echo ""

  # Backup always — before any changes
  BACKUP_DIR="$HOME/.claude.backup.$(date +%Y%m%d%H%M%S)"
  cp -r "$CLAUDE_DIR" "$BACKUP_DIR"
  ok "Backed up existing setup to: $BACKUP_DIR"
  echo ""

  if [ "$INSTALL_MODE" = "clean" ]; then
    rm -rf "$CLAUDE_DIR"
    mkdir -p "$CLAUDE_DIR"
    ok "Cleaned ~/.claude/ — starting fresh"
    echo ""
  fi

  if [ "$INSTALL_MODE" = "migrate" ]; then
    # ── Migration analysis ───────────────────────────────────────────────────
    echo ""
    echo "  ── Migration Analysis ──"
    echo ""

    STANDARD_SKILLS="ticket support spec arch dev qa start close draft weekly status learn sync save whiteboard setup-client pull-notes explore lens"

    # Compare each standard skill: existing vs repo template
    echo "  Skill files:"
    SKILLS_USE_NEW=()
    SKILLS_MODIFIED=()

    if [ -d "$CLAUDE_DIR/commands" ] && [ -n "$DETECTED_PREFIX" ]; then
      for _skill in $STANDARD_SKILLS; do
        # Existing installed file (prefixed)
        case "$_skill" in
          ticket|support|spec|arch|dev|qa)
            _existing_path="$CLAUDE_DIR/commands/${DETECTED_PREFIX}-${_skill}.md"
            _repo_path="$REPO_DIR/commands/${_skill}.md"
            ;;
          *)
            _existing_path="$CLAUDE_DIR/commands/${_skill}.md"
            _repo_path="$REPO_DIR/commands/${_skill}.md"
            ;;
        esac

        [ ! -f "$_existing_path" ] && continue
        [ ! -f "$_repo_path" ]    && continue

        _lines_existing=$(wc -l < "$_existing_path" | tr -d ' ')
        _lines_new=$(wc -l < "$_repo_path" | tr -d ' ')
        _diff=$(( _lines_new - _lines_existing ))

        if [ "$_diff" -gt 20 ]; then
          printf "    %-28s existing %s lines / new %s lines  → new has additions, use new\n" \
            "/$_skill" "$_lines_existing" "$_lines_new"
          SKILLS_USE_NEW+=("$_skill")
        elif [ "$_diff" -lt -20 ]; then
          printf "    %-28s existing %s lines / new %s lines  → existing was modified, review\n" \
            "/$_skill" "$_lines_existing" "$_lines_new"
          SKILLS_MODIFIED+=("$_skill")
        else
          printf "    %-28s existing %s lines / new %s lines  → comparable, use new\n" \
            "/$_skill" "$_lines_existing" "$_lines_new"
          SKILLS_USE_NEW+=("$_skill")
        fi
      done
    fi

    echo ""

    # Find custom skills (not in standard list)
    if [ -d "$CLAUDE_DIR/commands" ]; then
      for _f in "$CLAUDE_DIR/commands/"*.md; do
        [ ! -f "$_f" ] && continue
        _base=$(basename "$_f" .md)
        _stripped=$(echo "$_base" | sed "s/^${DETECTED_PREFIX}-//")
        _is_standard=false
        for _s in $STANDARD_SKILLS; do
          [ "$_stripped" = "$_s" ] && _is_standard=true && break
        done
        [ "$_is_standard" = false ] && CUSTOM_SKILLS+=("$_f")
      done
    fi

    if [ "${#CUSTOM_SKILLS[@]}" -gt 0 ]; then
      echo "  Custom skills (not in standard set — always kept):"
      for _f in "${CUSTOM_SKILLS[@]}"; do
        printf "    %s\n" "$(basename "$_f")"
      done
      echo ""
    fi

    # Check CLAUDE.md for custom content beyond the template
    echo "  CLAUDE.md:"
    if [ -f "$BACKUP_DIR/CLAUDE.md" ]; then
      _existing_lines=$(wc -l < "$BACKUP_DIR/CLAUDE.md" | tr -d ' ')
      _template_lines=$(wc -l < "$REPO_DIR/CLAUDE.md" | tr -d ' ')
      if [ "$_existing_lines" -gt $(( _template_lines + 10 )) ]; then
        printf "    Existing has %s lines vs template %s lines.\n" "$_existing_lines" "$_template_lines"
        echo "    Likely has custom rules. New CLAUDE.md will be used (identity pre-filled)."
        echo "    Review $BACKUP_DIR/CLAUDE.md after install to recover any custom rules."
      else
        echo "    No significant customization detected. New CLAUDE.md will be used."
      fi
    fi
    echo ""

    # Memory files
    _mem_count=$(find "$BACKUP_DIR/projects" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
    echo "  Memory files:"
    printf "    %s feedback memory files found — all preserved.\n" "$_mem_count"
    echo ""

    # Summary
    echo "  Migration plan:"
    echo "    - All standard skills: install new versions (updated)"
    [ "${#SKILLS_MODIFIED[@]}" -gt 0 ] && \
      echo "    - Modified skills: new installed, old saved to $BACKUP_DIR for manual review"
    [ "${#CUSTOM_SKILLS[@]}" -gt 0 ] && \
      echo "    - Custom skills: copied into new dotfiles/commands/custom/"
    echo "    - Memory files: copied to new memory location"
    echo "    - Knowledge vault: detected path used as default (not recreated)"
    echo ""

    read -rp "  Proceed with this migration plan? [Y/n]: " _confirm
    echo ""
    if [[ "$_confirm" =~ ^[Nn]$ ]]; then
      echo "  Migration cancelled. Your backup is at: $BACKUP_DIR"
      echo "  Re-run install.sh to start over."
      exit 0
    fi
  fi
fi

# ── Step 1: Identity ─────────────────────────────────────────────────────────
header "Step 1: Your Identity"
echo ""
dim "Written into CLAUDE.md so Claude knows your role and context."
echo ""

GIT_NAME=$(git config user.name 2>/dev/null || echo "")
GIT_EMAIL=$(git config user.email 2>/dev/null || echo "")

# Use detected values as defaults when migrating
_default_name="${DETECTED_NAME:-$GIT_NAME}"
_default_prefix="${DETECTED_PREFIX:-dt}"

USER_NAME=$(ask    "Full name"                         "$_default_name")
USER_TITLE=$(ask   "Job title"                         "Data Integration Manager")
USER_COMPANY=$(ask "Company"                           "")
USER_DOMAIN=$(ask  "Domain (e.g. Health AI, FinTech)"  "Health AI")
SKILL_PREFIX=$(ask "Skill prefix (e.g. 'ah' gives /ah-ticket, 'dt' gives /dt-ticket)" "$_default_prefix")
PREFIX_UPPER=$(echo "$SKILL_PREFIX" | tr '[:lower:]' '[:upper:]')

# ── Step 2: Base folder setup ────────────────────────────────────────────────
header "Step 2: Folder Setup"
echo ""
dim "Everything lives under one base folder, named by prefix."
dim "Example: base 'dipen' + prefix 'dp' creates ~/Developer/dipen/dp-dotfiles, dp-knowledge, dp-scripts"
echo ""

NAME_SLUG=$(echo "$USER_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
DEFAULT_BASE="$HOME/Developer/${NAME_SLUG}"

BASE_DIR=$(ask "Base folder path (e.g. ~/Developer/dipen)" "$DEFAULT_BASE")
# Expand ~ manually in case the user typed it literally
BASE_DIR="${BASE_DIR/#\~/$HOME}"

# All paths derive from base + prefix
DOTFILES_DIR="${BASE_DIR}/${SKILL_PREFIX}-dotfiles"
# When migrating, default vault to the detected existing path so we don't recreate it
VAULT_DIR="${DETECTED_VAULT:-${BASE_DIR}/${SKILL_PREFIX}-knowledge}"
SCRIPTS_DIR="${BASE_DIR}/${SKILL_PREFIX}-scripts"
MEETINGS_DIR="${VAULT_DIR}/06-meetings-summaries"
CODE_DIR="${BASE_DIR}/${SKILL_PREFIX}-code"
DEV_DIR="${BASE_DIR}/${SKILL_PREFIX}-dev"

echo ""
ok "Base:      $BASE_DIR"
ok "Dotfiles:  $DOTFILES_DIR"
ok "Knowledge: $VAULT_DIR"
ok "Scripts:   $SCRIPTS_DIR"
ok "Meetings:  $MEETINGS_DIR (inside knowledge)"
ok "Code:      $CODE_DIR  (read-only source)"
ok "Dev:       $DEV_DIR   (active checkouts)"
echo ""

# Warn if the repo is not already in the expected dotfiles location
if [ "$REPO_DIR" != "$DOTFILES_DIR" ]; then
  note "This repo is at: $REPO_DIR"
  note "Expected at:     $DOTFILES_DIR"
  note "Consider moving it: mv \"$REPO_DIR\" \"$DOTFILES_DIR\""
  echo ""
fi

mkdir -p "$BASE_DIR"
mkdir -p "$SCRIPTS_DIR"

# ── Step 3: Create folder structure ──────────────────────────────────────────
header "Step 3: Creating Folders"
echo ""

# Vault — not git tracked, local only
echo "  ${SKILL_PREFIX}-knowledge/ (Obsidian vault, local only — not git tracked)"
VAULT_DIRS=(
  "00-landing"
  "01-system-map/clients"
  "01-system-map/pipelines"
  "01-system-map/architecture"
  "01-system-map/data-model"
  "01-system-map/platform-learning"
  "02-tickets"
  "03-knowledge-base/decisions"
  "03-knowledge-base/learnings"
  "03-knowledge-base/patterns"
  "04-education"
  "05-claude-conversations"
  "06-meetings-summaries"
  "07-workflows"
  "memory"
  "output"
)

mkdir -p "$VAULT_DIR"
for dir in "${VAULT_DIRS[@]}"; do
  mkdir -p "$VAULT_DIR/$dir"
  ok "$dir"
done

echo ""

# Scripts — ask about git tracking
echo "  ${SKILL_PREFIX}-scripts/ (reusable scripts)"
SCRIPTS_GIT=""
read -rp "  Track scripts with git? [y/N]: " SCRIPTS_GIT
echo ""

if [[ "$SCRIPTS_GIT" =~ ^[Yy]$ ]]; then
  if [ ! -d "$SCRIPTS_DIR/.git" ]; then
    git -C "$SCRIPTS_DIR" init
    ok "Git initialized in ${SKILL_PREFIX}-scripts"
  else
    ok "Git already initialized in ${SKILL_PREFIX}-scripts"
  fi

  cat > "$SCRIPTS_DIR/.gitignore" << 'GITIGNORE'
__pycache__/
*.pyc
*.pyo
.env
*.log
.DS_Store
*.credentials
*.key
GITIGNORE

  ok "Created .gitignore for scripts"

  SCRIPTS_REMOTE=$(ask "  GitHub repo URL for scripts (Enter to skip)" "")
  if [ -n "$SCRIPTS_REMOTE" ]; then
    if git -C "$SCRIPTS_DIR" remote get-url origin &>/dev/null; then
      git -C "$SCRIPTS_DIR" remote set-url origin "$SCRIPTS_REMOTE"
    else
      git -C "$SCRIPTS_DIR" remote add origin "$SCRIPTS_REMOTE"
    fi
    ok "Remote set: $SCRIPTS_REMOTE"
  fi
else
  ok "Scripts folder created (no git tracking)"
fi

# ── Git working directories ──────────────────────────────────────────────────
echo ""
echo "  Developer directories (git workflow)"
echo ""
info "  Two directories keep read-only source truth separate from active work."
info "  ${SKILL_PREFIX}-code/  →  read-only. Claude reads here for design validation. Never written to."
info "  ${SKILL_PREFIX}-dev/   →  active checkouts. Feature branches live here. PRs go back to main."
echo ""

mkdir -p "$CODE_DIR"
mkdir -p "$DEV_DIR"
ok "Created: ${SKILL_PREFIX}-code/  (read-only source)"
ok "Created: ${SKILL_PREFIX}-dev/   (active checkouts)"
echo ""

echo "  Which repos do you want synced into ${SKILL_PREFIX}-code/ (read-only)?"
dim "  Enter full GitHub clone URLs, one per line. Press Enter on a blank line when done."
dim "  These stay at latest main. You never work directly in ${SKILL_PREFIX}-code/."
echo ""

SYNC_REPOS=()
while true; do
  read -rp "  Repo URL (or Enter to finish): " _repo_url
  [ -z "$_repo_url" ] && break
  SYNC_REPOS+=("$_repo_url")
done

if [ "${#SYNC_REPOS[@]}" -gt 0 ]; then
  echo ""
  note "Cloning repos into ${CODE_DIR}..."
  for _url in "${SYNC_REPOS[@]}"; do
    _repo_name=$(basename "$_url" .git)
    if [ -d "${CODE_DIR}/${_repo_name}/.git" ]; then
      git -C "${CODE_DIR}/${_repo_name}" pull --quiet
      ok "Updated: $_repo_name"
    else
      git clone --quiet "$_url" "${CODE_DIR}/${_repo_name}"
      ok "Cloned: $_repo_name"
    fi
  done
else
  note "No repos cloned. Add later: git clone <url> ${CODE_DIR}/<repo-name>"
fi

# ── Step 4: Install Claude Code config ───────────────────────────────────────
header "Step 4: Installing Claude Code Config"
echo ""

SLUG=$(echo "$HOME" | sed 's|/|-|g')
MEMORY_TARGET="$CLAUDE_DIR/projects/$SLUG/memory"

mkdir -p "$CLAUDE_DIR"
mkdir -p "$(dirname "$MEMORY_TARGET")"

backup "$CLAUDE_DIR/settings.json"
sed \
  -e "s|QH_KNOWLEDGE|${PREFIX_UPPER}_KNOWLEDGE|g" \
  -e "s|QH_MEETINGS|${PREFIX_UPPER}_MEETINGS|g" \
  -e "s|QH_SCRIPTS|${PREFIX_UPPER}_SCRIPTS|g" \
  "$REPO_DIR/settings.json" > "$CLAUDE_DIR/settings.json"
ok "Written: settings.json (env vars substituted for prefix: $SKILL_PREFIX)"

symlink "$REPO_DIR/memory"        "$MEMORY_TARGET"

# Commands: copy with prefix + name substitution so slash commands use the chosen prefix
mkdir -p "$CLAUDE_DIR/commands"
for src_file in "$REPO_DIR/commands/"*.md; do
  base=$(basename "$src_file")
  # Prefix the ticket-chain skills with the chosen prefix
  case "$base" in
    ticket.md|support.md|spec.md|arch.md|dev.md|qa.md)
      dest_name="${SKILL_PREFIX}-${base}"
      ;;
    *)
      dest_name="$base"
      ;;
  esac
  backup "$CLAUDE_DIR/commands/$dest_name"
  sed \
    -e "s|/qh-ticket|/${SKILL_PREFIX}-ticket|g" \
    -e "s|/qh-support|/${SKILL_PREFIX}-support|g" \
    -e "s|/qh-spec|/${SKILL_PREFIX}-spec|g" \
    -e "s|/qh-arch|/${SKILL_PREFIX}-arch|g" \
    -e "s|/qh-dev|/${SKILL_PREFIX}-dev|g" \
    -e "s|/qh-qa|/${SKILL_PREFIX}-qa|g" \
    -e "s|~/qh-output/|\$QH_KNOWLEDGE/output/|g" \
    -e "s|QH_KNOWLEDGE|${PREFIX_UPPER}_KNOWLEDGE|g" \
    -e "s|QH_MEETINGS|${PREFIX_UPPER}_MEETINGS|g" \
    -e "s|QH_SCRIPTS|${PREFIX_UPPER}_SCRIPTS|g" \
    -e "s|qh-code-temp|${SKILL_PREFIX}-code-temp|g" \
    -e "s|qh-code/|${SKILL_PREFIX}-code/|g" \
    -e "s|{NAME}|${USER_NAME}|g" \
    "$src_file" > "$CLAUDE_DIR/commands/$dest_name"
  ok "Installed: $dest_name"
done

# Cursor rules: deploy to vault with prefix substitution
if [ -d "$REPO_DIR/cursor-rules" ]; then
  CURSOR_RULES_DEST="$VAULT_DIR/.cursor/rules"
  mkdir -p "$CURSOR_RULES_DEST"
  for src_file in "$REPO_DIR/cursor-rules/"*.mdc; do
    [ -f "$src_file" ] || continue
    base=$(basename "$src_file")
    sed \
      -e "s|/qh-ticket|/${SKILL_PREFIX}-ticket|g" \
      -e "s|/qh-support|/${SKILL_PREFIX}-support|g" \
      -e "s|/qh-spec|/${SKILL_PREFIX}-spec|g" \
      -e "s|/qh-arch|/${SKILL_PREFIX}-arch|g" \
      -e "s|/qh-dev|/${SKILL_PREFIX}-dev|g" \
      -e "s|/qh-qa|/${SKILL_PREFIX}-qa|g" \
      -e "s|~/qh-output/|\$QH_KNOWLEDGE/output/|g" \
      -e "s|QH_KNOWLEDGE|${PREFIX_UPPER}_KNOWLEDGE|g" \
      -e "s|QH_MEETINGS|${PREFIX_UPPER}_MEETINGS|g" \
      -e "s|QH_SCRIPTS|${PREFIX_UPPER}_SCRIPTS|g" \
      -e "s|qh-code-temp|${SKILL_PREFIX}-code-temp|g" \
      -e "s|qh-code/|${SKILL_PREFIX}-code/|g" \
      -e "s|\[YOUR NAME\]|${USER_NAME}|g" \
      -e "s|\[YOUR TITLE\]|${USER_TITLE}|g" \
      -e "s|\[YOUR COMPANY\]|${USER_COMPANY}|g" \
      "$src_file" > "$CURSOR_RULES_DEST/$base"
    ok "Cursor rule: $base"
  done
fi

# Copy custom skills from migration into dotfiles/commands/custom/
if [ "$INSTALL_MODE" = "migrate" ] && [ "${#CUSTOM_SKILLS[@]}" -gt 0 ]; then
  CUSTOM_DEST="$REPO_DIR/commands/custom"
  mkdir -p "$CUSTOM_DEST"
  mkdir -p "$CLAUDE_DIR/commands"
  for _cf in "${CUSTOM_SKILLS[@]}"; do
    _cfname=$(basename "$_cf")
    cp "$_cf" "$CUSTOM_DEST/$_cfname"
    cp "$_cf" "$CLAUDE_DIR/commands/$_cfname"
    ok "Preserved custom skill: $_cfname"
  done
fi

# Copy memory files from migration backup to new memory location
if [ "$INSTALL_MODE" = "migrate" ] && [ -n "$BACKUP_DIR" ]; then
  _mem_src=$(find "$BACKUP_DIR/projects" -name "*.md" 2>/dev/null | head -1)
  if [ -n "$_mem_src" ]; then
    _mem_src_dir=$(dirname "$_mem_src")
    mkdir -p "$REPO_DIR/memory"
    cp "$_mem_src_dir"/*.md "$REPO_DIR/memory/" 2>/dev/null || true
    ok "Memory files copied to new location"
  fi
fi

# ── Step 5: Write CLAUDE.md with identity ────────────────────────────────────
header "Step 5: Writing CLAUDE.md"
echo ""

CLAUDE_DEST="$CLAUDE_DIR/CLAUDE.md"
backup "$CLAUDE_DEST"

sed \
  -e "s|\[YOUR NAME\]|${USER_NAME}|g" \
  -e "s|\[YOUR TITLE\]|${USER_TITLE}|g" \
  -e "s|\[YOUR COMPANY\]|${USER_COMPANY}|g" \
  -e "s|Health AI\. PHI/PII rules apply at all times, no exceptions\.|${USER_DOMAIN}. PHI/PII rules apply at all times, no exceptions.|g" \
  -e "s|QH_KNOWLEDGE|${PREFIX_UPPER}_KNOWLEDGE|g" \
  -e "s|QH_MEETINGS|${PREFIX_UPPER}_MEETINGS|g" \
  -e "s|QH_SCRIPTS|${PREFIX_UPPER}_SCRIPTS|g" \
  -e "s|/{prefix}-ticket|/${SKILL_PREFIX}-ticket|g" \
  -e "s|/{prefix}-support|/${SKILL_PREFIX}-support|g" \
  -e "s|/{prefix}-spec|/${SKILL_PREFIX}-spec|g" \
  -e "s|/{prefix}-arch|/${SKILL_PREFIX}-arch|g" \
  -e "s|/{prefix}-dev|/${SKILL_PREFIX}-dev|g" \
  -e "s|/{prefix}-qa|/${SKILL_PREFIX}-qa|g" \
  "$REPO_DIR/CLAUDE.md" > "$CLAUDE_DEST"

ok "Written: $CLAUDE_DEST"

# ── Step 6: Service connections ───────────────────────────────────────────────
header "Step 6: Service Connections"
echo ""
dim "For each service, choose MCP (browser OAuth) or API token or skip."
dim "MCP is easier if you do not have admin access to create tokens."
dim "API token is faster if you already have a token ready."

# Track choices for settings.local.json generation
ATLASSIAN_METHOD="skip"
SLACK_METHOD="skip"
NOTION_METHOD="skip"

# API token values (only used when method = api)
ATLASSIAN_URL=""
ATLASSIAN_USERNAME=""
ATLASSIAN_API_TOKEN=""
SLACK_BOT_TOKEN=""
SLACK_TEAM_ID=""
NOTION_TOKEN=""

# ── Atlassian ────────────────────────────────────────────────────────────────
echo ""
echo "  ── Atlassian (Jira + Confluence) ──"
dim "  MCP: browser OAuth on first use, no token needed."
dim "  API: requires an Atlassian API token from id.atlassian.com."

choose_connection "Atlassian" "yes"
ATLASSIAN_METHOD="$CONNECTION_CHOICE"

if [ "$ATLASSIAN_METHOD" = "api" ]; then
  echo ""
  ATLASSIAN_URL=$(ask "  Atlassian base URL (e.g. https://your-org.atlassian.net)" "")
  ATLASSIAN_USERNAME=$(ask "  Atlassian email" "$GIT_EMAIL")
  ATLASSIAN_API_TOKEN=$(ask_secret "  API token" "atlassian-api-token")
  echo ""
  cred_store "atlassian-url"       "$ATLASSIAN_URL"
  cred_store "atlassian-username"  "$ATLASSIAN_USERNAME"
  cred_store "atlassian-api-token" "$ATLASSIAN_API_TOKEN"
elif [ "$ATLASSIAN_METHOD" = "mcp" ]; then
  ok "Atlassian: MCP / OAuth. Browser will open on first Claude Code use."
else
  note "Atlassian: skipped. Re-run install.sh to add later."
fi

# ── Slack ────────────────────────────────────────────────────────────────────
echo ""
echo "  ── Slack ──"
dim "  Requires a Slack Bot token. Creating one needs workspace admin access."
dim "  If your company restricts this, choose s to skip."

choose_connection "Slack" "no"
SLACK_METHOD="$CONNECTION_CHOICE"

if [ "$SLACK_METHOD" = "api" ]; then
  echo ""
  SLACK_BOT_TOKEN=$(ask_secret "  Slack Bot Token (xoxb-...)" "slack-bot-token")
  SLACK_TEAM_ID=$(ask          "  Slack Team ID (T...)"       "")
  echo ""
  cred_store "slack-bot-token" "$SLACK_BOT_TOKEN"
  cred_store "slack-team-id"   "$SLACK_TEAM_ID"
else
  note "Slack: skipped. Re-run install.sh to add later."
fi

# ── Notion ───────────────────────────────────────────────────────────────────
echo ""
echo "  ── Notion (optional) ──"
dim "  Requires a Notion integration token from notion.so/my-integrations."

choose_connection "Notion" "no"
NOTION_METHOD="$CONNECTION_CHOICE"

if [ "$NOTION_METHOD" = "api" ]; then
  echo ""
  NOTION_TOKEN=$(ask_secret "  Notion token (secret_...)" "notion-token")
  echo ""
  cred_store "notion-token" "$NOTION_TOKEN"
else
  note "Notion: skipped. Re-run install.sh to add later."
fi

# ── Step 7: Generate credentials.sh ─────────────────────────────────────────
header "Step 7: Credentials Loader"
echo ""

cat > "$CREDS_SCRIPT" << 'CREDS'
#!/usr/bin/env bash
# credentials.sh — Cross-platform credential loader.
# Reads tokens from the OS credential store and exports as env vars.
# Sourced by the shell profile and by MCP server launch commands.
# Never edit manually. Re-run install.sh to add or rotate tokens.

_OS="$(uname -s)"
_KC="claude-dotfiles"

_kv() {
  local key="${_KC}-$1"
  case "$_OS" in
    Darwin)
      security find-generic-password -a "$USER" -s "$key" -w 2>/dev/null || true
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        secret-tool lookup service "$key" account "$USER" 2>/dev/null || true
      else
        local sf="$HOME/.claude/.secrets"
        [ -f "$sf" ] && grep "^${key}=" "$sf" 2>/dev/null | cut -d= -f2- || true
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      powershell -Command \
        "(Get-StoredCredential -Target '${key}').GetNetworkCredential().Password" \
        2>/dev/null || true
      ;;
  esac
}

_ATL_URL="$(_kv atlassian-url)"
_ATL_USER="$(_kv atlassian-username)"
_ATL_TOKEN="$(_kv atlassian-api-token)"
_SLACK_BOT="$(_kv slack-bot-token)"
_SLACK_TEAM="$(_kv slack-team-id)"
_NOTION="$(_kv notion-token)"

[ -n "$_ATL_URL" ]    && export JIRA_URL="$_ATL_URL" CONFLUENCE_URL="${_ATL_URL}/wiki"
[ -n "$_ATL_USER" ]   && export JIRA_USERNAME="$_ATL_USER" CONFLUENCE_USERNAME="$_ATL_USER" ATLASSIAN_USERNAME="$_ATL_USER"
[ -n "$_ATL_TOKEN" ]  && export JIRA_API_TOKEN="$_ATL_TOKEN" CONFLUENCE_API_TOKEN="$_ATL_TOKEN" ATLASSIAN_API_TOKEN="$_ATL_TOKEN"
[ -n "$_SLACK_BOT" ]  && export SLACK_BOT_TOKEN="$_SLACK_BOT"
[ -n "$_SLACK_TEAM" ] && export SLACK_TEAM_ID="$_SLACK_TEAM"
[ -n "$_NOTION" ]     && export NOTION_API_KEY="$_NOTION" NOTION_API_TOKEN="$_NOTION"

unset _ATL_URL _ATL_USER _ATL_TOKEN _SLACK_BOT _SLACK_TEAM _NOTION _OS _KC
CREDS

chmod +x "$CREDS_SCRIPT"
ok "Written: $CREDS_SCRIPT"
dim "Reads from OS credential store at runtime. No tokens stored in the file."

# ── Step 8: Write settings.local.json ────────────────────────────────────────
header "Step 8: MCP Server Config"
echo ""

# Build MCP server JSON blocks based on chosen methods
MCP_SERVERS=""

# Atlassian block
if [ "$ATLASSIAN_METHOD" = "mcp" ]; then
  MCP_SERVERS="${MCP_SERVERS}
    \"atlassian\": {
      \"command\": \"/bin/bash\",
      \"args\": [\"-c\", \"exec npx -y mcp-remote https://mcp.atlassian.com/v1/sse\"]
    },"
elif [ "$ATLASSIAN_METHOD" = "api" ]; then
  MCP_SERVERS="${MCP_SERVERS}
    \"atlassian\": {
      \"command\": \"/bin/bash\",
      \"args\": [\"-c\", \"source \\\"\\$HOME/.claude/credentials.sh\\\" 2>/dev/null; exec npx -y mcp-remote https://mcp.atlassian.com/v1/sse\"]
    },"
fi

# Slack block (API only)
if [ "$SLACK_METHOD" = "api" ]; then
  MCP_SERVERS="${MCP_SERVERS}
    \"slack\": {
      \"command\": \"/bin/bash\",
      \"args\": [\"-c\", \"source \\\"\\$HOME/.claude/credentials.sh\\\" 2>/dev/null; exec npx -y @modelcontextprotocol/server-slack\"]
    },"
fi

# Notion block (API only)
if [ "$NOTION_METHOD" = "api" ]; then
  MCP_SERVERS="${MCP_SERVERS}
    \"notion\": {
      \"command\": \"/bin/bash\",
      \"args\": [\"-c\", \"source \\\"\\$HOME/.claude/credentials.sh\\\" 2>/dev/null; exec npx -y @notionhq/notion-mcp-server\"]
    },"
fi

# Strip trailing comma from last server entry
MCP_SERVERS="${MCP_SERVERS%,}"

if [ -n "$MCP_SERVERS" ]; then
  cat > "$REPO_DIR/settings.local.json" << MCPJSON
{
  "mcpServers": {${MCP_SERVERS}
  }
}
MCPJSON
  ok "Written: settings.local.json"
  dim "MCP servers configured based on your connection choices."
else
  cat > "$REPO_DIR/settings.local.json" << 'MCPJSON'
{
  "mcpServers": {}
}
MCPJSON
  ok "Written: settings.local.json (no services configured — add via re-run)"
fi

# ── Step 9: Shell profile ─────────────────────────────────────────────────────
header "Step 9: Shell Profile"
echo ""

if [ -f "$HOME/.zshrc" ]; then
  SHELL_PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
  SHELL_PROFILE="$HOME/.bashrc"
else
  SHELL_PROFILE="$HOME/.profile"
fi

note "Profile: $SHELL_PROFILE"
echo ""

ENV_BLOCK="
# Arbiter (prefix: ${SKILL_PREFIX})
export ${PREFIX_UPPER}_KNOWLEDGE=\"${VAULT_DIR}\"
export ${PREFIX_UPPER}_MEETINGS=\"${MEETINGS_DIR}\"
export ${PREFIX_UPPER}_SCRIPTS=\"${SCRIPTS_DIR}\"
export ARBITER_KNOWLEDGE=\"${VAULT_DIR}\"
export CLAUDE_DOTFILES=\"${REPO_DIR}\"
[ -f \"\$HOME/.claude/credentials.sh\" ] && source \"\$HOME/.claude/credentials.sh\"
"

if grep -q "CLAUDE_DOTFILES" "$SHELL_PROFILE" 2>/dev/null; then
  ok "Env block already present in $SHELL_PROFILE — skipped"
  note "To update paths, edit $SHELL_PROFILE and run: source $SHELL_PROFILE"
else
  printf '%s\n' "$ENV_BLOCK" >> "$SHELL_PROFILE"
  ok "Added env vars and credentials loader"
fi

# ── Step 10: RAG Index Setup ─────────────────────────────────────────────────
header "Step 10: RAG Index Setup"
echo ""
dim "Installs Python dependencies for vault search (chromadb, sentence-transformers)"
dim "and builds the initial index. Re-running is safe: only changed files are re-indexed."
echo ""

RAG_SKIP=false

if ! command -v python3 &>/dev/null; then
  note "python3 not found — skipping RAG setup. Install Python 3.9+ and re-run install.sh."
  RAG_SKIP=true
fi

if [ "$RAG_SKIP" = false ]; then
  note "Installing Python dependencies (this may take a minute)..."
  python3 -m pip install --quiet chromadb sentence-transformers 2>&1 | tail -2
  ok "Dependencies installed: chromadb, sentence-transformers"

  echo ""
  note "Building initial vault index..."
  dim "  Model: all-MiniLM-L6-v2 (downloaded on first run, ~90 MB)"
  dim "  Index: ${VAULT_DIR}/.rag_index"
  echo ""

  python3 "$REPO_DIR/rag/build_index.py" \
    --dir "$VAULT_DIR" \
    --index "$VAULT_DIR/.rag_index" \
    --full

  ok "Index built: ${VAULT_DIR}/.rag_index"
  dim "vault_search_hook.sh will use this index on every prompt."
  dim "Re-index after adding docs: python3 $REPO_DIR/rag/build_index.py --dir $VAULT_DIR --index $VAULT_DIR/.rag_index"
fi

echo ""
note "Installing git pre-commit hook (blocks accidental token commits)..."
note "Run this in each repo you want protected:"
dim "  cp \"$REPO_DIR/hooks/pre-commit-secrets\" <repo>/.git/hooks/pre-commit && chmod +x <repo>/.git/hooks/pre-commit"
echo ""

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Done."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "  %-14s %s\n" "Name:"      "$USER_NAME"
printf "  %-14s %s\n" "Title:"     "$USER_TITLE"
printf "  %-14s %s\n" "Company:"   "$USER_COMPANY"
printf "  %-14s %s\n" "Prefix:"    "$SKILL_PREFIX"
echo ""
echo "  Folder layout:"
printf "  %-14s %s\n" "Base:"      "$BASE_DIR"
printf "  %-14s %s\n" "Dotfiles:"  "${BASE_DIR}/${SKILL_PREFIX}-dotfiles  (this repo)"
printf "  %-14s %s\n" "Knowledge:" "$VAULT_DIR  (local only)"
printf "  %-14s %s\n" "Scripts:"   "$SCRIPTS_DIR"
printf "  %-14s %s\n" "Code:"      "$CODE_DIR  (read-only source, latest main)"
printf "  %-14s %s\n" "Dev:"       "$DEV_DIR  (active checkouts, feature branches)"
echo ""
printf "  %-14s %s\n" "Config:"    "$CLAUDE_DEST"
printf "  %-14s %s\n" "Profile:"   "$SHELL_PROFILE"
printf "  %-14s %s\n" "Atlassian:" "$ATLASSIAN_METHOD"
printf "  %-14s %s\n" "Slack:"     "$SLACK_METHOD"
printf "  %-14s %s\n" "Notion:"    "$NOTION_METHOD"
echo ""

if [ "$ATLASSIAN_METHOD" = "mcp" ]; then
  note "Atlassian: a browser will open to authorize on first Claude Code use."
fi

echo ""
echo "  Next:"
echo "    1.  Reload shell:         source $SHELL_PROFILE"
echo "    2.  Open VSCode and run:  /start"
echo "    3.  Vault search is live — every prompt auto-queries your index"
echo ""
echo "  To re-index after adding docs:"
echo "    python3 $REPO_DIR/rag/build_index.py --dir $VAULT_DIR --index $VAULT_DIR/.rag_index"
echo ""
echo "  To add or rotate tokens at any time:  ./install.sh"
echo "  Worked example:  docs/walkthrough.md"
echo ""
