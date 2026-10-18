# drupal-contribute-fix

Find existing Drupal fixes. Prepare local contribution files when a new fix is needed.

`drupal-contribute-fix` is a Python command-line tool and an agent skill.
It searches Drupal.org issues before it packages a local code change.
It helps contributors choose an existing merge request (MR), verify a released fix, or prepare new work.

The tool creates local files for review. It does not post comments, create issues, push commits, or change issue status.

## Choose a resolution

| Finding | Next action |
| --- | --- |
| A matching MR or patch exists | Review the change. Test it in the affected environment. |
| A matching issue is fixed | Check the commit and release. Verify that the release fixes your case before an upgrade. |
| No matching fix is confirmed | Reproduce the bug. Make a focused change. Prepare contribution files. |
| The change may disclose a security vulnerability | Stop public contribution work. Use the [Drupal security reporting process](https://www.drupal.org/docs/develop/issues/issue-procedures-and-etiquette/reporting-a-security-issue). |

Search results are candidates. The matching algorithm cannot confirm that an issue fixes your bug.
Check the affected file, function, target branch, and behavior before you accept a match.
The tool does not check development branches or upgrade dependencies automatically.

## Requirements

- Python 3.8 or later. The Python tool uses only the standard library.
- Git for `package` and `reroll`.
- Network access for Drupal.org searches and upstream Git checkouts.
- PHP for syntax checks.
- PHP_CodeSniffer with the Drupal standard for coding-standard checks.

DDEV and `drupalorg-cli` are optional. See [Setup scripts](scripts/README.md) for their requirements and installation steps.

## Start here

Clone the repository:

```bash
git clone https://github.com/scottfalconer/drupal-contribute-fix.git
cd drupal-contribute-fix
```

Check the command options:

```bash
python3 scripts/contribute_fix.py --help
```

Search before you change code:

```bash
python3 scripts/contribute_fix.py preflight \
  --project metatag \
  --keywords "TypeError MetatagManager build" \
  --paths src/MetatagManager.php \
  --out .drupal-contribute-fix
```

This example searches the `metatag` project. Replace its project, keywords, and path with values from your bug report.
Read the candidate issues and their MRs. Confirm the match before you use a proposed fix.

For agent use, load [SKILL.md](SKILL.md) with your agent's skill installation method.
Keep the complete repository together. The entry file uses `scripts/`, `lib/`, and `references/`.

## Commands

| Command | Purpose |
| --- | --- |
| `preflight` | Search issues. Save candidate metadata. |
| `package` | Compare local code with an upstream baseline. Create a local diff and report. |
| `test` | Write a comment draft from test evidence that you supply. It does not execute tests. |
| `reroll` | Try to apply a historical patch to another Git ref. Save a reroll if possible. |

Use `python3 scripts/contribute_fix.py COMMAND --help` for each command's options.

### Prepare a local change

Use the project directory as `--changed-path`. For Drupal core, use the site's `core` directory.
Use the directory that contains the site's `composer.lock` as `--root`.

```bash
python3 scripts/contribute_fix.py package \
  --root /path/to/site \
  --changed-path /path/to/site/web/modules/contrib/metatag \
  --keywords "TypeError MetatagManager build" \
  --description missing-canonical-link \
  --test-steps \
    "Create an entity without a canonical link template" \
    "Trigger metatag generation for the entity" \
    "Before the fix: record the exception" \
    "After the fix: confirm the expected metadata output" \
  --out .drupal-contribute-fix
```

Replace the example steps with the exact procedure for your issue.
Test steps describe a procedure. They are not evidence that you executed it.

The command searches for existing work before it creates a diff.
Use `--issue ISSUE_ID` when you have already identified the issue.
Use `--upstream-ref REF` to select an explicit baseline.
Check the selected baseline before you use the diff.

Use `--force` only after you inspect an existing fix and document why another local diff is needed.
It overrides the existing-fix stop. It does not establish that your change is correct.

### Record completed tests

Run the relevant tests separately. Save the command, environment, output, and exit status.
Then use `test` to prepare a local comment draft.

For example, after a targeted test passes, replace the example values with your evidence:

```bash
python3 scripts/contribute_fix.py test \
  --issue 1234567 \
  --mr 42 \
  --tested-on "Drupal branch and commit; PHP version; database version" \
  --result pass \
  --test-command "the exact command you ran" \
  --test-output "the observed output and exit status" \
  --out .drupal-contribute-fix
```

Use `--patch FILENAME` instead of `--mr` for a historical patch.
Use `fail` or `partial` when the evidence does not support `pass`.
The command records your supplied result. It cannot verify the evidence or grant RTBC status.
Review `TEST_COMMENT.md` before you use it.

### Reroll a historical patch

Use this command when the maintainer requests a patch workflow.
Use the issue's actual patch URL and target ref.

```bash
python3 scripts/contribute_fix.py reroll \
  --project PROJECT \
  --issue ISSUE_ID \
  --patch-url "https://www.drupal.org/files/issues/PATCH_FILE.patch" \
  --target-ref TARGET_REF \
  --out .drupal-contribute-fix
```

An application check proves only that Git can apply the patch.
Run the relevant tests before you report that the fix works.
See [Local diffs and historical patches](references/patch-conventions.md).

## Output files

`preflight` writes `UPSTREAM_CANDIDATES.json` in the output directory.
If an installed `drupal-issue-queue` helper is available, an online search can also save an issue summary.

`package` writes an issue directory:

```text
.drupal-contribute-fix/
├── UPSTREAM_CANDIDATES.json
└── 1234567-short-description/
    ├── REPORT.md
    ├── ISSUE_COMMENT.md
    ├── WORKFLOW.md
    └── diffs/
        └── project-description-1234567.diff
```

The directory starts with `unfiled-` when no issue is selected.
A stopped package operation can produce reports without a diff.
Keep these files until the contribution work is complete.
Keep local evidence outside the upstream MR diff.

If `ci/*.log` files exist in the issue directory, the report writer can create a local CI summary template.
Complete that template with actual commands and results. Its presence does not prove that CI checks passed.

See the [sample report](examples/sample-report.md) for the required evidence.

## Validation and limits

`package` attempts PHP syntax checks and PHP_CodeSniffer checks unless you use `--skip-validation`.
Unavailable tools are reported as not run.
A failed executed check returns exit code `40`; generated files remain available for review.
A successful package operation does not mean that application tests passed.

Run PHPUnit, PHPStan, browser checks, and project-specific CI checks separately as needed.
For a visible behavior change, verify the affected page with the relevant user role.
The optional [drupal-intent-testing skill](https://github.com/scottfalconer/drupal-intent-testing) can help with this check.

Other limits:

- Searches inspect a bounded set of issues. `--max-issues` defaults to `200`.
- `--offline` uses cached Drupal.org responses. Missing cache data causes an error.
- Offline package operations stop before a Git checkout. No offline baseline cache is provided.
- Security and code-pattern checks use heuristics. They are not a security audit or a complete code review.
- Deletion detection is off by default. Composer distributions can omit files that exist upstream.
- Exit code `20` is reserved. Automatic release or development-branch verification is not implemented.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | The requested operation completed. Inspect its report for check scope and skipped checks. |
| `10` | A candidate has existing work or fixed status. Verify its relevance before you stop. |
| `20` | Reserved for a future upstream-version check. |
| `30` | The generated change needs further review, or a reroll has unresolved conflicts. |
| `40` | The operation or an executed validation check failed. |
| `50` | The security heuristic stopped packaging. Review the finding privately. |

Invalid command arguments use argparse's exit code `2`.

## Continue with an MR

Use the project's contribution instructions to select the target branch and issue fork.
Keep generated `.diff` files for local review.
Use an MR for new work unless the maintainer requests another process.

The optional `drupalorg-cli` can inspect issues, forks, MRs, and pipeline results.
Check its installed version and command help before use.
See [Setup scripts](scripts/README.md) for the workspace setup helpers.

Before submission:

1. Inspect the complete diff.
2. Add or update regression tests for the bug.
3. Run the relevant checks.
4. Record exact commands and results.
5. Replace every draft placeholder with verified information.
6. Submit only the changes and evidence needed for the issue.

GitLab pipeline jobs depend on the project's configuration.
Do not assume that a green pipeline covers checks that the project does not run.

## Contribute to this tool

Read [CONTRIBUTING.md](CONTRIBUTING.md) for development checks and the documentation policy.
All maintained documentation and generated text use ASD-STE100 as the writing standard.
The policy explains the review requirements and the limits of a compliance claim.

License: [GPL-2.0-or-later](LICENSE).
