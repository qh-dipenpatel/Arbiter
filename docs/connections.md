# Service Connections

Created by Dipen Patel.

Connections fall into three tiers based on what is available for each service. Knowing which tier a service uses before setup saves troubleshooting time.

| Service | Tier | Method | Status |
|---|---|---|---|
| Jira | 1 (MCP) | API token via MCP server | Works |
| Confluence | 1 (MCP) | API token via MCP server | Works |
| Notion | 1 (MCP) | Browser OAuth or integration token via MCP server | Works |
| Slack | 1 (MCP) | Bot token via MCP server | Works; see known issues |
| GitHub | 2 (Direct) | `gh` CLI | Works |
| Databricks | 2 (Direct) | PAT stored in credential store | Works |
| Google Workspace | 3 (Bridge) | Python scripts with local OAuth token | No MCP server exists |

---

## Tier 1: MCP Servers

MCP servers are the standard Claude Code connection pattern. Claude calls them as tools during a session. `install.sh` registers the servers at user scope with `claude mcp add --scope user` and stores tokens in your OS credential store.

Tokens are never written to disk. They live in macOS Keychain, Linux Secret Service, or Windows Credential Manager.

### Atlassian (Jira and Confluence)

One token covers both services.

`install.sh` prompts for:
- Atlassian base URL (`https://your-org.atlassian.net`)
- Your login email
- Your API token

Create a token at: https://id.atlassian.com/manage-profile/security/api-tokens

After install, connect the server in VSCode: Claude Code panel, settings gear, MCP Servers, Connect.

Verify: type `@jira` in Claude Code. Tool autocomplete confirms the server is live.

### Notion

Two options. MCP browser OAuth is easier for most users.

**MCP (browser OAuth):** `install.sh` picks `m`. A browser window opens on first Claude Code use and walks through Notion's OAuth consent screen. No token to create or store.

**API token:** `install.sh` picks `a`. Prompts for your Notion integration token (starts with `secret_`). Admin requirement: your workspace admin must enable developer connections at https://app.notion.com/developers/connections before you can create a token.

With either method, share specific pages with your integration or OAuth app. Open a Notion page, click `...`, select "Add connections". Claude reads only pages you have explicitly shared.

### Slack

Slack requires a bot token created through the Slack API app setup.

`install.sh` prompts for:
- Bot token (starts with `xoxb-`)
- Team ID (from the URL when Slack is open in a browser: `app.slack.com/client/T01ABCD123/...`)

Required OAuth scopes for the bot app:

| Scope | What it allows |
|---|---|
| `channels:history` | Read messages in channels |
| `channels:read` | List channels |
| `search:read` | Search messages |
| `users:read` | Look up users |
| `files:read` | Read file metadata |

Create the app at: https://api.slack.com/apps

If your workspace restricts app creation to admins, skip Slack during install and ask your workspace admin to create the app and share the token.

Arbiter never writes to Slack via MCP. Claude drafts; you send.

### MCP Stability

Recent Claude Code releases have broken MCP connections for some services. If a previously working server fails:

1. Disconnect and reconnect in VSCode MCP settings
2. Re-run `install.sh` to re-register the server and re-store the token
3. Check `node --version`. MCP servers require Node.js 18 or higher.
4. If MCP remains broken for a service, use the bridge pattern documented in Tier 3 as a fallback

---

## Tier 2: Direct API and CLI

These services connect via PAT or CLI auth and work without an MCP server.

### GitHub

`gh` CLI handles GitHub auth. No manual token management needed.

```bash
gh auth login
```

Follow the prompts. After auth, Claude uses `gh` commands directly via Bash.

Verify: `gh auth status`

### Databricks

Databricks requires a Personal Access Token. PHI constraints mean OAuth and subscription auth are not appropriate; a PAT scoped to your workspace with the minimum needed permissions is correct.

**Generate a PAT:**

1. Open your Databricks workspace
2. Top right: your username, Settings, Developer, Access tokens
3. Generate a new token. Set an expiration. Copy the token.

**Store the token in your credential store:**

```bash
# macOS
security add-generic-password -s "databricks-pat" -a "$USER" -w "dapi..."

# Linux
secret-tool store --label="Databricks PAT" service databricks-pat username "$USER"
```

**Expose it to Claude at runtime.** Add to `~/.claude/credentials.sh`:

```bash
export DATABRICKS_TOKEN=$(security find-generic-password -s "databricks-pat" -a "$USER" -w 2>/dev/null)
export DATABRICKS_HOST="https://your-workspace.azuredatabricks.net"
```

No MCP server exists for Databricks. Claude interacts with it through:
- Direct REST API calls via Bash using `$DATABRICKS_TOKEN`
- Python scripts in `$PREFIX_SCRIPTS` using the `databricks-sdk` library
- SQL via the DBSQL API endpoint

