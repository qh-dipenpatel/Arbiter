#!/usr/bin/env bash
# install.sh — One-button setup for Arbiter
# Run once after cloning. Safe to re-run: backs up files, skips already-done steps.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
CREDS_SCRIPT="$CLAUDE_DIR/credentials.sh"
KC_PREFIX="claude-dotfiles"
OS="$(uname -s)"   # Darwin | Linux | MINGW* | CYGWIN*

# Standard skills list (used in migration analysis and custom-skill detection)
STANDARD_SKILLS="ticket support spec arch dev qa start close draft weekly status learn sync save whiteboard setup-client pull-notes explore lens"

# ── Formatting ────────────────────────────────────────────────────────────────
BOLD='\033[1m'; RESET='\033[0m'; GREEN='\033[0;32m'
YELLOW='\033[0;33m'; DIM='\033[2m'; CYAN='\033[0;36m'

header() { echo -e "\n${BOLD}── $1 ──${RESET}"; }
ok()     { echo -e "  ${GREEN}✓${RESET}  $1"; }
note()   { echo -e "  ${YELLOW}→${RESET}  $1"; }
dim()    { echo -e "  ${DIM}$1${RESET}"; }
info()   { echo -e "  ${CYAN}$1${RESET}"; }

# ── Plain-text prompt ─────────────────────────────────────────────────────────
ask() {
  local prompt="$1" default="${2:-}" result
  if [ -n "$default" ]; then
    read -rp "  $prompt [$default]: " result
    echo "${result:-$default}"
  else
    read -rp "  $prompt: " result
    echo "$result"
  fi
}

# ── Cross-platform credential read ────────────────────────────────────────────
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
        local sf="$CLAUDE_DIR/.secrets"
        [ -f "$sf" ] && grep "^${service}=" "$sf" 2>/dev/null | cut -d= -f2- || echo ""
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      cmdkey /list | grep -q "claude-dotfiles-$1" \
        && powershell -Command "(Get-StoredCredential -Target '${service}').GetNetworkCredential().Password" 2>/dev/null \
        || echo ""
      ;;
    *) echo "";;
  esac
}

# ── Cross-platform credential write ──────────────────────────────────────────
cred_store() {
  local service="$1" value="$2"
  if [ -z "$value" ]; then
    note "Skipped (empty): ${service}"
    return
  fi
  local key="${KC_PREFIX}-${service}"
  case "$OS" in
    Darwin)
      security add-generic-password -a "$USER" -s "$key" -w "$value" -U 2>/dev/null
      ok "Saved to Keychain: ${service}"
      ;;
    Linux)
      if command -v secret-tool &>/dev/null; then
        printf '%s' "$value" | secret-tool store --label="$key" service "$key" account "$USER" 2>/dev/null
        ok "Saved to Secret Service: ${service}"
      else
        local sf="$CLAUDE_DIR/.secrets"
        # umask 077 scopes both tmp and final file to 0600 from creation;
        # avoids the window where touch+chmod leaves the file world-readable
        # and avoids mv replacing a 0600 file with a 0644 tmp.
        ( umask 077
          grep -v "^${key}=" "$sf" 2>/dev/null > "${sf}.tmp" || true
          echo "${key}=${value}" >> "${sf}.tmp"
          mv "${sf}.tmp" "$sf"
        )
        ok "Saved to secrets file: ${service}"
        note "Install secret-tool for better security: sudo apt install libsecret-tools"
      fi
      ;;
    MINGW*|CYGWIN*|MSYS*)
      cmdkey /generic:"$key" /user:"$USER" /pass:"$value" &>/dev/null
      ok "Saved to Credential Manager: ${service}"
      ;;
    *)
      note "Unknown OS — could not save ${service}. You may need to re-enter it next time."
      ;;
  esac
}

# ── Hidden token prompt (credential-store-aware) ──────────────────────────────
ask_secret() {
  local prompt="$1" service="$2" result existing masked
  existing=$(cred_read "$service")
  if [ -n "$existing" ]; then
    masked="****${existing: -4}"
    read -rsp "  $prompt [saved: ${masked} — press Enter to keep]: " result
    echo "" >&2
    if [ -z "$result" ]; then echo "$existing"; else echo "$result"; fi
  else
    read -rsp "  $prompt [press Enter to skip]: " result
    echo "" >&2
    echo "$result"
  fi
}

# ── Connection chooser ────────────────────────────────────────────────────────
# Sets global CONNECTION_CHOICE to "mcp", "api", or "skip"
CONNECTION_CHOICE=""
choose_connection() {
  local service="$1" has_mcp="$2" result
  echo ""
  if [ "$has_mcp" = "yes" ]; then
    echo "    b) Sign in with your browser   Easiest — a login page opens automatically, no key needed."
    echo "    k) Paste an API key            If you already have one ready."
  else
    echo "    k) Paste an API key            Required for this service."
  fi
  echo "    s) Skip for now                Add this later by re-running install.sh."
  echo ""
  while true; do
    if [ "$has_mcp" = "yes" ]; then
      read -rp "  Choice [b/k/s]: " result
      result=$(echo "$result" | tr '[:upper:]' '[:lower:]')
      case "$result" in
        b) CONNECTION_CHOICE="mcp";  return;;
        k) CONNECTION_CHOICE="api";  return;;
        s) CONNECTION_CHOICE="skip"; return;;
        *) echo "  Please type b, k, or s.";;
      esac
    else
      read -rp "  Choice [k/s]: " result
      result=$(echo "$result" | tr '[:upper:]' '[:lower:]')
      case "$result" in
        k) CONNECTION_CHOICE="api";  return;;
        s) CONNECTION_CHOICE="skip"; return;;
        *) echo "  Please type k or s.";;
      esac
    fi
  done
}

# ── Escape user input for sed replacement strings ────────────────────────────
# Escapes \, &, and the | delimiter so user-supplied strings (names, company)
# cannot corrupt sed expressions or produce garbled output files.
_sed_escape() {
  printf '%s' "$1" | sed 's/\\/\\\\/g; s/&/\\&/g; s/|/\\|/g'
}

