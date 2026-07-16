# Integrations Framework & Jira (Server / Data Center) Plan

> **Status: design only — no implementation yet.**
> Goal: let TestGen use Jira as **both** a *source* of requirements and a *sink*
> for generated test cases, where actions run **as the logged-in user's own Jira
> account**, on a **hosted** Jira (Server / Data Center — not Cloud). The design
> is deliberately provider-agnostic so Azure DevOps, Xray, Zephyr, TestRail,
> Polarion, etc. can be added as drop-in adapters.

---

## 1. Design principle — Ports & Adapters (hexagonal)

The TestGen core never imports Jira. It depends only on **abstract ports**. Jira
is one **adapter**. Adding another platform = new adapter, **zero core changes**.

```
                      ┌─────────────────────────────────────────┐
                      │                TestGen core              │
   Requirements  ◀────┤  RequirementsSource (port)               │
   (documents)        │  TestCaseSink       (port)               │────▶  Test cases
                      │  AuthStrategy       (port)               │        (push)
                      │  FieldMapper        (port)               │
                      └──────────────▲───────────────▲───────────┘
                                     │ implements     │ implements
                    ┌────────────────┴───┐   ┌────────┴───────────────┐
                    │ jira_server adapter │   │ azure_devops adapter … │
                    └─────────────────────┘   └────────────────────────┘
```

Everything platform-specific (REST paths, auth dance, field names, test-mgmt
app quirks) lives inside an adapter. A **registry** exposes installed adapters to
the API/UI dynamically.

### Proposed package layout
```
backend/app/integrations/
├── base.py            # Port interfaces + normalized DTOs (no vendor code)
├── registry.py        # register/lookup adapters by name; capability discovery
├── models.py          # Connection, Identity, ExternalLink storage models
├── crypto.py          # encrypt/decrypt tokens at rest (Fernet/AES-GCM)
├── fake/              # in-memory adapter for tests + offline demo
│   └── adapter.py
└── jira_server/
    ├── adapter.py     # wires auth + source + sink + mapping together
    ├── client.py      # thin REST client over /rest/api/2 (+ Xray/Zephyr)
    ├── auth_pat.py    # Personal Access Token  (DC 8.14+)
    ├── auth_oauth2.py # OAuth 2.0 (DC as provider, Authorization Code + PKCE)
    ├── auth_oauth1.py # OAuth 1.0a (RSA) — legacy Server application links
    ├── source.py      # JQL search + issue → RequirementDocument
    ├── sink.py        # test case → Jira issue / Xray / Zephyr test
    └── mapping.py     # default + preset field maps (plain / Xray / Zephyr)
```

---

## 2. The ports (stable contracts)

Defined in `integrations/base.py`. All DTOs are plain, vendor-neutral.

### 2.1 `AuthStrategy` — "log in as the user"
```
begin_login(user_id, connection)      -> LoginChallenge   # redirect URL or form spec
complete_login(user_id, callback)     -> StoredCredential # after redirect/PAT submit
get_client(user_id, connection)       -> AuthedClient     # applies token, auto-refresh
revoke(user_id, connection)           -> None
whoami(user_id, connection)           -> ExternalUser     # validates the session
```
Each auth method (PAT / OAuth2 / OAuth1) is a separate `AuthStrategy`
implementation selected by `connection.auth_method`. This is the crux of the
"act as the user" requirement — see §4.

### 2.2 `RequirementsSource` — Jira → TestGen (source)
```
search(client, query)                 -> list[ExternalRef]   # query = JQL for Jira
fetch(client, ref)                    -> RequirementDocument # normalized
capabilities()                        -> {supports_search, supports_attachments,…}
```
`RequirementDocument` maps directly onto the **existing `Document` model**
(title, content, doc_type, metadata) plus a `source` block
(`{provider, external_key, url, synced_at}`).

### 2.3 `TestCaseSink` — TestGen → Jira (sink)
```
push(client, testcase, target)        -> ExternalRef  # create issue/test
update(client, external_ref, testcase)-> ExternalRef  # idempotent re-push
link(client, test_ref, requirement_ref, link_type)    # e.g. Test "tests" Story
capabilities()                        -> {supports_update, supports_link, bdd_field,…}
```
`target` carries the **destination Jira project** (`project_key`) and issue type.
It defaults to the connection's `push_project_key` / `push_issue_type` and can be
**overridden per push** from the UI, so different runs can target different Jira
projects with the same connection.

