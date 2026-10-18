# Drupal.org issue status codes

The API uses `field_issue_status` for issue status.
The table matches the labels in `lib/drupalorg_api.py`.
Read the issue and its recent comments before you choose an action.

| Code | Label | Review action |
| --- | --- | --- |
| `1` | Active | Check for related work. |
| `2` | Fixed | Verify the commit and release. |
| `3` | Closed (duplicate) | Follow the canonical issue. |
| `4` | Postponed | Identify the blocker. |
| `5` | Closed (won't fix) | Read the decision. |
| `6` | Closed (works as designed) | Check the intended behavior. |
| `7` | Closed (fixed) | Verify the applicable release. |
| `8` | Needs review | Review the proposed change. |
| `13` | Needs work | Address the review findings. |
| `14` | Reviewed & tested by the community | Inspect the review evidence. |
| `15` | Patch (to be ported) | Check the required target branch. |
| `16` | Postponed (maintainer needs more info) | Supply the missing evidence. |
| `17` | Closed (outdated) | Check a supported version. |
| `18` | Closed (cannot reproduce) | Verify the reproduction steps. |

See the official [issue status definitions](https://www.drupal.org/docs/develop/issues/fields-and-other-parts-of-an-issue/issue-status-field).

## Interpret tool output

A candidate with fixed status, an MR, or a patch can cause exit code `10`.
This is a request to review existing work. It is not proof that the local bug is resolved.

Issue status does not prove release availability or test coverage.
Verify the relevant code and behavior before you recommend an upgrade or stop local work.
Do not set RTBC solely because a test passes.

## Priority codes

| Code | Label |
| --- | --- |
| `400` | Critical |
| `300` | Major |
| `200` | Normal |
| `100` | Minor |

Priority is separate from status.
Use the project's [priority guidance](https://www.drupal.org/docs/develop/issues/fields-and-other-parts-of-an-issue/issue-priority-field).
