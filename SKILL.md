---
name: drupal-contribute-fix
description: >
  REQUIRED when user mentions a Drupal module + error/bug/issue - even without
  stack traces. Trigger on: (1) "<module_name> module has an error/bug/issue",
  (2) "Acquia/Pantheon/Platform.sh" + module problem, (3) any contrib module name
  (metatag, webform, mcp, paragraphs, etc.) + problem description. Searches
  drupal.org BEFORE you write code changes. NOT just for upstream contributions -
  use for ALL local fixes to contrib/core.
license: GPL-2.0-or-later
metadata:
  author: Drupal Community
  version: "1.7.0"
---

# drupal-contribute-fix

**Use this skill for ANY Drupal contrib/core bug - even "local fixes".**

Checks drupal.org before you write code, so you don't duplicate existing fixes.

## Preferred Companion Skill: drupalorg-cli (Highly Recommended)

`drupal-contribute-fix` should focus on bug identification, triage quality, and report prep.
Use `drupalorg-cli` for issue-fork, MR, and pipeline execution steps.

Recommended split:

- **This skill:** detect bug ownership, search/match upstream issues, build clear reproduction + test steps, prepare submission-ready notes.
- **drupalorg-cli:** fork/remote setup, branch checkout, MR inspection, pipeline status/log checks, iterative push loop.

Quick prerequisite check:

```bash
drupalorg --version
php -v
```

Use `drupalorg-cli` commands (0.8+ expected, PHP 8.1+):

```bash
drupalorg issue:show <nid> --format=llm
drupalorg issue:get-fork <nid> --format=llm
drupalorg issue:setup-remote <nid>
drupalorg issue:checkout <nid> <branch>
drupalorg mr:list <nid> --format=llm
drupalorg mr:status <nid> <mr-iid> --format=llm
drupalorg mr:logs <nid> <mr-iid>
```

If `drupalorg-cli` is unavailable, fall back to the manual Drupal.org/GitLab flow below.

## Resolving Script Paths

All script paths below are relative to this skill's root directory — NOT your current working directory. Before running any command, resolve the skill root once:

```bash
for d in "$HOME/.agents/skills/drupal-contribute-fix" "$HOME/.codex/skills/drupal-contribute-fix"; do [ -f "$d/SKILL.md" ] && DCF_ROOT="$d" && break; done
```

All commands below use `$DCF_ROOT`. You only need to run the line above once per session.

## FIRST STEP - Before Writing Any Code

**If you are debugging an error in `docroot/modules/contrib/*` or `web/modules/contrib/*`,
run `preflight` BEFORE editing any code - even if the user only asked for a local fix.**

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project <module-name> \
  --keywords "<error message>" \
  --out .drupal-contribute-fix
```

### False-Positive Guard (Required)

`preflight` candidate matching is heuristic. Do not treat "already fixed" output as final without verification.

Before stopping work due to an "existing fix", you must verify all of the following:

1. Open the referenced issue/commit and confirm its title/component matches the bug class and code area.
2. Inspect the exact affected file/function in the target branch and confirm the bug condition is actually gone.
3. Record file path + commit/issue evidence in your notes/report before closing/switching local tracking.

If any verification step fails, treat it as a false positive and continue triage/fix flow.

This takes 30 seconds and may save hours of duplicate work.

**Important:** Drupal.org's `api-d7` endpoint does **not** support a full-text `text=` filter (it returns HTTP 412). If you need a manual keyword search link, use the Drupal.org UI search:

```text
https://www.drupal.org/project/issues/search/<project>?text=<keywords>
```

## Optional Companion Skill: drupal-issue-queue

If the `drupal-issue-queue` skill is also available, use it for deeper triage and clean issue summaries (still read-only, still `api-d7`):

- Summarize the best-match issue:
  - `python scripts/dorg.py issue <nid-or-url> --format md`
- Filter/search a project's issue queue (status/priority/category/version/component/tag):
  - `python scripts/dorg.py search --project <machine_name> --status "needs review" --limit 20 --format json`

(Run those commands from the `drupal-issue-queue` skill directory.)

If the tool isn’t in a standard location, set `DRUPAL_ISSUE_QUEUE_DIR=/path/to/drupal-issue-queue`.

## LAST STEP - Produce a Handoff (Always)

This skill should always end with a clear handoff package for upstream contribution.

If you made local code changes, run `package`:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path docroot/modules/contrib/<module-name> \
  --keywords "<error message>" \
  --test-steps "<step 1>" "<step 2>" "<step 3>" \
  --out .drupal-contribute-fix
```