# ── Auto-generate prefix from name initials ───────────────────────────────────
make_prefix() {
  echo "$1" | tr '[:upper:]' '[:lower:]' \
    | awk '{r=""; for(i=1;i<=NF&&i<=3;i++) r=r substr($i,1,1); print r}'
}

# ── Backup + symlink ──────────────────────────────────────────────────────────
backup() {
  local path="$1"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    mv "$path" "$path.bak.$(date +%Y%m%d%H%M%S)"
    note "Backed up: $(basename "$path")"
  fi
}

symlink() {
  local src="$1" dest="$2"
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
echo "  Arbiter  —  AI assistant setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Sets up Claude Code to work the way your team works."
echo "  Takes about 5 minutes."
echo ""
echo "  What it does:"
echo "    • Creates a personal notes folder for your work"
echo "    • Connects Claude to Jira, Notion, and Slack"
echo "    • Saves your details so Claude knows who you are"
echo ""
echo "  Press Enter at any prompt to use the suggested answer."
echo "  Built by Dipen Patel — questions? Ask Dipen on Slack."
echo ""
read -rp "  Ready? Press Enter to start (or Ctrl-C to exit): "
echo ""

echo "  Setup mode:"
echo "    Simple   — auto-configures folders and paths (recommended for most teams)"
echo "    Advanced — manually set folder paths, code reference dir, and repo cloning"
echo ""
_mode_input=""
read -rp "  Advanced setup? [y/N]: " _mode_input
if [[ "$_mode_input" == [yY] || "$_mode_input" == [yY][eE][sS] ]]; then
  SIMPLE_MODE=false
else
  SIMPLE_MODE=true
fi
echo ""

# ── Detect existing setup ─────────────────────────────────────────────────────
INSTALL_MODE="fresh"
DETECTED_PREFIX=""
DETECTED_VAULT=""
DETECTED_NAME=""
DETECTED_TITLE=""
DETECTED_COMPANY=""
DETECTED_DOMAIN=""
DETECTED_BASE=""
CUSTOM_SKILLS=()
BACKUP_DIR=""
ARBITER_CONFIG="$HOME/.claude/arbiter-config"

# Load saved config from a previous run so users don't re-enter everything
if [ -f "$ARBITER_CONFIG" ]; then
  # shellcheck source=/dev/null
  source "$ARBITER_CONFIG"
fi

_count_files() { { ls "$1"/*.md 2>/dev/null || true; } | wc -l | tr -d ' '; }

if [ -d "$CLAUDE_DIR" ] && [ "$(ls -A "$CLAUDE_DIR" 2>/dev/null)" ]; then
  EXISTING_COMMANDS=0
  EXISTING_MEMORIES=0

  [ -d "$CLAUDE_DIR/commands" ] && EXISTING_COMMANDS=$(_count_files "$CLAUDE_DIR/commands")
  EXISTING_MEMORIES=$(find "$CLAUDE_DIR/projects" -name "*.md" 2>/dev/null | wc -l | tr -d ' ' || echo "0")

  TICKET_FILE=$(ls "$CLAUDE_DIR/commands/"*-ticket.md 2>/dev/null | head -1 || echo "")
  [ -n "$TICKET_FILE" ] && DETECTED_PREFIX=$(basename "$TICKET_FILE" | sed 's/-ticket\.md//')

  for _v in QH_KNOWLEDGE DT_KNOWLEDGE DP_KNOWLEDGE SF_KNOWLEDGE ARBITER_KNOWLEDGE; do
    if [ -n "${!_v:-}" ]; then
      DETECTED_VAULT="${!_v}"
      break
    fi
  done

  if [ -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    DETECTED_NAME=$(grep -m1 "^\*\*Name:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Name:\*\* //' | tr -d '\r' || echo "")
    DETECTED_TITLE=$(grep -m1 "^\*\*Title:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Title:\*\* //' | tr -d '\r' || echo "")
    DETECTED_COMPANY=$(grep -m1 "^\*\*Company:\*\*" "$CLAUDE_DIR/CLAUDE.md" 2>/dev/null \
      | sed 's/\*\*Company:\*\* //' | tr -d '\r' || echo "")
  fi

  if [ "$SIMPLE_MODE" = true ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Existing setup found"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    [ -n "$DETECTED_NAME" ] && echo "  Name on file: $DETECTED_NAME"
    echo ""
    echo "  What would you like to do?"
    echo ""
    echo "    k) Keep and update   Upgrade to the latest version, keep your notes."
    echo "    f) Start fresh       Wipe everything and start over."
    echo ""
    while true; do
      read -rp "  Choice [k/f, default k]: " _m_choice
      _m_choice="${_m_choice:-k}"
      _m_choice=$(echo "$_m_choice" | tr '[:upper:]' '[:lower:]')
      case "$_m_choice" in
        k) INSTALL_MODE="migrate"; break;;
        f) INSTALL_MODE="clean";   break;;
        *) echo "  Please type k or f.";;
      esac
    done
  else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "  Existing Claude Code setup found"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    printf "  %-22s %s\n" "Commands found:"   "$EXISTING_COMMANDS files"
    printf "  %-22s %s\n" "Memory files:"     "$EXISTING_MEMORIES files"
    [ -n "$DETECTED_PREFIX" ] && printf "  %-22s %s\n" "Detected prefix:"  "$DETECTED_PREFIX"
    [ -n "$DETECTED_NAME" ]   && printf "  %-22s %s\n" "Detected name:"    "$DETECTED_NAME"
    [ -n "$DETECTED_VAULT" ]  && printf "  %-22s %s\n" "Existing vault:"   "$DETECTED_VAULT"
    echo ""
    echo "  What would you like to do?"
    echo ""
    echo "    m) Migrate   Keep your memory and vault, install new skills alongside them."
    echo "    c) Clean     Wipe ~/.claude/ and start completely fresh."
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
  fi

  echo ""

  # Backup always, before any changes
  BACKUP_DIR="$HOME/.claude.backup.$(date +%Y%m%d%H%M%S)"
  cp -rL "$CLAUDE_DIR" "$BACKUP_DIR" 2>/dev/null \
    || cp -r "$CLAUDE_DIR" "$BACKUP_DIR" 2>/dev/null \
    || { note "Could not fully back up $CLAUDE_DIR — continuing anyway (original untouched)."; BACKUP_DIR=""; }
  [ -n "$BACKUP_DIR" ] && ok "Backed up existing setup to: $BACKUP_DIR"
  echo ""

  if [ "$INSTALL_MODE" = "clean" ]; then
    rm -rf "$CLAUDE_DIR"
    mkdir -p "$CLAUDE_DIR"
    ok "Cleared existing setup — starting fresh"
    echo ""
  fi

  # Advanced mode only: detailed migration analysis
  if [ "$INSTALL_MODE" = "migrate" ] && [ "$SIMPLE_MODE" = false ]; then
    echo ""
    echo "  ── Migration Analysis ──"
    echo ""
    echo "  Skill files:"
    SKILLS_USE_NEW=()
    SKILLS_MODIFIED=()

    if [ -d "$CLAUDE_DIR/commands" ] && [ -n "$DETECTED_PREFIX" ]; then
      for _skill in $STANDARD_SKILLS; do
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
    _mem_count=$([ -n "$BACKUP_DIR" ] && find "$BACKUP_DIR/projects" -name "*.md" 2>/dev/null | wc -l | tr -d ' ' || echo "0")
    echo "  Memory files:"
    printf "    %s feedback memory files found — all preserved.\n" "$_mem_count"
    echo ""
    echo "  Migration plan:"
    echo "    - All standard skills: install new versions"
    [ "${#SKILLS_MODIFIED[@]}" -gt 0 ] && \
      echo "    - Modified skills: new installed, old saved to $BACKUP_DIR for manual review"
    [ "${#CUSTOM_SKILLS[@]}" -gt 0 ] && \
      echo "    - Custom skills: copied into new dotfiles/commands/custom/"
    echo "    - Memory files: copied to new memory location"
    echo ""
    read -rp "  Proceed with this migration plan? [Y/n]: " _confirm
    echo ""
    if [[ "$_confirm" =~ ^[Nn]$ ]]; then
      echo "  Migration cancelled. Your backup is at: $BACKUP_DIR"
      echo "  Re-run install.sh to start over."
      exit 0
    fi
  fi

  # Custom skill detection (both modes)
  if [ "$INSTALL_MODE" = "migrate" ] && [ -d "$CLAUDE_DIR/commands" ]; then
    for _f in "$CLAUDE_DIR/commands/"*.md; do
      [ ! -f "$_f" ] && continue
      _base=$(basename "$_f" .md)
      _stripped=$(echo "$_base" | sed "s/^${DETECTED_PREFIX:-dt}-//")
      _is_standard=false
      for _s in $STANDARD_SKILLS; do
        [ "$_stripped" = "$_s" ] && _is_standard=true && break
      done
      [ "$_is_standard" = false ] && CUSTOM_SKILLS+=("$_f")
    done

    if [ "${#CUSTOM_SKILLS[@]}" -gt 0 ] && [ "$SIMPLE_MODE" = false ]; then
      echo "  Custom skills (always kept):"
      for _f in "${CUSTOM_SKILLS[@]}"; do
        printf "    %s\n" "$(basename "$_f")"
      done
      echo ""
    fi
  fi
fi  # end existing-setup detection

# ── Step 1: Your Details ──────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = true ]; then
  header "Your Details"
else
  header "Step 1: Your Identity"
  dim "Written into CLAUDE.md so Claude knows your role and context."
fi
echo ""

GIT_NAME=$(git config user.name 2>/dev/null || echo "")
GIT_EMAIL=$(git config user.email 2>/dev/null || echo "")
_default_name="${SAVED_NAME:-${DETECTED_NAME:-$GIT_NAME}}"
_default_title="${SAVED_TITLE:-${DETECTED_TITLE:-Data Integration Manager}}"
_default_company="${SAVED_COMPANY:-${DETECTED_COMPANY:-}}"
_default_domain="${SAVED_DOMAIN:-Health AI}"

USER_NAME=$(ask  "Your full name"    "$_default_name")
while [ -z "$USER_NAME" ]; do
  echo "  Name is required."
  USER_NAME=$(ask "Your full name" "")
done
USER_TITLE=$(ask "Your job title"    "$_default_title")
USER_COMPANY=$(ask "Your company"   "$_default_company")
USER_DOMAIN=$(ask  "Your industry (e.g. Health AI, FinTech, Insurance)" "$_default_domain")

if [ "$SIMPLE_MODE" = true ]; then
  # Auto-generate prefix from name initials; don't expose the concept to the user
  _auto_prefix=$(make_prefix "$USER_NAME")
  [ -z "$_auto_prefix" ] && _auto_prefix="dt"
  SKILL_PREFIX="${SAVED_PREFIX:-${DETECTED_PREFIX:-$_auto_prefix}}"
else
  _default_prefix="${SAVED_PREFIX:-${DETECTED_PREFIX:-dt}}"
  SKILL_PREFIX=$(ask "Skill prefix (e.g. 'ah' gives /ah-ticket, 'dt' gives /dt-ticket)" "$_default_prefix")
fi

PREFIX_UPPER=$(echo "$SKILL_PREFIX" | tr '[:lower:]' '[:upper:]')

# Save answers so re-runs don't require re-entry
mkdir -p "$CLAUDE_DIR"
cat > "$ARBITER_CONFIG" << SAVEDCONFIG
SAVED_NAME="$USER_NAME"
SAVED_TITLE="$USER_TITLE"
SAVED_COMPANY="$USER_COMPANY"
SAVED_DOMAIN="$USER_DOMAIN"
SAVED_PREFIX="$SKILL_PREFIX"
SAVEDCONFIG

# ── Step 2: Folder Setup ──────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 2: Folder Setup"
  dim "Everything lives under one base folder."
fi
echo ""

NAME_SLUG=$(echo "$USER_NAME" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
DEFAULT_BASE="$HOME/Developer/${NAME_SLUG}"

if [ "$SIMPLE_MODE" = true ]; then
  _default_vault="${DETECTED_VAULT:-${DEFAULT_BASE}/${SKILL_PREFIX}-knowledge}"
  echo "  Your notes will be saved to:"
  echo "    $_default_vault"
  echo ""
  read -rp "  Press Enter to use this, or type a different path: " _vault_input
  if [ -n "$_vault_input" ]; then
    _vault_input="${_vault_input/#\~/$HOME}"
    VAULT_DIR="$_vault_input"
  else
    VAULT_DIR="$_default_vault"
  fi
  # All other dirs derive from DEFAULT_BASE so they stay consistent
  BASE_DIR="$DEFAULT_BASE"
  DOTFILES_DIR="${BASE_DIR}/${SKILL_PREFIX}-dotfiles"
  SCRIPTS_DIR="${BASE_DIR}/${SKILL_PREFIX}-scripts"
  MEETINGS_DIR="${VAULT_DIR}/06-meetings-summaries"
  CODE_DIR="${BASE_DIR}/${SKILL_PREFIX}-code"
  DEV_DIR="${BASE_DIR}/${SKILL_PREFIX}-dev"
else
  BASE_DIR=$(ask "Base folder path (press Enter for default)" "${SAVED_BASE:-$DEFAULT_BASE}")
  BASE_DIR="${BASE_DIR/#\~/$HOME}"
  DOTFILES_DIR="${BASE_DIR}/${SKILL_PREFIX}-dotfiles"
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
  if [ "$REPO_DIR" != "$DOTFILES_DIR" ]; then
    note "This repo is at: $REPO_DIR"
    note "Expected at:     $DOTFILES_DIR"
    note "Consider moving: mv \"$REPO_DIR\" \"$DOTFILES_DIR\""
    echo ""
  fi
fi

mkdir -p "$BASE_DIR" "$SCRIPTS_DIR"

# Persist the resolved base path for future re-runs
echo "SAVED_BASE=\"$BASE_DIR\"" >> "$ARBITER_CONFIG"

# ── Step 3: Create Folder Structure ──────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 3: Creating Folders"
  echo ""
fi

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
  [ "$SIMPLE_MODE" = false ] && ok "$dir"
done
[ "$SIMPLE_MODE" = true ] && ok "Notes folder ready: $VAULT_DIR"

mkdir -p "$CODE_DIR" "$DEV_DIR"

# Advanced only: optional scripts git tracking and read-only repo sync
if [ "$SIMPLE_MODE" = false ]; then
  echo ""
  echo "  ${SKILL_PREFIX}-scripts/ — your personal reusable scripts folder"
  dim "  Optional: back this up with git so your scripts are version controlled and recoverable."
  SCRIPTS_GIT=""
  read -rp "  Track scripts with git? [y/N]: " SCRIPTS_GIT
  echo ""
  if [[ "$SCRIPTS_GIT" =~ ^[Yy]$ ]]; then
    if ! command -v git &>/dev/null; then
      note "git not found — skipping scripts git tracking. Install git and re-run install.sh."
    elif [ ! -d "$SCRIPTS_DIR/.git" ]; then
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
    dim "  Paste the GitHub repo URL where your scripts should be pushed (e.g. https://github.com/you/my-scripts)."
    dim "  This is for YOUR scripts repo — not a company repo you read from."
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

  echo ""
  echo "  Code repo directories (read-only source + active dev)"
  echo ""
  info "  ${SKILL_PREFIX}-code/  →  read-only mirror. Claude reads your company repos here"
  info "                            for design validation. You never edit files here."
  info "  ${SKILL_PREFIX}-dev/   →  your active working checkouts. All feature branch"
  info "                            work happens here."
  echo ""
  echo "  Which company repos do you want mirrored into ${SKILL_PREFIX}-code/ (read-only)?"
  dim "  These are repos you need Claude to read for context — e.g. your data platform repo."
  dim "  Enter full GitHub clone URLs, one per line. Press Enter on a blank line when done."
  echo ""
  SYNC_REPOS=()
  while true; do
    read -rp "  Repo URL (or Enter to finish): " _repo_url
    [ -z "$_repo_url" ] && break
    SYNC_REPOS+=("$_repo_url")
  done
  if [ "${#SYNC_REPOS[@]}" -gt 0 ]; then
    if ! command -v git &>/dev/null; then
      note "git not found — skipping repo clone. Install git and re-run install.sh."
    fi
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
fi

# ── Step 4: Install Claude Code Config ───────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 4: Installing Claude Code Config"
  echo ""
fi

SLUG=$(echo "$REPO_DIR" | sed 's|/|-|g')
MEMORY_TARGET="$CLAUDE_DIR/projects/$SLUG/memory"

mkdir -p "$CLAUDE_DIR" "$(dirname "$MEMORY_TARGET")"

# Global settings carry the hooks, so they fire in every workspace, not only
# inside this repo. Paths are baked in as absolute values because Claude Code
# does not expand env vars in permission rules, and a GUI-launched editor may
# start without the shell profile loaded.
backup "$CLAUDE_DIR/settings.json"
sed \
  -e "s|\$CLAUDE_DOTFILES|$(_sed_escape "$REPO_DIR")|g" \
  -e "s|\$ARBITER_KNOWLEDGE|$(_sed_escape "$VAULT_DIR")|g" \
  -e "s|\$QH_SCRIPTS|$(_sed_escape "$SCRIPTS_DIR")|g" \
  "$REPO_DIR/settings.json" > "$CLAUDE_DIR/settings.json"
ok "Settings configured (hooks active globally)"

symlink "$REPO_DIR/memory" "$MEMORY_TARGET"

# Escape user-supplied strings before embedding in sed replacement positions.
# & means "matched text" in sed replacements; | closes our delimiter; \ is the escape char.
USER_NAME_ESC=$(_sed_escape "$USER_NAME")
USER_TITLE_ESC=$(_sed_escape "$USER_TITLE")
USER_COMPANY_ESC=$(_sed_escape "$USER_COMPANY")
USER_DOMAIN_ESC=$(_sed_escape "$USER_DOMAIN")

# Install commands with prefix substitution
mkdir -p "$CLAUDE_DIR/commands"
for src_file in "$REPO_DIR/commands/"*.md; do
  base=$(basename "$src_file")
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
    -e "s|qh-scripts|${SKILL_PREFIX}-scripts|g" \
    -e "s|{NAME}|${USER_NAME_ESC}|g" \
    "$src_file" > "$CLAUDE_DIR/commands/$dest_name"
  [ "$SIMPLE_MODE" = false ] && ok "Installed: $dest_name"
done
[ "$SIMPLE_MODE" = true ] && ok "Commands installed"

# Cursor rules — each rule is independently toggled
# Disabled rules are stored as .mdc.disabled so users can re-enable without re-running install.sh
if [ -d "$REPO_DIR/cursor-rules" ]; then
  CURSOR_RULES_DEST="$VAULT_DIR/.cursor/rules"
  CURSOR_RULES_DISABLED="$VAULT_DIR/.cursor/rules-disabled"
  mkdir -p "$CURSOR_RULES_DEST" "$CURSOR_RULES_DISABLED"

  _apply_cursor_rule() {
    local src_file="$1" dest="$2"
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
      -e "s|qh-scripts|${SKILL_PREFIX}-scripts|g" \
      -e "s|\[YOUR NAME\]|${USER_NAME_ESC}|g" \
      -e "s|\[YOUR TITLE\]|${USER_TITLE_ESC}|g" \
      -e "s|\[YOUR COMPANY\]|${USER_COMPANY_ESC}|g" \
      -e "s|Health AI\. PHI/PII rules apply at all times, no exceptions\.|${USER_DOMAIN_ESC}. PHI/PII rules apply at all times, no exceptions.|g" \
      -e "s|/{prefix}-|/${SKILL_PREFIX}-|g" \
      "$src_file" > "$dest"
  }

  if [ "$SIMPLE_MODE" = true ]; then
    # Quick mode: install all rules enabled
    for src_file in "$REPO_DIR/cursor-rules/"*.mdc; do
      [ -f "$src_file" ] || continue
      base=$(basename "$src_file")
      _apply_cursor_rule "$src_file" "$CURSOR_RULES_DEST/$base"
    done
    ok "Cursor rules installed (all enabled)"
  else
    echo ""
    echo "  Cursor rules — choose which to enable"
    dim "  Rules that are off are saved to rules-disabled/ and can be moved back any time."
    echo ""

    _RULE_CHOICES=()
    for src_file in "$REPO_DIR/cursor-rules/"*.mdc; do
      [ -f "$src_file" ] || continue
      base=$(basename "$src_file" .mdc)
      # Extract description from frontmatter
      _desc=$(grep -m1 "^description:" "$src_file" 2>/dev/null | sed 's/^description: *//' | tr -d '"' || echo "$base")
      printf "  Enable %-22s %s\n" "$base" "$_desc"
      read -rp "  [Y/n]: " _rule_yn
      _rule_yn="${_rule_yn:-y}"
      _RULE_CHOICES+=("$(basename "$src_file"):${_rule_yn}")
    done

    echo ""
    for _entry in "${_RULE_CHOICES[@]}"; do
      _rfile="${_entry%%:*}"
      _yn="${_entry##*:}"
      src_file="$REPO_DIR/cursor-rules/$_rfile"
      if [[ "$_yn" =~ ^[Yy] ]]; then
        _apply_cursor_rule "$src_file" "$CURSOR_RULES_DEST/$_rfile"
        ok "Cursor rule enabled:  $_rfile"
      else
        _apply_cursor_rule "$src_file" "$CURSOR_RULES_DISABLED/$_rfile"
        note "Cursor rule disabled: $_rfile  (saved to rules-disabled/)"
      fi
    done
    dim "  To toggle later: move .mdc files between .cursor/rules/ and .cursor/rules-disabled/"
  fi
fi

# Preserve custom skills from migration
if [ "$INSTALL_MODE" = "migrate" ] && [ "${#CUSTOM_SKILLS[@]}" -gt 0 ]; then
  CUSTOM_DEST="$REPO_DIR/commands/custom"
  mkdir -p "$CUSTOM_DEST" "$CLAUDE_DIR/commands"
  for _cf in "${CUSTOM_SKILLS[@]}"; do
    _cfname=$(basename "$_cf")
    cp "$_cf" "$CUSTOM_DEST/$_cfname"
    cp "$_cf" "$CLAUDE_DIR/commands/$_cfname"
    ok "Preserved custom skill: $_cfname"
  done
fi

# Carry over memory files from migration
if [ "$INSTALL_MODE" = "migrate" ] && [ -n "$BACKUP_DIR" ]; then
  _mem_src=$(find "$BACKUP_DIR/projects" -name "*.md" 2>/dev/null | head -1 || echo "")
  if [ -n "$_mem_src" ]; then
    _mem_src_dir=$(dirname "$_mem_src")
    mkdir -p "$REPO_DIR/memory"
    cp "$_mem_src_dir"/*.md "$REPO_DIR/memory/" 2>/dev/null || true
    ok "Notes and memory preserved"
  fi
fi

WORKSPACE_FILE="$BASE_DIR/${SKILL_PREFIX}.code-workspace"

# ── Step 5: Write CLAUDE.md ───────────────────────────────────────────────────

CLAUDE_DEST="$CLAUDE_DIR/CLAUDE.md"
backup "$CLAUDE_DEST"

CODE_DIR_ESC=$(_sed_escape "$CODE_DIR")
DEV_DIR_ESC=$(_sed_escape "$DEV_DIR")
VAULT_DIR_ESC=$(_sed_escape "$VAULT_DIR")
SCRIPTS_DIR_ESC=$(_sed_escape "$SCRIPTS_DIR")
MEETINGS_DIR_ESC=$(_sed_escape "$MEETINGS_DIR")
DOTFILES_DIR_ESC=$(_sed_escape "$DOTFILES_DIR")
sed \
  -e "s|\[YOUR NAME\]|${USER_NAME_ESC}|g" \
  -e "s|\[YOUR TITLE\]|${USER_TITLE_ESC}|g" \
  -e "s|\[YOUR COMPANY\]|${USER_COMPANY_ESC}|g" \
  -e "s|Health AI\. PHI/PII rules apply at all times, no exceptions\.|${USER_DOMAIN_ESC}. PHI/PII rules apply at all times, no exceptions.|g" \
  -e "s|QH_KNOWLEDGE|${PREFIX_UPPER}_KNOWLEDGE|g" \
  -e "s|QH_MEETINGS|${PREFIX_UPPER}_MEETINGS|g" \
  -e "s|QH_SCRIPTS|${PREFIX_UPPER}_SCRIPTS|g" \
  -e "s|/{prefix}-ticket|/${SKILL_PREFIX}-ticket|g" \
  -e "s|/{prefix}-support|/${SKILL_PREFIX}-support|g" \
  -e "s|/{prefix}-spec|/${SKILL_PREFIX}-spec|g" \
  -e "s|/{prefix}-arch|/${SKILL_PREFIX}-arch|g" \
  -e "s|/{prefix}-dev|/${SKILL_PREFIX}-dev|g" \
  -e "s|/{prefix}-qa|/${SKILL_PREFIX}-qa|g" \
  -e "s|{CODE_DIR}|${CODE_DIR_ESC}|g" \
  -e "s|{DEV_DIR}|${DEV_DIR_ESC}|g" \
  -e "s|{VAULT_DIR}|${VAULT_DIR_ESC}|g" \
  -e "s|{SCRIPTS_DIR}|${SCRIPTS_DIR_ESC}|g" \
  -e "s|{MEETINGS_DIR}|${MEETINGS_DIR_ESC}|g" \
  -e "s|{DOTFILES_DIR}|${DOTFILES_DIR_ESC}|g" \
  -e "s|{PREFIX_UPPER}|${PREFIX_UPPER}|g" \
  -e "s|{SKILL_PREFIX}|${SKILL_PREFIX}|g" \
  -e "s|{WORKSPACE_FILE}|${WORKSPACE_FILE}|g" \
  "$REPO_DIR/CLAUDE.md" > "$CLAUDE_DEST"

ok "Profile written for $USER_NAME"

# Optional: read-only code reference directory for path guard hook
# In simple mode, CODE_DIR is already set to the auto-derived path from Step 2.
# In advanced mode, the user can override with any path.
if [ "$SIMPLE_MODE" = false ]; then
  CODE_DIR=""
  echo ""
  note "Code reference directory (optional):"
  dim "  A read-only directory Claude should never write to (e.g. a local mirror of your repos at latest main)."
  dim "  The path guard hook blocks any write to this path. Leave blank to skip."
  read -rp "  Code reference directory [blank to skip]: " _code_dir_input
  CODE_DIR="${_code_dir_input:-}"
  if [ -n "$CODE_DIR" ] && [ ! -d "$CODE_DIR" ]; then
    note "Directory not found — skipping code reference guard."
    CODE_DIR=""
  fi
fi
echo "CODE_DIR=\"${CODE_DIR:-}\"" >> "$ARBITER_CONFIG"

# ── Step 6: Service Connections ───────────────────────────────────────────────
if [ "$SIMPLE_MODE" = true ]; then
  header "Connect Your Services"
  echo ""
  echo "  Connect the tools you use every day."
  echo "  Browser sign-in is easiest — just click through the login page that opens."
  echo "  You can skip any service and add it later by re-running install.sh."
else
  header "Step 6: Service Connections"
  echo ""
  dim "For each service, choose browser sign-in, paste an API key, or skip."
fi

ATLASSIAN_METHOD="skip"
SLACK_METHOD="skip"
NOTION_METHOD="skip"

ATLASSIAN_URL=""
ATLASSIAN_USERNAME=""
ATLASSIAN_API_TOKEN=""
SLACK_BOT_TOKEN=""
SLACK_TEAM_ID=""
NOTION_TOKEN=""

# ── Jira + Confluence ─────────────────────────────────────────────────────────
echo ""
echo "  ── Jira and Confluence ──"
if [ "$SIMPLE_MODE" = true ]; then
  echo "  Sign in to read your tickets and look up company docs from inside Claude."
else
  dim "  Browser sign-in: no key needed."
  dim "  API key: create one at id.atlassian.com/manage-profile/security/api-tokens"
fi

choose_connection "Jira and Confluence" "yes"
ATLASSIAN_METHOD="$CONNECTION_CHOICE"

if [ "$ATLASSIAN_METHOD" = "api" ]; then
  echo ""
  ATLASSIAN_URL=$(ask "  Your Atlassian URL (e.g. https://yourcompany.atlassian.net)" "")
  ATLASSIAN_USERNAME=$(ask "  Your Atlassian login email" "$GIT_EMAIL")
  ATLASSIAN_API_TOKEN=$(ask_secret "  API key (from id.atlassian.com/manage-profile/security/api-tokens)" "atlassian-api-token")
  echo ""
  cred_store "atlassian-url"       "$ATLASSIAN_URL"
  cred_store "atlassian-username"  "$ATLASSIAN_USERNAME"
  cred_store "atlassian-api-token" "$ATLASSIAN_API_TOKEN"
elif [ "$ATLASSIAN_METHOD" = "mcp" ]; then
  ok "Jira and Confluence: a login page will open the first time Claude needs them."
else
  note "Jira and Confluence: skipped. Re-run install.sh to add later."
fi

# ── Notion ────────────────────────────────────────────────────────────────────
echo ""
echo "  ── Notion ──"
if [ "$SIMPLE_MODE" = true ]; then
  echo "  Sign in to let Claude read and reference your Notion pages."
else
  dim "  Browser sign-in: no key needed."
  dim "  API key: create one at notion.so/my-integrations"
fi

choose_connection "Notion" "yes"
NOTION_METHOD="$CONNECTION_CHOICE"

if [ "$NOTION_METHOD" = "api" ]; then
  echo ""
  NOTION_TOKEN=$(ask_secret "  Notion integration key (from notion.so/my-integrations, starts with secret_)" "notion-token")
  echo ""
  cred_store "notion-token" "$NOTION_TOKEN"
elif [ "$NOTION_METHOD" = "mcp" ]; then
  ok "Notion: a login page will open the first time Claude needs it."
else
  note "Notion: skipped. Re-run install.sh to add later."
fi

# ── Slack ─────────────────────────────────────────────────────────────────────
echo ""
echo "  ── Slack ──"
if [ "$SIMPLE_MODE" = true ]; then
  echo "  Lets Claude search your Slack messages for context."
  echo "  Requires a bot key from your Slack admin. No browser sign-in option."
  echo "  Skip this if you don't have one — ask your Slack admin for help."
else
  dim "  Requires a bot token (xoxb-...) from your Slack workspace admin."
  dim "  No browser sign-in option: Slack does not provide one."
  dim "  Admin guide: api.slack.com/apps"
fi

choose_connection "Slack" "no"
SLACK_METHOD="$CONNECTION_CHOICE"

if [ "$SLACK_METHOD" = "api" ]; then
  echo ""
  SLACK_BOT_TOKEN=$(ask_secret "  Slack Bot Token (starts with xoxb-)" "slack-bot-token")
  SLACK_TEAM_ID=$(ask          "  Slack Team ID (the T... code from your Slack URL)" "")
  echo ""
  cred_store "slack-bot-token" "$SLACK_BOT_TOKEN"
  cred_store "slack-team-id"   "$SLACK_TEAM_ID"
else
  note "Slack: skipped. Re-run install.sh to add later."
fi

# ── Credentials loader ────────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 7: Credentials Loader"
  echo ""
fi

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
ok "Credentials configured (tokens stored in your system keychain, not in files)"

# ── MCP Server Config ─────────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 8: MCP Server Config"
  echo ""
fi

# Register servers with the Claude Code CLI at user scope so they apply in
# every workspace. Browser sign-in uses Claude Code's native HTTP transport
# (OAuth on first use, no Node needed). API-key servers run through npx.
ATLASSIAN_MCP_URL="https://mcp.atlassian.com/v1/mcp"
NOTION_MCP_URL="https://mcp.notion.com/mcp"
CREDS_SOURCE="source \"\$HOME/.claude/credentials.sh\" 2>/dev/null"

_mcp_register() {
  local name="$1"; shift
  claude mcp remove --scope user "$name" >/dev/null 2>&1 || true
  if claude mcp add --scope user "$name" "$@" >/dev/null 2>&1; then
    ok "Connected $name (all workspaces)"
  else
    note "Could not register $name. Run later: claude mcp add --scope user $name $*"
  fi
}

_mcp_register_npx() {
  local name="$1" package="$2"
  if ! command -v npx >/dev/null 2>&1; then
    note "$name needs Node.js (npx not found). Install Node, then re-run install.sh."
    return
  fi
  _mcp_register "$name" -- /bin/bash -c "${CREDS_SOURCE}; exec npx -y ${package}"
}

if ! command -v claude >/dev/null 2>&1; then
  note "Claude Code CLI not found, so services were not connected."
  note "Install Claude Code, then re-run install.sh to connect Jira, Notion, and Slack."
else
  case "$ATLASSIAN_METHOD" in
    mcp) _mcp_register atlassian --transport http "$ATLASSIAN_MCP_URL" ;;
    api) _mcp_register_npx atlassian "mcp-remote ${ATLASSIAN_MCP_URL}" ;;
  esac
  case "$NOTION_METHOD" in
    mcp) _mcp_register notion --transport http "$NOTION_MCP_URL" ;;
    api) _mcp_register_npx notion "@notionhq/notion-mcp-server" ;;
  esac
  [ "$SLACK_METHOD" = "api" ] && _mcp_register_npx slack "@modelcontextprotocol/server-slack"
  ok "Service connections saved"
fi

# ── Shell Profile ─────────────────────────────────────────────────────────────
if [ "$SIMPLE_MODE" = false ]; then
  header "Step 9: Shell Profile"
  echo ""
fi

if [ -f "$HOME/.zshrc" ]; then
  SHELL_PROFILE="$HOME/.zshrc"
elif [ -f "$HOME/.bashrc" ]; then
  SHELL_PROFILE="$HOME/.bashrc"
else
  SHELL_PROFILE="$HOME/.profile"
fi

ENV_BLOCK="
# Arbiter (prefix: ${SKILL_PREFIX})
export ${PREFIX_UPPER}_KNOWLEDGE=\"${VAULT_DIR}\"
export ${PREFIX_UPPER}_MEETINGS=\"${MEETINGS_DIR}\"
export ${PREFIX_UPPER}_SCRIPTS=\"${SCRIPTS_DIR}\"
export ARBITER_KNOWLEDGE=\"${VAULT_DIR}\"
export CLAUDE_DOTFILES=\"${REPO_DIR}\"
export ARBITER_CODE_DIR=\"${CODE_DIR:-}\"
[ -f \"\$HOME/.claude/credentials.sh\" ] && source \"\$HOME/.claude/credentials.sh\"
"

if grep -q "CLAUDE_DOTFILES" "$SHELL_PROFILE" 2>/dev/null; then
  ok "Shell profile already configured"
  if [ "$SIMPLE_MODE" = true ]; then
    note "If you changed your notes folder, update the path in $SHELL_PROFILE and reload your terminal."
  else
    note "To update paths, edit $SHELL_PROFILE and run: source $SHELL_PROFILE"
  fi
else
  printf '%s\n' "$ENV_BLOCK" >> "$SHELL_PROFILE"
  ok "Shell profile updated: $SHELL_PROFILE"
fi

# ── Vault Search Index ────────────────────────────────────────────────────────
DO_RAG=false

if [ "$SIMPLE_MODE" = true ]; then
  echo ""
  echo "  ── Vault Search (optional) ──"
  echo "  Lets Claude automatically search your notes when you ask questions."
  echo "  Downloads a small AI model (~90 MB) on first run."
  echo ""
  read -rp "  Set this up now? [y/N]: " _rag_input
  [[ "${_rag_input:-n}" =~ ^[Yy]$ ]] && DO_RAG=true
else
  header "Step 10: Vault Search Index"
  echo ""
  dim "Installs Python deps (chromadb, sentence-transformers) and builds the initial index."
  dim "Re-running is safe: only changed files are re-indexed."
  echo ""
  DO_RAG=true
fi

if [ "$DO_RAG" = true ]; then
  if ! command -v python3 &>/dev/null; then
    note "Python 3 not found — skipping vault search setup. Install Python 3.9+ and re-run install.sh."
  else
    note "Installing search dependencies (this may take a minute)..."
    # Wrap in if so set -e / pipefail don't kill the install on pip failure
    if python3 -m pip install --quiet chromadb sentence-transformers 2>&1 | tail -2; then
      ok "Search dependencies installed"
      echo ""
      note "Building search index..."
      dim "  Model: all-MiniLM-L6-v2 (~90 MB, downloaded once)"
      dim "  Index: ${VAULT_DIR}/.rag_index"
      echo ""
      python3 "$REPO_DIR/rag/build_index.py" \
        --dir "$VAULT_DIR" \
        --index "$VAULT_DIR/.rag_index" \
        --full \
        && ok "Search index built — Claude will search your notes automatically" \
        || note "Index build failed — re-run install.sh after fixing Python to retry."
    else
      note "Could not install search dependencies — skipping vault search."
      note "Fix Python / pip and re-run install.sh to add it later."
    fi
  fi
fi

echo ""
if [ "$SIMPLE_MODE" = false ]; then
  note "Pre-commit secret protection hook:"
  dim "  Run in each repo: cp \"$REPO_DIR/hooks/pre-commit-secrets\" <repo>/.git/hooks/pre-commit && chmod +x <repo>/.git/hooks/pre-commit"
  echo ""
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  You're all set."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "  %-20s %s\n" "Name:"    "$USER_NAME"
printf "  %-20s %s\n" "Company:" "$USER_COMPANY"
printf "  %-20s %s\n" "Notes:"   "$VAULT_DIR"
echo ""
_conn_label() {
  case "$1" in
    mcp)  echo "Connected (browser sign-in)";;
    api)  echo "Connected (API key)";;
    skip) echo "Not connected — re-run install.sh to add";;
    *)    echo "$1";;
  esac
}
printf "  %-20s %s\n" "Jira / Confluence:" "$(_conn_label "$ATLASSIAN_METHOD")"
printf "  %-20s %s\n" "Notion:"            "$(_conn_label "$NOTION_METHOD")"
printf "  %-20s %s\n" "Slack:"             "$(_conn_label "$SLACK_METHOD")"
echo ""

[ "$ATLASSIAN_METHOD" = "mcp" ] && note "Jira: a login page will open the first time Claude accesses Jira."
[ "$NOTION_METHOD"   = "mcp" ] && note "Notion: a login page will open the first time Claude accesses Notion."

# ── VS Code workspace file ────────────────────────────────────────────────────
cat > "$WORKSPACE_FILE" << WORKSPACE
{
  "folders": [
    {
      "name": "${SKILL_PREFIX}-knowledge (notes & vault)",
      "path": "${VAULT_DIR}"
    },
    {
      "name": "${SKILL_PREFIX}-dotfiles (skills & config)",
      "path": "${REPO_DIR}"
    },
    {
      "name": "${SKILL_PREFIX}-scripts (your scripts)",
      "path": "${SCRIPTS_DIR}"
    }
  ],
  "settings": {
    "files.exclude": {
      "**/.rag_index": true,
      "**/__pycache__": true
    }
  }
}
WORKSPACE
ok "VS Code workspace created: $WORKSPACE_FILE"

