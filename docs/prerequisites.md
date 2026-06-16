# Prerequisites

Created by Dipen Patel.

Complete this page before running `install.sh`. Everything here is one-time setup. Once done, the installer takes under 10 minutes.

---

## Platform Support

| Platform | Status | Credential store |
|---|---|---|
| macOS | Full support | macOS Keychain (`security`) |
| Linux (Ubuntu, Fedora, Arch) | Full support | GNOME Secret Service (`secret-tool`), fallback to `~/.claude/.secrets` (mode 600) |
| Windows (WSL) | Full support | Runs as Linux inside WSL |
| Windows (Git Bash) | Supported | Windows Credential Manager (`cmdkey`) |

The installer detects your OS automatically and uses the appropriate credential store. No manual configuration needed.

---

## Apps to Install

### 1. Package manager

**macOS:**
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```
Verify: `brew --version`

**Linux:** Your distro package manager is already available (`apt`, `dnf`, `pacman`). No setup needed.

**Windows (WSL):** Use `apt` inside WSL. No extra setup needed.

### 2. Git

**macOS:** Usually pre-installed. Confirm: `git --version`. If missing: `brew install git`

**Linux:** `sudo apt install git` or `sudo dnf install git`

Configure your identity on all platforms:

```bash
git config --global user.name "Your Full Name"
git config --global user.email "your.email@example.com"
```

### 3. Node.js (minimum version 18)

MCP servers run via `npx`. Node.js provides it.

**macOS:** `brew install node`

**Linux (Ubuntu/Debian):**
```bash
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**Linux (Fedora):** `sudo dnf install nodejs`

**Linux (Arch):** `sudo pacman -S nodejs npm`

Verify: `node --version` and `npx --version`

### 3b. Credential store (Linux only)

On Linux, the installer uses GNOME Secret Service to store tokens securely. Install `secret-tool`:

**Ubuntu/Debian:** `sudo apt install libsecret-tools`

**Fedora:** `sudo dnf install libsecret`

**Arch:** `sudo pacman -S libsecret`

If `secret-tool` is not available, the installer falls back to a mode-600 file at `~/.claude/.secrets`. This works but is less secure than the Secret Service. Install `secret-tool` when possible.

### 4. Claude Code

Claude Code is the CLI this system runs on.

Download: https://claude.ai/download

After installing, authenticate (see **Claude Authentication** below before running this):

```bash
claude
```

Verify: `claude --version`

### 5. VSCode

Primary editor. Claude Code runs as an extension inside it.

Download: https://code.visualstudio.com

Install the Claude Code extension:

1. Open VSCode
2. Press `Cmd+Shift+X`
3. Search "Claude Code"
4. Install the Anthropic extension

### 6. Obsidian

The knowledge vault app. The installer creates your vault folder structure. Point Obsidian at it after setup.

Download: https://obsidian.md

---

## Claude Authentication

Claude Code supports two connection methods. Choose one based on what you have access to.

### Option A: Claude.ai Account (recommended for most users)

Use this if you have a Claude Pro or Claude Team subscription.

1. Run `claude` in your terminal
2. It opens a browser and prompts you to sign in to claude.ai
3. Authorize Claude Code
4. Done. No API key needed.

Best for: individual users and teams on a Claude subscription.

### Option B: Anthropic API Key

Use this if your company has an Anthropic API account or you want usage-based billing.

1. Go to: https://console.anthropic.com
2. Sign in or create an account
3. Go to "API Keys" in the left sidebar
4. Click "Create Key"
5. Copy the key (starts with `sk-ant-`)
6. Run `claude` and choose the API key option when prompted, or set it directly:

```bash
export ANTHROPIC_API_KEY="sk-ant-your-key-here"
claude
```

Add the export to your `~/.zshrc` to persist across sessions.

Best for: enterprise accounts, developer billing, or when your company manages the Anthropic relationship.

---

## Connection Methods

For each service the installer asks how you want to connect. Two options:

**MCP / browser OAuth**: No token needed. The MCP server opens a browser on first use and handles authentication. Best when you do not have admin access to create API tokens. Available for Atlassian only.

**API token**: You enter a token now. It is stored in the OS credential store (macOS Keychain, Linux Secret Service, or Windows Credential Manager), never in any file. Best when you already have a token or want a permanent connection that does not require browser re-auth. Available for all services.

**Skip**: Leave the service unconfigured. Re-run `install.sh` at any time to add it.

Slack requires a bot token regardless of connection method. If your company workspace restricts app creation to workspace admins, skip Slack and ask your IT team or admin to create the app and provide the token.

---

## Tokens to Collect

Only needed if you choose "API token" for a service. The installer prompts you during setup. Input is hidden as you type.

---

### Atlassian API Token (5 minutes)

One token covers both Jira and Confluence.

