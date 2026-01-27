# Drupal.org Issue Status Codes

When analyzing API responses (`field_issue_status`), use this logic map.

## Status Codes with Agent Logic

| Code | Label | Agent Logic |
|:-----|:------|:------------|
| **1** | Active | **Proceed.** Open bug. Check for existing patches in comments. |
| **2** | Fixed | **Stop.** Issue is resolved. Advise user to upgrade module version. |
| **3** | Closed (duplicate) | **Stop.** Find the canonical issue and check its status. |
| **4** | Postponed | **Check.** Read last comment to see why (may be waiting on Core fix). |
| **5** | Closed (won't fix) | **Stop.** Issue intentionally not addressed. Don't submit patches. |
| **6** | Closed (works as designed) | **Stop.** Reported behavior is intentional. |
| **7** | Closed (fixed) | **Stop.** Already fixed. Advise user to upgrade. |
| **8** | Needs review | **Caution.** Fix exists. You MUST compare local fix to existing MR/Patch. |
| **13** | Needs work | **Proceed.** Existing fixes failed review. Your patch might address feedback. |
| **14** | RTBC | **Stop.** Ready to be committed. Do not add noise unless RTBC patch is broken. |
| **15** | Patch (to be ported) | **Check.** Patch exists but needs porting. May need version-specific patch. |
| **16** | Postponed (needs info) | **Check.** Waiting for clarification. May need more details, not code. |
| **17** | Closed (outdated) | **Stop.** Issue no longer relevant. |
| **18** | Closed (cannot reproduce) | **Check.** Provide reproduction steps if you can reproduce. |

## Agent Decision Matrix by Status

### Generate Patch (Proceed)
- **1 (Active)**: Open issue, patches welcome
- **13 (Needs work)**: Previous attempts failed review, try again

### Compare First (Caution)
- **8 (Needs review)**: **MUST compare** local fix to existing MR/patch before proceeding
- **15 (Patch to be ported)**: Check if your version needs the port

### Do Not Generate Patch (Stop)
- **2 (Fixed)**: Already fixed
- **7 (Closed - fixed)**: Already fixed and closed
- **14 (RTBC)**: About to be committed, don't add noise
- **3 (Duplicate)**: Wrong issue
- **5 (Won't fix)**: Intentionally rejected
- **6 (Works as designed)**: Not a bug
- **17 (Outdated)**: No longer relevant

### Human Decision Needed (Check)
- **4 (Postponed)**: May be blocked by something else
- **16 (Needs info)**: May need analysis, not code
- **18 (Cannot reproduce)**: Provide steps if reproducible

## Priority Codes

| Code | Label | Urgency |
|------|-------|---------|
| 400 | Critical | Blocks site operation, security issue |
| 300 | Major | Significant functionality broken |
| 200 | Normal | Standard bug or feature |
| 100 | Minor | Small improvement, edge case |

## API Usage

Query issues by status:
```
https://www.drupal.org/api-d7/node.json?type=project_issue&field_issue_status=8
```

Multiple statuses (comma-separated):
```
https://www.drupal.org/api-d7/node.json?type=project_issue&field_issue_status=1,8,13
```

Get issue with MR details:
```
https://www.drupal.org/api-d7/node/[nid].json?related_mrs=1
```

## References

- [Drupal.org API Documentation](https://www.drupal.org/drupalorg/docs/apis/rest-and-other-apis)
- [Issue Workflow](https://www.drupal.org/docs/develop/issues/issue-procedures-and-etiquette/issue-status-meanings)
