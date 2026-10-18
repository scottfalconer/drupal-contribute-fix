---
name: drupal-contribute-fix
description: >
  Investigate bugs in Drupal core or contributed modules, themes, and profiles.
  Search Drupal.org for existing work before code changes. Prepare local diffs,
  reproduction steps, and review evidence for contribution. Use for local fixes
  as well as upstream contribution work.
license: GPL-2.0-or-later
metadata:
  author: Drupal Community
  version: "1.7.0"
---

# Drupal contribution fixes

Help the user resolve a Drupal bug with verified evidence.
Use an existing fix when it applies. Prepare a focused contribution when new work is needed.

Use [CONTRIBUTING.md](CONTRIBUTING.md#documentation-and-generated-text) for all documentation and generated text.

## Find existing work

Resolve `DCF_ROOT` to the directory that contains this `SKILL.md`.
Do not assume that it is the current working directory.

Before you change contrib or core code, run a search:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" preflight \
  --project PROJECT \
  --keywords "ERROR_OR_BEHAVIOR" \
  --paths RELATIVE_FILE_PATH \
  --out .drupal-contribute-fix
```

Use the actual project machine name, error terms, and affected path.
If search access fails, record the limitation. Do not report that no existing fix exists.

Treat matches as candidates. Before you accept an existing fix:

1. Compare the issue's component and failure conditions with the local bug.
2. Inspect the affected file and function in the proposed fix.
3. Check the target branch or release.
4. Reproduce the original failure when possible.
5. Test the proposed fix in the affected environment.
6. Record the issue, commit, files, commands, and results.

A fixed issue status does not prove that an installed release contains the fix.
The tool does not verify development branches or upgrade dependencies automatically.
Exit code `20` is reserved.

Read [Issue status codes](references/issue-status-codes.md) when issue status affects the next action.

## Prepare a new change

Keep changes limited to the verified cause.
Read [Code review patterns](references/hack-patterns.md) when the change affects access checks, caching, exception handling, or site-specific behavior.

Add or adjust a regression test for a bug fix.
For Drupal test selection and evidence, read [Drupal test checks](references/core-testing.md).
For a UI change, verify the affected page with the relevant user role.
Use `drupal-intent-testing` if that skill is available and the task needs browser verification.

Run `package` after the local change is ready:

```bash
python3 "$DCF_ROOT/scripts/contribute_fix.py" package \
  --root /path/to/site \
  --changed-path /path/to/site/web/modules/contrib/PROJECT \
  --keywords "ERROR_OR_BEHAVIOR" \
  --test-steps "SETUP" "ACTION" "BEFORE_RESULT" "AFTER_RESULT" \
  --out .drupal-contribute-fix
```

Replace every placeholder with issue-specific information.
Use `--issue ISSUE_ID` for a known issue.
Check the selected baseline before you use the diff.

If an existing-fix stop is incorrect, record the comparison before you use `--force`.
If a security finding appears, stop public contribution work.
Follow the [Drupal security reporting process](https://www.drupal.org/docs/develop/issues/issue-procedures-and-etiquette/reporting-a-security-issue).

## Validate the result

Inspect `REPORT.md` for failures and skipped checks.
PHP syntax checks and coding-standard checks do not replace application tests.
Run the checks that prove the changed behavior.
Record each exact command, exit status, and observed result.
Never report a test as passed unless you ran it and retained its result.

The `test` command writes a draft from supplied test evidence. It does not execute tests.
It does not grant RTBC status or change issue status.
Use its `--help` output for the required evidence fields.

`--offline` uses cached Drupal.org data.
Package operations cannot create a new baseline checkout offline.
Keep this limit clear when a user requests work without network access.

## Give the user a handoff

Keep `.drupal-contribute-fix/` evidence until the work is complete.
Provide the exact paths to the report, comment draft, workflow note, and local diff, when present.
State what passed, failed, or did not run.
State the next action and any unresolved blocker.

Use MRs for new contributions unless the maintainer requests another process.
The Python tool creates local files only. It does not post comments, create issues, or push commits.
Respect the user's existing authorization for separate contribution actions.

Use `drupalorg-cli` for issue-fork and MR operations when it is available.
Check the installed command help before use.
See [Setup scripts](scripts/README.md) for optional environment helpers.
For historical patches, read [Local diffs and historical patches](references/patch-conventions.md).

See [README.md](README.md) for command options, output files, and exit codes.