1. Go to: https://id.atlassian.com/manage-profile/security/api-tokens
2. Click "Create API token"
3. Label it "claude-code"
4. Copy the token. It is shown only once.

You also need:
- Your Atlassian base URL: `https://your-org.atlassian.net`
- Your Atlassian login email

---

### Slack Bot Token (15 to 20 minutes, optional)

Slack requires creating an app in your workspace. If your company Slack workspace restricts app creation to workspace admins, ask IT or your admin to create the app, or skip Slack for now and add it later by re-running the installer.

If you have access to create apps:

**Create the app:**

1. Go to: https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From scratch"
4. Name it (e.g. "Claude Code") and select your workspace
5. Click "Create App"

**Add OAuth scopes:**

1. Left sidebar: "OAuth and Permissions"
2. Scroll to "Bot Token Scopes"
3. Add these scopes:

| Scope | What it allows |
|---|---|
| `channels:history` | Read messages in channels |
| `channels:read` | List channels |
| `search:read` | Search messages |
| `users:read` | Look up users by name |
| `files:read` | Read file metadata |

**Install and copy token:**

1. Click "Install to Workspace"
2. Allow permissions
3. Copy the "Bot User OAuth Token" (starts with `xoxb-`)

**Get your Team ID:**

Open Slack in a browser. The team ID is in the URL: `app.slack.com/client/T01ABCD123/...`

---

### Notion Integration Token (5 minutes, optional)

Only needed if your team uses Notion.

**Admin requirement:** Creating a Notion integration token requires a workspace admin to enable developer connections first. This is a one-time workspace setting, not a per-user setting. Without it, the "New integration" button does not appear.

Admins can enable it at: https://app.notion.com/developers/connections

If your workspace does not have developer connections enabled, skip Notion during install and add it later by re-running the installer once your admin enables it.

**Why a token is worth having:** An API token gives Claude persistent, stable access to Notion pages, databases, and meeting notes through the MCP server. It does not expire and does not require periodic browser re-authorization. Without a token, Claude cannot read or draft Notion content directly, and `/pull-notes` cannot import meeting transcripts from Notion.

**If developer connections are enabled:**

1. Go to: https://www.notion.so/my-integrations
2. Click "New integration"
3. Name it and select your workspace
4. Enable: Read content, Update content, Insert content
5. Copy the "Internal Integration Secret" (starts with `secret_`)

After setup: share specific Notion pages with your integration. Open a page in Notion, click `...`, select "Add connections", and choose your integration. Claude can only read pages you have explicitly shared.

**If you do not have a token yet:** Choose "skip" when the installer asks about Notion. Re-run `./install.sh` to add it later once your admin enables the developer connections setting.

---

## Connecting MCP Servers

MCP servers give Claude Code live access to Jira, Slack, and Notion. After running `install.sh`, connect them in VSCode.

### How to connect in VSCode

1. Open the Claude Code panel in VSCode (left sidebar or `Cmd+Shift+P` → "Claude Code")
2. Click the settings gear icon
3. Go to "MCP Servers"
4. The servers defined in `settings.local.json` appear here (slack, atlassian, notion)
5. Click "Connect" next to each one

### The Atlassian server uses OAuth

The Atlassian MCP server (`mcp-remote`) opens a browser window to authorize access to your Atlassian account on first connect. Complete the OAuth flow and the connection persists.

### Verify a server is working

In Claude Code, type `@jira` or `@slack`. If the server is connected, tool autocomplete appears. If nothing shows, check the troubleshooting steps below.

### Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Server shows error on connect | Token not stored yet | Re-run `install.sh` to add the token |
| `npx not found` error | Node.js not installed | `brew install node` |
| Atlassian OAuth loop | Session expired | Disconnect and reconnect the server |
| Slack server connects but returns no data | Missing OAuth scope | Add the missing scope in api.slack.com/apps and reinstall |

---

## Checklist Before Running install.sh

**Apps:**
- [ ] Homebrew installed
- [ ] Git installed and configured (name and email)
- [ ] Node.js 18 or higher installed
- [ ] Claude Code installed and authenticated (Option A or B above)
- [ ] VSCode installed with the Claude Code extension
- [ ] Obsidian installed

**Tokens:**
- [ ] Atlassian API token copied
- [ ] Atlassian base URL noted (e.g. `https://your-org.atlassian.net`)
- [ ] Atlassian login email ready
- [ ] Slack Bot token copied (optional, starts with `xoxb-`)
- [ ] Slack Team ID copied (optional, starts with `T`)
- [ ] Notion token copied (optional, starts with `secret_`). Requires workspace admin to enable developer connections at https://app.notion.com/developers/connections first.

Once this checklist is complete:

```bash
./install.sh
```

After the installer finishes, connect MCP servers in VSCode and run `/start`.
