# Code review patterns

Use these patterns to guide review. A pattern match does not prove that code is incorrect.
A missing warning does not prove that code is safe.

The tool uses regular expressions and file names to find possible problems.
Review the complete change and its context.

## Review the behavior

| Pattern | Review action |
| --- | --- |
| Cache disabled or broadly invalidated | Check cache tags, contexts, and invalidation. Preserve correct cache behavior. |
| Hardcoded entity IDs, paths, or host names | Check whether the value must vary by site or configuration. |
| Error suppression or an empty exception handler | Check the failure path. Preserve useful error information. |
| Direct database queries | Check parameter handling and whether the query needs entity access or lifecycle behavior. |
| Static service access in a service class | Check the surrounding dependency injection pattern. |
| An access check removed or bypassed | Verify the authorization requirement and affected roles. |
| Debug output | Remove temporary output before contribution. |
| Unrelated formatting or refactoring | Separate changes that are not needed for the fix. |

These operations can be valid in some contexts.
Explain the reason and add a test when the reason is not clear from the code.
Do not replace review with a universal ban on an API.

## Keep the fix focused

1. Identify the condition that causes the failure.
2. Check the relevant API contract.
3. Correct that condition with the smallest complete change.
4. Preserve valid existing behavior.
5. Add a regression test.

A null check is useful only when null is a valid input or expected absence.
A default value can hide missing data.
An early return can skip required cleanup or authorization.
Test the intended behavior instead of treating a code pattern as automatically safe.

## Handle a possible vulnerability

If the change reveals an access bypass, injection, or other vulnerability, stop public contribution work.
Keep the reproduction details private while you assess the finding.
Use the [Drupal security reporting process](https://www.drupal.org/docs/develop/issues/issue-procedures-and-etiquette/reporting-a-security-issue).

The tool's security result is a heuristic warning. It is not a security audit.
The `--force` option only overrides the existing-fix stop.
It does not waive security review or correct an unsafe change.