### 2.4 `FieldMapper` — declarative, per-connection
Generalizes today's `export.py::DEFAULT_JIRA_MAPPING` into structured, per-
connection config with transforms (e.g. `gherkin → Xray Cucumber scenario
field`, `priority enum → Jira priority id`). Ships **presets**: `plain_jira`,
`xray`, `zephyr`.

---

## 3. Data model additions (new storage collections)

Mirrors the existing `Collection` KV pattern in `storage.py`.

| Collection | Purpose | Secrets? |
|---|---|---|
| `connections` | A configured provider instance (per project or workspace): `{id, provider, base_url, auth_method, ca_bundle, mapping_preset, field_overrides,` **`push_project_key`** `,` **`push_issue_type`** `,` **`import_project_key`** `}`. The **push target Jira project** is configured here and can be overridden per push. | No (client *secret* stays in env/secret store) |
| `identities` | Per **(app-user, connection)** credential: `{user_id, connection_id,` **`jira_username`** `, pat*, access_token*, refresh_token*, expires_at, scopes, external_account}` — **encrypted at rest**. For PAT auth the user's **manually entered Jira identity + PAT** live here (see §4). | Yes (encrypted) |
| `external_links` | `{entity_type, testgen_id, external_key, url, hash, synced_at}` — idempotent sync ledger (document.id↔issueKey, testcase.id↔testKey) | No |

Small extensions to existing models: `Document.source` and
`TestCase.external_refs: [...]`.

---

## 4. Authentication — acting as the user on hosted Jira

Hosted Jira has different options than Cloud. We support three, all behind the
same `AuthStrategy` port, chosen per connection:

| Method | Jira support | UX | Notes |
|---|---|---|---|
| **PAT (Personal Access Token)** — *chosen for Phase 1* | **Data Center 8.14+** | In **Settings**, the user enters their **Jira identity (username/email)** and **pastes a PAT** they created in Jira → *Profile → Personal Access Tokens* | **Simplest per-user identity, no SSO needed.** Bearer token; both the entered identity and PAT are validated against `/rest/api/2/myself` and stored encrypted. |
| **OAuth 2.0 (Auth Code + PKCE)** | DC 8.x+ (as OAuth provider via Application Links) | Click "Connect" → redirect to Jira → approve | SSO-friendly, refreshable, no token handling by user. Requires registering a redirect URI + client in Jira. |
| **OAuth 1.0a (RSA-SHA1)** | Server / older DC | 3-legged request→authorize→access dance | Legacy fallback for estates without OAuth2/PAT. |

Explicitly **excluded**: basic auth (username/password) and cookie/session login —
deprecated on DC and incompatible with SSO.

**Why this satisfies "actions performed as their account":** every source/sink
call uses `get_client(user_id)`, which loads *that user's* token. Jira then
enforces *that user's* permissions server-side — a security benefit we get for
free (no over-privileged service account).

### OAuth 2.0 sequence (server-side, per user)
```
Frontend  ── POST /integrations/{conn}/login/start ──▶ Backend
Backend   ── builds authorize URL (state+PKCE) ───────▶ returns URL
Browser   ── redirect to Jira, user logs in as self ──▶ Jira
Jira      ── redirect GET /integrations/callback?code&state ─▶ Backend
Backend   ── exchange code → access+refresh token ────▶ encrypt + store (user,conn)
later     ── get_client(user) → auto-refresh if expired
```
PAT flow is the same port with no redirect (validate + store the pasted token).

### App-user identity — **manual entry in Settings (decided)**
No SSO/OIDC dependency. The user **types their Jira identity (username/email)
alongside their PAT** in the Settings → Integrations screen; that entered
identity is what actions are attributed to and what keys the stored credential.

- The manually entered Jira identity **is** the `user_id` for the credential
  record — on save we call `/rest/api/2/myself` to verify the PAT resolves to
  that identity, and persist `{jira_username, pat}` **encrypted**.
- The frontend passes the active identity on requests (e.g. an `X-User-Id`
  header set from Settings) so the backend loads the right PAT; no login server
  or reverse proxy is required.
- **App authentication (who the TestGen user is)** stays cleanly separated from
  **Jira authorization (their PAT)**, so SSO/OIDC can be slotted in later without
  touching the adapters — but it is **not** required for this build.

---

## 5. Security
- **Encrypt tokens at rest** (`integrations/crypto.py`, Fernet/AES-GCM; key from
  `TESTGEN_SECRET_KEY` env or KMS). Never store plaintext tokens.
- **OAuth hardening**: CSRF `state`, PKCE, short-lived state store, exact
  redirect-URI match.
- **Never log tokens**; redact in errors.
- **On-prem TLS**: allow a custom **CA bundle** per connection for corporate
  self-signed certs (common on hosted Jira). Never disable verification.