# ── Verify Claude Code hooks ──────────────────────────────────────────────────
# Hooks are defined in settings.json and installed globally in Step 4. Confirm
# every referenced hook exists and is executable; a missing PHI or secrets hook
# fails silently at runtime, so surface it here instead.
_hook_missing=$(python3 - "$CLAUDE_DIR/settings.json" <<'PYTHON'
import json, os, shlex, sys
settings = json.load(open(sys.argv[1]))
for groups in settings.get('hooks', {}).values():
    for group in groups:
        for hook in group.get('hooks', []):
            path = shlex.split(hook['command'])[0]
            if not os.access(path, os.X_OK):
                print(path)
PYTHON
)
if [ -z "$_hook_missing" ]; then
  ok "Claude Code hooks active in all workspaces"
  dim "  Hook paths point at ${REPO_DIR} — re-run install.sh after moving this directory"
else
  while IFS= read -r _hook; do note "Hook missing or not executable: $_hook"; done <<< "$_hook_missing"
  note "Some hooks will not run. PHI and secrets scanning may be off until fixed."
fi

echo ""
echo "  What to do next:"
echo ""
echo "    1.  Close this terminal and open a new one"
echo "        (or run:  source $SHELL_PROFILE)"
echo ""
echo "    2.  Open VS Code using your workspace file:"
echo "          code \"$WORKSPACE_FILE\""
echo "        Or: File → Open Workspace from File → $(basename "$WORKSPACE_FILE")"
echo ""
echo "    3.  In VS Code, type:  /start"
echo ""
if [ "$SIMPLE_MODE" = true ]; then
  echo "  To connect services you skipped, or to change any setting:"
  echo "    Re-run: ./install.sh"
  echo ""
else
  echo "  To re-index after adding notes:"
  echo "    python3 $REPO_DIR/rag/build_index.py --dir $VAULT_DIR --index $VAULT_DIR/.rag_index"
  echo ""
  echo "  To rotate or add tokens at any time:  ./install.sh"
  echo "  Worked example:  docs/walkthrough.md"
  echo ""
  echo "  If you move the Arbiter directory:"
  echo "    Re-run: ./install.sh  (updates hook paths automatically)"
  echo ""
fi