If you did triage-only (no local code change), preserve `preflight` evidence and provide:
- The best-match issue(s)/MR(s)
- Specific reproduction + expected behavior steps
- Suggested `drupalorg-cli` commands to continue contribution work

**Then tell the user** where the artifacts are and what to run next.

## NEVER DELETE Contribution Artifacts

**DO NOT delete these files:**
- `.drupal-contribute-fix/` directory
- Diff files in `diffs/`
- `ISSUE_COMMENT.md`
- `REPORT.md`

Even if the user asks to "reset" or "undo" the local fix, **preserve the contribution artifacts**
so the fix can be submitted upstream. The whole point is to help the Drupal community.

## Complete Workflow

```
1. DETECT    → Error from contrib/core? Trigger activated.
2. PREFLIGHT → Search drupal.org BEFORE writing code
3. TRIAGE    → Verify/score candidates, avoid false positives
4. PREP      → Produce report-quality repro/test steps and recommendation
5. PACKAGE   → If code changed, run `package`; otherwise keep preflight evidence only
6. HANDOFF   → Prefer `drupalorg-cli` for fork/MR/pipeline execution
7. PRESERVE  → Keep .drupal-contribute-fix/ artifacts for follow-up
```

**Steps 4-7 are MANDATORY.** Don't stop at "issue found"; leave an actionable handoff.

## When to Use This Skill

### Early Conversational Triggers - Fire BEFORE Investigation

**You don't need a stack trace to trigger this skill.** Fire on high-level descriptions:

| User Says | Trigger? | Why |
|-----------|----------|-----|
| "The metatag module has an error" | **YES** | Module name + "error" |
| "mcp module isn't working with Acquia" | **YES** | Module + platform constraint |
| "I'm getting a bug in webform" | **YES** | Module name + "bug" |
| "paragraphs module throws an exception" | **YES** | Module + error indicator |
| "contrib module X has a problem" | **YES** | Explicit "contrib" mention |
| "my custom module has a bug" | Maybe | Only if it triggers a contrib/core bug |

