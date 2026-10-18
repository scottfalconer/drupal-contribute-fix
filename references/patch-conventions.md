# Local diffs and historical patches

Use a merge request (MR) for new contribution work unless the maintainer requests another process.
See the [Drupal MR workflow](https://www.drupal.org/docs/develop/git/using-gitlab-to-contribute-to-drupal/introduction).

The `package` command creates a `.diff` file for local review.
It does not submit that file to Drupal.org.

## Check the generated diff

The generated filename has this form:

```text
project-description-issue.diff
project-description-new.diff
```

The CLI uses `new` when no issue number is selected.
It uses lowercase words and hyphens in the description.
It does not assign an issue comment number.

Paths must be relative to the upstream repository root.
For a contributed module, expect paths such as `src/Example.php`.
For Drupal core, expect paths such as `core/lib/Drupal/Example.php`.
Do not include the site's `web/` or `docroot/` prefix.

The packager removes known distribution metadata from the diff.
It reduces diff context when the change includes an `.info.yml` file.
Inspect the result for missing changes and unrelated files.

Deletion detection is off by default.
A Composer distribution can omit tests or other upstream files.
Use `--detect-deletions` only when you can distinguish an intentional deletion from an omitted distribution file.

## Check application

Use a clean checkout of the intended target ref.
Check the patch before you apply it:

```bash
git apply --check /absolute/path/to/change.diff
```

Then apply it:

```bash
git apply /absolute/path/to/change.diff
```

Inspect the resulting diff.
Run the tests that prove the changed behavior.
A successful `git apply --check` is not a test of Drupal behavior.

## Create a diff manually

For changes already staged in Git:

```bash
git diff --cached --binary > /absolute/path/to/change.diff
```

For tracked changes that are not staged:

```bash
git diff --binary > /absolute/path/to/change.diff
```

Untracked files are absent from the second command's output.
Stage the intended new files before you use the first command.
Review the file list before you create the diff.

## Reroll a historical patch

Use `reroll` when a maintainer requests a patch for another branch.
The command downloads the original patch and checks it against the selected Git ref.
It attempts a three-way application when a direct application fails.
It saves a rerolled patch if that attempt succeeds.
It reports conflicts when manual work is needed.

Review `REROLL_COMMENT.md` and any generated patch.
Replace draft placeholders with actual findings.
Run the required tests before you submit the result.

If reviewers need a comparison between two patches, use `interdiff` when available:

```bash
interdiff old.patch new.patch > interdiff.txt
```

Inspect this comparison before you share it.
Keep the original and updated patch names in the review notes.