- **Least privilege / scopes**; disconnect endpoint revokes server-side too.

---

## 6. Sync semantics

**Source (Jira → TestGen).** JQL-driven import into `documents`
(`doc_type=requirements`), preserving `external_key`. Re-import of a changed
issue creates a **new version** (reuses the existing document-versioning
feature). Freshness options: on-demand, scheduled poll, or Jira webhooks.

**Sink (TestGen → Jira).** Only **approved** test cases are pushable (respects
the existing approval workflow, HLR10). **Idempotent** via `external_links`
(create vs update). The **destination Jira project is configurable** —
`push_project_key` on the connection sets the default, and the UI lets the user
**override the target project (and issue type) per push**. Destination form:
- plain Jira issue of type **Test** (Gherkin in Description) — Phase 1 default, or
- **Xray** / **Zephyr** test entity (Gherkin in the app's Cucumber/BDD field).
Optionally **link** each Test to its source Story (`"tests"` link). Supports a
**dry-run preview** using the field mapping before writing anything.

---

## 7. API surface (new `integrations` router)
```
GET    /integrations/providers                     # registry + capabilities
POST   /integrations/connections                   # configure a connection
GET    /integrations/connections                   # list (per project/workspace)
POST   /integrations/connections/{id}/login/start  # OAuth: returns authorize URL
GET    /integrations/callback                       # OAuth redirect handler
POST   /integrations/connections/{id}/login/pat     # PAT: submit {jira_username, pat} → verify via /myself → store encrypted
GET    /integrations/connections/{id}/status        # is current user connected (+ resolved account)
DELETE /integrations/connections/{id}/identity      # disconnect / revoke
POST   /integrations/connections/{id}/import        # JQL search → create Documents
POST   /integrations/connections/{id}/push          # push testcase ids; body may override {project_key, issue_type, dry_run}
```

## 8. Frontend
- **Settings → Integrations**: list providers, add a connection (base URL, auth
  method, **push project key**, mapping preset). For PAT: fields to **enter the
  Jira identity (username/email) and paste the PAT**; "Verify" calls
  `/myself` and shows the resolved account + live status.
- **Requirements page**: "Import from Jira" — JQL search, pick issues → creates
  versioned Documents.
- **Review & Approve page**: "Push to Jira" — **choose/confirm the target Jira
  project** (defaults to the connection's, overridable), **dry-run preview** of
  the mapped issue, then push; shows resulting issue links.

## 9. Testing / offline
- Ship a **`fake` adapter** (in-memory) — mirrors the deterministic-LLM
  philosophy so the whole flow runs in tests/demos with no Jira.
- **Contract tests**: one shared port test-suite run against *every* adapter, so
  new providers must satisfy the same behavior.

---

## 10. Phased roadmap
| Phase | Scope |
|---|---|
| **0 — Framework** | Ports, registry, `fake` adapter, storage (`connections`/`identities`/`external_links`), `crypto`, **manual `X-User-Id` identity dependency**. No Jira yet. |
| **1 — Jira PAT MVP** | Jira Server adapter with **PAT** auth (**manual identity + PAT entered in Settings**); JQL import → Documents; push → plain "Test" issue in a **configurable target project**; field mapping; idempotency. Delivers per-user "acts as me" on DC 8.14+ with no SSO. |
| **2 — Jira OAuth** | OAuth 2.0 (DC) + OAuth 1.0a fallback; disconnect/refresh. |
| **3 — Test-mgmt + sync** | Xray/Zephyr mapping presets; Test↔Story linking; webhooks / scheduled sync. |
| **4 — Prove modularity** | Add a second provider (e.g. Azure DevOps) against the same ports. |

---

## 11. Decisions

**Confirmed**
- ✅ **Auth = PAT**, with the user's **Jira identity + PAT entered manually in
  Settings** (no SSO/OIDC). Assumes Jira **Data Center 8.14+** (PAT support).
- ✅ **Push target project is configurable** on the connection and overridable
  per push.

**Still open**
1. **Test management** — Phase 1 targets **plain Jira "Test" issues** by default;
   confirm whether **Xray** / **Zephyr** support is needed (adds mapping presets
   + the BDD/Cucumber field), and if so, which and when.
2. **Secret storage** — env var vs Vault/KMS for the token-encryption key
   (`TESTGEN_SECRET_KEY`).
3. **OAuth (later phases)** — if OAuth 2.0/1.0a is ever wanted, a stable backend
   redirect URI + Jira application-link setup become prerequisites. Not needed
   for the PAT build.
```