**Key insight:** If the user mentions a Drupal module name (that isn't clearly custom) + any problem indicator (error, bug, issue, not working, exception, broken), trigger this skill FIRST. Don't wait until you've investigated and found a stack trace.

### MANDATORY Triggers - You MUST Use This Skill When:

1. **Error/exception originates FROM contrib or core code**
   - Stack trace shows `modules/contrib/` or `core/` as the source
   - Error message references a class in `Drupal\<contrib_module>\` namespace
   - Fatal error, TypeError, exception thrown by contrib/core code

2. **You are about to edit files in contrib or core**
   - `docroot/modules/contrib/*` or `web/modules/contrib/*`
   - `docroot/core/*` or `web/core/*`
   - `docroot/themes/contrib/*` or `web/themes/contrib/*`

3. **You are about to modify contrib/core code that should go upstream**
   - Replacing ad-hoc Composer patching with a real MR contribution
   - Converting temporary local fixes into issue-fork/MR work

4. **Custom module encounters a bug in core/contrib**
   - Custom code works correctly but triggers a bug in contrib/core
   - The fix would need to be in the contrib/core code, not the custom module

5. **Hosting platform constraints cause contrib/core issues**
   - "Acquia best practices", "Pantheon", "Platform.sh" constraints
   - Core module disabled/unavailable causing contrib to fail

### This Skill is NOT Just for "Upstream Contributions"

**Common misconception:** This skill is only for patch uploads to drupal.org.

**Reality:** Use it for ALL local fixes to contrib modules. Why?
- The bug may already be fixed upstream (save yourself the work)
- An existing MR or attachment may already solve it
- Even if you need a local fix NOW, the preflight search is fast

### How to Recognize Contrib/Core Errors

Look for these patterns in error messages or stack traces:

```
# Error ORIGINATES from contrib - USE THIS SKILL
Drupal\metatag\MetatagManager->build()
docroot/modules/contrib/mcp/src/Plugin/Mcp/General.php
web/modules/contrib/webform/src/...
core/lib/Drupal/Core/...

# Error in CUSTOM module - skill may not apply
# (unless the custom code is triggering a bug in contrib/core)
modules/custom/mymodule/src/...
```

### Path Triggers:

- `web/core/`, `web/modules/contrib/`, `web/themes/contrib/`
- `docroot/core/`, `docroot/modules/contrib/`, `docroot/themes/contrib/`
- `patches/` directory (especially `patches/drupal-*`)

## What To Do

1. **FIRST**: Run `preflight` to search drupal.org (even for "local fixes")
2. **TRIAGE**: Verify candidate quality (issue title/component/file/function match)
3. **DOCUMENT**: Write precise reproduction, before/after behavior, and test steps
4. **IF CODE CHANGED**: Run `package` to generate artifacts; otherwise keep preflight outputs
5. **HANDOFF TO CLI**: Recommend `drupalorg-cli` commands for fork/MR/pipeline flow
6. **PRESERVE**: Keep `.drupal-contribute-fix/` directory - NEVER delete it
7. **GUIDE USER**: Tell them the exact next command(s) to run

## What This Skill Does

1. **Identifies contrib/core bug ownership** from symptoms, paths, and stack traces
2. **Searches drupal.org** for existing issues/MRs/attachments matching the bug
3. **Validates candidate relevance** before declaring "already fixed"
4. **Builds report-quality issue content** (repro steps, expected/actual behavior, rationale)
5. **Generates contribution artifacts** when local code changes exist:
   - Paste-ready issue comment
   - Properly-named local `.diff` file
   - Validation results (php lint, phpcs if available)
6. **Hands off execution to `drupalorg-cli`** for branch/MR/pipeline actions

## Mandatory Gatekeeper Behavior

**No new local diff artifact may be generated until upstream search + "already fixed?" checks are complete.**
**No "STOP existing fix found" decision may be accepted until the file-level verification steps above are completed.**

The skill ends in exactly one of these outcomes:

| Exit Code | Outcome | Meaning |
|-----------|---------|---------|
| 0 | PROCEED | MR artifacts + local diff generated |
| 10 | STOP | Existing upstream fix found (MR-based, historical patch attachments, or closed-fixed) |
| 20 | STOP | Fixed upstream in newer version (reserved for future use) |
| 30 | STOP | Analysis-only recommended (change would be hacky/broad) |
| 40 | ERROR | Couldn't determine project/baseline, network failure |
| 50 | STOP | Security-related issue detected (follow security team process) |

**Workflow modes:** When an existing fix is found (exit 10), the skill reports whether the
issue has an active MR or only historical patch attachments to guide contributor workflow.

## Workflow Hygiene (MR-first)

Drupal contributions should be handled through **Merge Requests (MRs)**.
To reduce maintainer back-and-forth, this skill records workflow context but defaults to MR-only contributions for new work.
When available, drive execution with `drupalorg-cli` instead of manual UI/Git steps.

Outputs (in every issue directory):
- `WORKFLOW.md` - at-a-glance workflow decision + links + MR-first guidance
- `REPORT.md` - includes a **Workflow** section near the top
- `ISSUE_COMMENT.md` - template is workflow-aware:
  - MR-based: comment template points to the existing MR(s)
  - Historical patch attachments: comment template still directs follow-up via MR workflow

Rule of thumb:
- **MR-based issues:** contribute via GitLab MR/issue fork branch; don't upload new patches to the Drupal.org issue unless maintainers request it.
- **Issues with only historical patch attachments:** use MR workflow for new work; use old attachments as context.

## Commands

### Preflight (search only)

Search drupal.org for existing issues without generating local artifacts:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project metatag \
  --keywords "TypeError MetatagManager::build" \
  --paths "src/MetatagManager.php" \
  --out .drupal-contribute-fix
```

### drupalorg-cli handoff (preferred execution path)

After triage identifies the target issue/MR, use `drupalorg-cli` for issue-fork and MR execution:

```bash
drupalorg issue:show <nid> --format=llm
drupalorg issue:get-fork <nid> --format=llm
drupalorg issue:setup-remote <nid>
drupalorg issue:checkout <nid> <branch>
drupalorg mr:list <nid> --format=llm
drupalorg mr:status <nid> <mr-iid> --format=llm
drupalorg mr:logs <nid> <mr-iid>
```

### Package (search + generate)

Search upstream AND generate contribution artifacts if appropriate:

```bash
# For web/ docroot layout:
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path web/modules/contrib/metatag \
  --keywords "TypeError MetatagManager::build" \
  --test-steps "Enable metatag" "Visit affected page" "Confirm fixed behavior" \
  --out .drupal-contribute-fix

# For docroot/ layout (common in Acquia/BLT projects):
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/drupal/site \
  --changed-path docroot/modules/contrib/mcp \
  --keywords "module not installed" "update_get_available" \
  --test-steps "Set up failing config" "Trigger failing code path" "Confirm expected post-fix result" \
  --out .drupal-contribute-fix
```

**Note:** `package` always runs `preflight` first and refuses to generate local artifacts
if an existing fix is found (unless `--force` is provided).

### Test (generate RTBC comment)

Generate a Tested-by/RTBC comment for an existing MR or diff artifact you've tested:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" test \
  --issue 3345678 \
  --tested-on "Drupal 10.2, PHP 8.2" \
  --result pass \
  --out .drupal-contribute-fix
```

Options: `--result` can be `pass`, `fail`, or `partial`. Use `--mr` or `--patch`
to specify which artifact you tested.

### Reroll (legacy patch-only issues)

Legacy fallback only: reroll an existing patch attachment when maintainers explicitly request patch workflow:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" reroll \
  --issue 3345678 \
  --patch-url "https://www.drupal.org/files/issues/metatag-fix-3345678-15.patch" \
  --target-ref 2.0.x \
  --out .drupal-contribute-fix
```

This downloads the patch, attempts to apply it to your target branch, and generates
a rerolled patch if needed (or confirms it applies cleanly). Prefer MR workflow for new contributions.

### Common Options

| Option | Description |
|--------|-------------|
| `--project` | Drupal project machine name (e.g., `metatag`, `drupal`) |
| `--keywords` | Error message fragments or search terms (space-separated) |
| `--paths` | Relevant file paths (space-separated) |
| `--out` | Output directory for artifacts |
| `--offline` | Use cached data only, don't hit API |
| `--force` | Override gatekeeper and generate local diff artifact anyway |
| `--issue` | Known issue number (runs gatekeeper check against this issue) |
| `--detect-deletions` | Include deleted files in diff (risky with Composer trees) |
| `--test-steps` | **REQUIRED** Specific test steps for the issue (agent must provide) |

### Test Steps (MANDATORY)

**Agents MUST provide specific test steps via `--test-steps`.** Generic placeholders are not acceptable.

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --changed-path docroot/modules/contrib/mcp \
  --keywords "update module not installed" \
  --test-steps \
    "Enable MCP module with Update module disabled" \
    "Call the general:status tool via MCP endpoint" \
    "Before fix: Fatal error - undefined function update_get_available()" \
    "After fix: JSON response with status unavailable" \
  --out .drupal-contribute-fix
```

Test steps should:
1. Describe how to set up the environment to reproduce the bug
2. Describe the action that triggers the bug
3. Describe the expected behavior BEFORE the fix (the bug)
4. Describe the expected behavior AFTER the fix (the fix)

## Output Files

```
.drupal-contribute-fix/
├── UPSTREAM_CANDIDATES.json              # Search results cache (shared)
├── 3541839-fix-metatag-build/            # Known issue
│   ├── REPORT.md                         # Analysis & next steps
│   ├── ISSUE_COMMENT.md                  # Paste-ready drupal.org comment
│   └── diffs/
│       └── project-fix-3541839.diff
├── 3573571-component-context/            # Optional local CI evidence
│   ├── LOCAL_CI_PARITY_2026-02-16.md     # Job/result summary + commands
│   └── ci/
│       ├── canvas-ci-local-full-20260216.log
│       └── canvas-ci-local-rerun-20260216.log
└── unfiled-update-module-check/          # New issue needed
    ├── REPORT.md
    ├── ISSUE_COMMENT.md
    └── diffs/
        └── project-fix-new.diff
```

**Directory naming:**
- `{issue_nid}-{slug}/` - Existing issue matched or specified
- `unfiled-{slug}/` - No existing issue found

**Preflight vs Package:** `preflight` only updates `UPSTREAM_CANDIDATES.json`.
Issue directories are created by `package` when generating artifacts.

## Local CI Evidence Artifacts (Recommended)

If local CI parity tooling is available (for example `gitlab-ci-local`), keep
evidence under the issue directory in `.drupal-contribute-fix/`:

- `LOCAL_CI_PARITY_YYYY-MM-DD.md`: concise summary with exact commands, exit codes,
  pass/fail/incomplete jobs, and blocker details.
- `ci/*.log`: raw logs for audit/debug follow-up.
- `drupal-contribute-fix package` now auto-creates `LOCAL_CI_PARITY_YYYY-MM-DD.md`
  when `ci/*.log` exists in that issue directory and no parity summary file exists yet.

Rules:
- These are local review artifacts, not upstream contribution artifacts.
- Keep them out of MR diffs.
- If local CI tooling mutates tracked files, restore tracked files before preparing
  the final MR diff.
- If the tooling is unavailable, record `not run` and why.

## Security Issue Handling

If the fix appears security-related, the skill will **STOP with exit code 50**.

Security indicators:
- Access bypass patterns
- User input reaching dangerous sinks (SQL, shell, eval)
- Authentication/session handling changes
- File system access control modifications

**Do NOT post security issues publicly.** Follow the Drupal Security Team process:
https://www.drupal.org/drupal-security-team/security-team-procedures

## Minimal + Upstream Acceptable

The skill enforces contribution best practices:

- **Warns** if a change touches >3 files or has large LOC changes
- **Separates** "must fix" from "nice-to-haves" (nice-to-haves excluded from submitted change)
- **Detects** patterns likely to be rejected:
  - Broad cache disables/bypasses
  - Swallowed exceptions
  - Access check bypasses
  - Environment-specific hacks

See [references/hack-patterns.md](references/hack-patterns.md) for details.

## Validation

The skill runs validation and reports results honestly:

- **Always runs:** `php -l` on changed PHP files
- **Runs if available:** PHPCS with Drupal standard
- **Never claims** tests passed if they weren't run

## After Completion - What To Tell The User

When triage/fix is complete, **you MUST inform the user** about the contribution artifacts and provide a CLI-first handoff:

```
I completed contrib/core bug triage and prepared contribution artifacts:

📁 .drupal-contribute-fix/<nid>-<slug>/
  - REPORT.md - Triage findings and next steps
  - ISSUE_COMMENT.md - Copy/paste issue or MR comment text
  - WORKFLOW.md - MR/patch workflow recommendation
  - diffs/<diff-file>.diff - Present only when code changed (local artifact)

**Recommended next commands (drupalorg-cli):**
drupalorg issue:show <nid> --format=llm
drupalorg issue:get-fork <nid> --format=llm
drupalorg issue:setup-remote <nid>
drupalorg issue:checkout <nid> <branch>
drupalorg mr:list <nid> --format=llm
```

For unfiled issues (no existing drupal.org issue found):
```
📁 .drupal-contribute-fix/unfiled-<slug>/
  - Create a new issue at https://www.drupal.org/project/issues/<project> first
  - Use ISSUE_COMMENT.md as the issue description template
  - Then continue with drupalorg-cli using the new issue NID
```

**DO NOT skip this step.** The user may not know about the contribution workflow.

## Drupal.org GitLab Workflow (CLI-first)

**All Drupal core and contrib contributions use GitLab merge requests.** Patch uploads are exception-only when explicitly requested by maintainers.

**Reference**: https://www.drupal.org/docs/develop/git/using-gitlab-to-contribute-to-drupal

### Preferred command sequence

```bash
drupalorg issue:show <nid> --format=llm
drupalorg issue:get-fork <nid> --format=llm
drupalorg issue:setup-remote <nid>
drupalorg issue:checkout <nid> <branch>
drupalorg mr:list <nid> --format=llm
drupalorg mr:status <nid> <mr-iid> --format=llm
drupalorg mr:logs <nid> <mr-iid>
```

### Iteration loop (after triage)

```bash
git add <changed-files>
git commit -m "Issue #<nid> by <username>: <short description>"
git push
drupalorg mr:status <nid> <mr-iid> --format=llm
drupalorg mr:logs <nid> <mr-iid>   # only if failing
```

### Rebase when needed

```bash
git fetch origin
git checkout BASE_BRANCH_NAME
git pull
git checkout ISSUE_BRANCH_NAME
git rebase BASE_BRANCH_NAME
git push --force-with-lease
```

### GitLab CI Automated Testing

**GitLab CI runs automatically on all merge requests.** You cannot test patch files—contributions must be merge requests to be tested.

**What runs automatically:**
- Compatibility testing across Drupal Core versions
- PHP and database configuration testing
- PHPCS, PHPStan, and cspell linting
- Project-specific PHPUnit tests

**Interpreting results:**
1. Check pipeline status with `drupalorg mr:status <nid> <mr-iid> --format=llm`
2. If failing, inspect logs with `drupalorg mr:logs <nid> <mr-iid>`
3. Apply fixes, push again, and re-check status

**Triggering test re-runs:**
- Push additional commits to the branch

**Important:** GitLab CI uses `phpunit.xml.dist`, `phpstan.neon.dist` and other `.dist` files. Review these files as they may cause unexpected test failures.

### Manual fallback (only when drupalorg-cli is unavailable)

If `drupalorg-cli` cannot run in the environment, use the issue page's **Issue fork**
controls and standard Git/GitLab UI as a fallback.

### Local CI Parity (Best Effort)

If local CI tooling exists in the contributor environment, run parity checks and
archive evidence under `.drupal-contribute-fix/<issue>/`:

1. Save the exact command line(s) and exit status.
2. Save raw logs in `ci/`.
3. Summarize outcomes in `LOCAL_CI_PARITY_YYYY-MM-DD.md` (auto-scaffolded by
   `package` when `ci/*.log` is present).

If local parity tooling is not installed or blocked by environment constraints,
state that clearly and do not claim full local parity.

### Drupal Core Contributions

**Drupal core requires test coverage for all changes.** Contrib modules don't require tests (though they're encouraged).

For core contributions, you MUST:
1. Include test coverage for changes
2. Ensure all existing tests pass
3. Update tests if behavior changes

See [references/core-testing.md](references/core-testing.md) for:
- Choosing the right test type (Unit vs Kernel vs Functional)
- Test file locations and class structure
- Example test classes
- Running tests locally (DDEV/Lando commands)
- Test coverage checklist

### Contribution Workflow Summary

```
1. Detect + triage bug with `preflight`
2. Prepare report-quality reproduction and test steps
3. Identify target issue/MR (or file a new issue)
4. Use `drupalorg-cli` to set up fork remote + checkout branch
5. Make changes with test coverage (required for core)
6. Push commits and monitor MR pipeline
7. Iterate until pipeline is green and review feedback is addressed
```

### Key Command Reference

| Task | Command |
|------|---------|
| Show issue details | `drupalorg issue:show <nid> --format=llm` |
| Inspect fork + branches | `drupalorg issue:get-fork <nid> --format=llm` |
| Set up issue fork remote | `drupalorg issue:setup-remote <nid>` |
| Check out issue branch | `drupalorg issue:checkout <nid> <branch>` |
| List MRs | `drupalorg mr:list <nid> --format=llm` |
| Check MR pipeline | `drupalorg mr:status <nid> <mr-iid> --format=llm` |
| Read failing job logs | `drupalorg mr:logs <nid> <mr-iid>` |
| Push latest commit(s) | `git push` |

## References

- [references/issue-status-codes.md](references/issue-status-codes.md) - Drupal.org issue status mapping
- [references/patch-conventions.md](references/patch-conventions.md) - Patch naming and format
- [references/hack-patterns.md](references/hack-patterns.md) - Patterns to avoid
- [references/core-testing.md](references/core-testing.md) - Writing tests for Drupal core contributions

## Example Output

See [examples/sample-report.md](examples/sample-report.md) for a complete example.
