# Drupal Patch Conventions

Reference for creating patches that follow Drupal community standards.

## Filename Format

Since we cannot predict the exact comment number at the time of generation, use `comment-next` or `do-not-test` as the placeholder.

**Standard Format:**
```
[project_machine_name]-[short_description]-[issue_id]-[placeholder].patch
```

### Examples
- `metatag-fix-null-pointer-3345678-comment-next.patch`
- `drupal-views-cache-bug-3123456-comment-next.patch`
- `token-entity-type-notice-3789012-do-not-test.patch`
- `webform-submission-handler-new-0.patch` (for issues not yet created)

### Naming Rules
- Use **lowercase** only
- Use **hyphens** to separate words (not underscores)
- Keep description **short** (2-4 words)
- Use `new` or `0` if no issue number exists yet
- Use `comment-next` when issue exists but comment number unknown
- Use `do-not-test` to skip automated testing on drupal.org

## Content Standards

### Root Relative Paths

Patches must be generated relative to the **project root**, not the site root.

```diff
# CORRECT: Relative to project root
diff --git a/src/Entity/Node.php b/src/Entity/Node.php

# INCORRECT: Includes site path
diff --git a/web/modules/contrib/metatag/src/Entity/Node.php ...
```

### Context Lines

Use standard git diff (3 lines of context) unless working with `.info.yml` files.

```bash
# Standard (3 lines context)
git diff > patch.patch

# Reduced context for .info.yml files (prevents conflicts)
git diff -U1 > patch.patch
```

## Creating Patches

### From Git (Recommended)

```bash
# Stage your changes
git add -A

# For new files, use intent-to-add
git add -N path/to/new/file.php

# Generate patch
git diff > project-description-ISSUE-comment-next.patch
```

### With Binary Files

If your patch includes binary files (images, fonts, etc.):
```bash
git diff --binary > project-description-ISSUE-comment-next.patch
```

### For .info.yml Files

Drupal's packaging system can cause context conflicts with `.info.yml` files:
```bash
git diff -U1 > project-description-ISSUE-comment-next.patch
```

## Applying Patches

### Verify Patch Applies

```bash
# Dry run - checks without applying
git apply --check path/to/patch.patch
```

### Apply Patch

```bash
# Standard apply
git apply path/to/patch.patch

# With 3-way merge (if conflicts)
git apply --3way path/to/patch.patch
```

## Interdiffs

When updating an existing patch, provide an interdiff showing what changed:

```bash
# Generate interdiff between old and new patch
interdiff old.patch new.patch > interdiff-OLDCOMMENT-NEWCOMMENT.txt
```

The interdiff helps reviewers quickly see what changed between versions.

## Patch Scope Guidelines

| Files Changed | Lines Changed | Recommendation |
|---------------|---------------|----------------|
| 1-3 files | < 100 lines | Ideal for contribution |
| 4-5 files | 100-200 lines | Acceptable, consider splitting |
| 6+ files | 200+ lines | Should probably be split |
| Any | 500+ lines | Definitely needs splitting |

## Best Practices

### DO
- Keep patches focused on **one issue**
- Include **only necessary changes**
- Test that patch applies to **clean checkout**
- Follow **Drupal coding standards**
- Update any **related tests**
- Include **test coverage** for bug fixes

### DON'T
- Include unrelated code style changes
- Add debugging code (`kint()`, `dd()`, `var_dump()`)
- Include environment-specific changes
- Modify `composer.lock`
- Include merge commits
- Mix bug fixes with new features

## MR vs Patch Workflow

As of 2024+, Drupal prefers **Merge Requests** over patches for many projects.

| Workflow | When to Use |
|----------|-------------|
| **MR** | Issue already has MR, project uses GitLab workflow |
| **Patch** | Issue is patch-based, quick fix, MR not practical |

If an issue has an existing MR, **review/update that MR** rather than posting a competing patch.

## References

- [Making a Patch](https://www.drupal.org/docs/develop/git/using-git-to-contribute-to-drupal/working-with-patches/making-a-patch)
- [Applying a Patch](https://www.drupal.org/docs/develop/git/using-git-to-contribute-to-drupal/working-with-patches/applying-a-patch)
- [GitLab MR Workflow](https://www.drupal.org/docs/develop/git/using-gitlab-to-contribute-to-drupal)
