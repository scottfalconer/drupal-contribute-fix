# Example contribution report

This is an illustrative report template. It is not evidence from a real issue or test run.
Replace bracketed fields with verified information.
Keep incomplete fields visible until the missing work is complete.

## Problem

**Project:** [Project machine name]
**Issue:** [Verified issue URL, or no matching issue confirmed]
**Environment:** [Drupal, project, PHP, and database versions]
**Affected code:** [File and function]

[Describe the action that causes the failure.]
[Describe the expected behavior.]
[Describe the observed behavior.]

## Existing work

**Search command:** [Exact preflight command]
**Candidate:** [Issue and MR links]
**Review result:** [Confirmed match, rejected match, or unresolved]

[Explain which failure conditions and code paths match.]
[Record the inspected branch and commit.]
[State any limit in the search or verification.]

## Proposed change

[Explain the cause and the focused correction.]
[Explain how the regression test detects the original failure.]

**Local diff:** `.drupal-contribute-fix/unfiled-example/diffs/project-example-new.diff`
**Workflow:** [Existing MR, new MR, or analysis only]

## Reproduction procedure

1. [Set up the relevant configuration and content.]
2. [Perform the action that triggers the bug.]
3. [Record the original failure.]
4. [Apply the selected change.]
5. [Repeat the action.]
6. [Compare the observed result with the expected behavior.]

These steps are a proposed procedure until execution evidence is recorded below.

## Validation evidence

| Check | Command | Result | Evidence |
| --- | --- | --- | --- |
| Regression test before the fix | [Exact command] | Not run | [Blocker or log path] |
| Regression test after the fix | [Exact command] | Not run | [Blocker or log path] |
| Related tests | [Exact command] | Not run | [Blocker or log path] |
| PHP syntax | [Exact command] | Not run | [Blocker or log path] |
| Coding standards | [Exact command] | Not run | [Blocker or log path] |
| Browser check, if needed | [Procedure and user role] | Not run | [Blocker or evidence path] |

For each executed command, replace `Not run` with the exit status and observed result.
Do not infer test success from a generated report or diff.

## Next action

[State the next action, responsible person, and unresolved blocker.]
Review the complete diff and draft text before submission.
Keep local evidence outside the upstream contribution.