Scripts you build for recurring Databricks tasks belong in `$PREFIX_SCRIPTS`. Claude reads from there instead of regenerating code each session.

---

## Tier 3: Bridge Pattern

Some services have no MCP server and no stable direct API path from Claude Code. Google Workspace is the primary example. The bridge pattern covers this gap.

How it works: a Python script calls the service API and writes structured JSON to stdout. Claude calls the script via Bash, reads the output, and works with the result. The script lives in `$PREFIX_SCRIPTS` and is reused across sessions. Claude never has direct authenticated access to the service.

### Google Workspace (Gmail, Calendar, Drive)

No official MCP server exists for Google Workspace. Subscription auth via Claude.ai connectors works in the browser product but not in Claude Code sessions.

**One time setup:**

1. Create a Google Cloud project at https://console.cloud.google.com

2. Enable the APIs you need: Gmail API, Google Calendar API, Google Drive API

3. Go to APIs and Services, Credentials, Create Credentials, OAuth 2.0 Client ID. Choose Desktop application.

4. Download the credentials JSON. Store it at `~/.claude/google-credentials.json`. Set permissions:

```bash
chmod 600 ~/.claude/google-credentials.json
```

5. Install the Google client libraries:

```bash
pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

6. Run the one time auth flow. This opens a browser and saves a local token:

```bash
python3 - <<'EOF'
import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
TOKEN_PATH = os.path.expanduser("~/.claude/google-token.json")
CREDS_PATH = os.path.expanduser("~/.claude/google-credentials.json")

flow = InstalledAppFlow.from_client_secrets_file(CREDS_PATH, SCOPES)
creds = flow.run_local_server(port=0)

with open(TOKEN_PATH, "w") as f:
    f.write(creds.to_json())

os.chmod(TOKEN_PATH, 0o600)
print(f"Token saved to {TOKEN_PATH}")
EOF
```

The token at `~/.claude/google-token.json` refreshes automatically. You do not need to repeat this step unless you revoke access or change scopes.

**Bridge script template.** Save in `$PREFIX_SCRIPTS/gmail_search.py`:

```python
# Author: [your name]
# Date: [date]
# Scope: Gmail read bridge for Claude Code
# Usage: python3 gmail_search.py "query string" [--max 10]

import argparse
import json
import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

TOKEN_PATH = os.path.expanduser("~/.claude/google-token.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_credentials() -> Credentials:
    creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(TOKEN_PATH, "w") as f:
            f.write(creds.to_json())
    return creds


def main() -> None:
    parser = argparse.ArgumentParser(description="Search Gmail and return JSON")
    parser.add_argument("query", type=str, help="Gmail search query")
    parser.add_argument("--max", type=int, default=10, help="Max results")
    args = parser.parse_args()

    service = build("gmail", "v1", credentials=get_credentials())
    results = service.users().messages().list(
        userId="me", q=args.query, maxResults=args.max
    ).execute()

    messages = results.get("messages", [])
    output = []
    for msg in messages:
        detail = service.users().messages().get(
            userId="me",
            id=msg["id"],
            format="metadata",
            metadataHeaders=["Subject", "From", "Date"],
        ).execute()
        headers = {h["name"]: h["value"] for h in detail["payload"]["headers"]}
        output.append(
            {
                "id": msg["id"],
                "subject": headers.get("Subject", ""),
                "from_address": headers.get("From", ""),
                "date": headers.get("Date", ""),
            }
        )

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
```

Claude calls it during a session:

```
Bash(python3 $PREFIX_SCRIPTS/gmail_search.py "from:client@hospital.org after:2026-07-01")
```

Only read scopes are requested. Claude reads and drafts; you send.

---

## PHI and Auth Method

Services that can reach PHI must use API auth, not subscription auth or OAuth flows that route through external providers.

| Service | PHI exposure | Required auth |
|---|---|---|
| Databricks | Yes, contains patient data | PAT only |
| Jira | Possible, ticket descriptions | API token |
| Slack | Possible, channel messages | Bot token, read scopes only |
| Notion | Possible, page content | Integration token, read scope |
| Gmail | Possible, email content | Local OAuth token, read scope, never routed externally |
| GitHub | Possible, commit content | gh CLI, local |

Minimum scope always. If PHI could flow through a service connection, its credentials must live in the OS credential store, never in any file that could be logged, printed, or committed.

---

## Adding a Service Later

Re-run `install.sh` at any time. It detects existing configuration and prompts only for new services. Existing tokens are not overwritten unless you choose to update them.

```bash
cd ~/Developer/{base}/{prefix}-dotfiles
./install.sh
```
