# Supabase Plugin & MCP Setup Review

Single consolidated review of Supabase plugin and MCP configuration for SwiftBolt_ML.

---

## 1. Current State

### Plugin (Cursor Settings)

- **Location:** `.cursor/settings.json`
- **Config:** `"plugins": { "supabase": { "enabled": true } }`
- **Status:** Supabase plugin is **enabled**. This gives you the Supabase sidebar, project linking UI, and in-editor Supabase features.

### Project config (Supabase CLI)

- **Root:** `supabase/config.toml` — `project_id = "cygflaemtmwiwaviclks"`, function `verify_jwt` settings.
- **Backend (local dev):** `backend/supabase/config.toml` — same `project_id`, full local config (db, studio, auth, etc.).
- **Status:** Single project ID used consistently; root config is the one used when running Supabase from repo root.

### MCP (AI-callable tools)

- **Before:** Supabase MCP server was **not** in the list of available MCP servers for the agent (`cursor-ide-browser`, `user-GitHub`, `user-perplexity` only). So the AI could not call `execute_sql`, `apply_migration`, `list_migrations`, etc.
- **Fix applied:** Added `.cursor/mcp.json` so Cursor can start the Supabase MCP server:

```json
{
  "mcpServers": {
    "supabase": {
      "url": "https://mcp.supabase.com/mcp"
    }
  }
}
```

- **After adding:** Restart Cursor (or reload MCP). Then in **Settings → Cursor Settings → Tools & MCP** you should see the Supabase server. The AI will be able to use Supabase tools; when a tool needs a project, use `project_id`: **`cygflaemtmwiwaviclks`** (from `supabase/config.toml`).

---

## 2. What You Should Do

1. **Restart Cursor** (or reload MCP) so it picks up `.cursor/mcp.json`.
2. **Link & auth:** If Cursor prompts you to log in to Supabase (browser), complete sign-in. Link this repo to project **cygflaemtmwiwaviclks** if the UI offers it.
3. **Verify:** In Cursor go to **Settings → Tools & MCP** and confirm the Supabase server is listed. You can ask the AI to run a safe Supabase MCP command (e.g. “List migrations for this project using MCP”) to confirm tools work.
4. **Project ID for MCP:** When the AI calls Supabase MCP tools that take `project_id`, the value is **`cygflaemtmwiwaviclks`** (from `supabase/config.toml`).

---

## 3. MCP Tool Reference (for AI)

Supabase MCP tools live under the server name **`plugin-supabase-supabase`**. Examples:

- `list_migrations` — `{ "project_id": "cygflaemtmwiwaviclks" }`
- `execute_sql` — `{ "project_id": "cygflaemtmwiwaviclks", "query": "..." }`
- `apply_migration` — `{ "project_id": "cygflaemtmwiwaviclks", "name": "snake_case_name", "query": "..." }`
- `list_tables` — `{ "project_id": "cygflaemtmwiwaviclks" }`
- `list_edge_functions`, `deploy_edge_function`, `get_project`, etc. — see `mcps/plugin-supabase-supabase/tools/*.json` for args.

---

## 4. Summary

| Item                    | Status / Action                                      |
|-------------------------|------------------------------------------------------|
| Supabase plugin enabled | Yes (`.cursor/settings.json`)                        |
| Project ID               | `cygflaemtmwiwaviclks` (in both Supabase configs)   |
| MCP server available     | Configured in `.cursor/mcp.json`; restart Cursor     |
| Auth / project linking   | Do in Cursor UI when prompted after restart          |

Once Cursor has restarted and Supabase MCP is listed under Tools & MCP, the Supabase plugin and MCP are set up correctly for this project.

**If Supabase MCP still doesn’t appear:** Some Cursor versions read MCP config only from **Cursor Settings → MCP** (or the global config file). Add the same `supabase` server there (`url`: `https://mcp.supabase.com/mcp`).

---

## 5. Migrations check (wired-in verification)

- **DB:** 151 migrations applied (through `allow_anon_strategies`). Strategy tables exist: `strategy_user_strategies`, `strategy_backtest_jobs`, `strategy_backtest_results`.
- **RLS:** Strategy tables use consolidated policies: `select_own_or_anon_strategies`, `insert_own_or_anon_strategies`, etc., so anon and authenticated users are both supported.
- **Repo:** `supabase/migrations/` is the source of truth. `allow_anon_strategies` was applied via MCP; the DB migration record may show a different version timestamp than the filename `20260222150000_allow_anon_strategies.sql`. If you run `supabase db push` later, Supabase may try to re-apply that file; you can mark it as applied or rely on the existing record.
