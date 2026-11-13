# Kiro features in Page 888

| Kiro feature | Files in this repo | Planned use |
|---|---|---|
| Specs | `.kiro/specs/page888/requirements.md`, `design.md`, `tasks.md` | Source of truth for behaviour. Requirements R1-R14 carry EARS criteria; criteria marked [PBT] become property tests. Implementation proceeds task by task from the spec. |
| Steering | `.kiro/steering/product.md`, `structure.md`, `tech.md`, `teletext-style.md` (fileMatch: palette, grid, double-height rules) | Always-on rules: stdlib-only, no JS, 40x24 grid, 50 KB budget, NWS etiquette, accessibility, no broadcaster trademarks. |
| Hooks | `.kiro/hooks/page-budget-a11y.json`, `spec-trace.json`, `no-js-guard.json` | `page-budget-a11y`: run `tools/check_pages.py site` when generated pages, templates, CSS or `render.py` are saved. `spec-trace`: on saving `src/page888/*.py`, agent names the requirement/property numbers implemented and adds or updates the test. `no-js-guard`: on Stop, run `tools/check_pages.py site --strict`. |
| Custom agents | `.kiro/agents/teletext-qa.json` | Read-only strict reviewer for accessibility and teletext budgets. Tools limited to read, grep and shell (shell restricted to pytest and `tools/check_pages.py`). |
| Static checker | `tools/check_pages.py` | Shared by the hooks and the agent. Checks size, script/handler/external resources, lang/title/main/h1/nav label. Exits 0 with a message if `site/` does not exist yet. It complements, and does not replace, the build's own `verify` stage (R9, R12, R13). |
| MCP | none configured (`.kiro/settings/mcp.json` not created) | Candidates only; see below. |
| Powers | none installed | Candidates only; see below. |
| Property-based testing | `tests/test_*.py` (`test_prop_*`, hypothesis); [PBT] criteria in `requirements.md` | Kiro's spec-driven PBT feature is IDE-only and will be run in Kiro IDE. The hypothesis tests themselves also run in plain `pytest -q`, which is what CI/the CLI use. |

## MCP server candidates (candidate, not yet installed)

- Fetch/HTTP MCP server: candidate, not yet installed. Use: explore `api.weather.gov/alerts/active?area=XX&status=actual` responses while writing fixtures for `tests/fixtures/`. Must send a descriptive User-Agent and stay within the NWS etiquette in `tech.md`; fixtures are recorded once, so tests never hit the network.
- Filesystem MCP server: candidate, not yet installed. Use: structured access to `site/` and `tests/fixtures/`. Kiro's built-in file tools may make it unnecessary.
- Git MCP server: candidate, not yet installed. Use: inspecting history and diffs during review. The `git` CLI may make it unnecessary.

## Powers candidates (candidate, not yet installed)

No specific power has been verified for this project. Categories worth checking in the Kiro power catalogue:

- Python testing/pytest helper power: candidate, not yet installed.
- Accessibility (WCAG/axe-style) checking power: candidate, not yet installed. Any such tool must not add runtime dependencies or ship anything in `site/`.
- Static-site hosting/deployment power for the chosen free host: candidate, not yet installed.

## Notes

- Hooks run `python3 tools/check_pages.py ...` from the workspace root.
- No figures about effectiveness are claimed here; none have been measured.
