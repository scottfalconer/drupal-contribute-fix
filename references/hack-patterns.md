# Hack vs. Fix Patterns

The agent must flag any patch containing these patterns as "Needs Human Review" or "Rejected."

## Forbidden Patterns (The "Hack" List)

These patterns should **block patch generation** or require explicit `--force`:

| Pattern | Example | Why It's Bad |
|---------|---------|--------------|
| **Core Hacking** | Modifying `/core/` files for a contrib module | Breaks upgrades, won't be accepted |
| **Disabling Caches** | `'#cache' => ['max-age' => 0]` | Destroys site performance |
| **Hardcoded IDs** | `if ($node->id() == 145)` | Won't work on other sites |
| **Suppressing Errors** | `@$entity->get(...)` | Hides real problems |
| **Empty Catch Blocks** | `catch (Exception $e) {}` | Swallows errors silently |
| **Direct SQL** | `\Drupal::database()->query(...)` | Should use EntityQuery |
| **DI Violations** | `\Drupal::service()` in injected class | Breaks testability |
| **Bypassing Access** | `->accessCheck(FALSE)` without justification | Security risk |

### Code Examples

```php
// FORBIDDEN: Disabling cache entirely
$build['#cache'] = ['max-age' => 0];

// FORBIDDEN: Broad cache invalidation
Cache::invalidateAll();

// FORBIDDEN: Swallowing exceptions
try {
  $result = $service->process();
} catch (\Exception $e) {
  // Ignore
}

// FORBIDDEN: Bypassing access
$nodes = $query->accessCheck(FALSE)->execute();

// FORBIDDEN: Hardcoded access
$build['#access'] = TRUE;
```

## Suspicious Patterns (Warn Only)

These patterns should trigger a **warning** but not block:

| Pattern | Example | Recommendation |
|---------|---------|----------------|
| **Commented Out Code** | `// old code` blocks | Remove before submission |
| **Debug Code** | `kint()`, `dd()`, `var_dump()` | Remove before submission |
| **Formatting Only** | Whitespace-only changes | Should be separate patch |
| **Environment Variables** | `getenv()`, `$_ENV` | May be environment-specific |
| **Hardcoded URLs** | `https://example.com` | Make configurable |

```php
// SUSPICIOUS: Debug statements (remove before patch)
var_dump($variable);
print_r($array);
dd($data);
\Drupal::logger('debug')->notice('here');
```

## Acceptable Patterns (Safe Fixes)

These patterns are generally safe and welcomed:

| Pattern | Example | Why It's Good |
|---------|---------|---------------|
| **Null Checks** | `if ($value !== NULL)` | Prevents TypeError |
| **Type Checks** | `instanceof` or `is_array()` | Guards against wrong types |
| **Null Coalescing** | `$value ?? $default` | Safe default handling |
| **Early Returns** | Guard clauses | Prevents nested errors |
| **Proper Logging** | `$this->logger->error(...)` | Traceable error handling |

```php
// GOOD: Null check before operation
if ($entity !== NULL && $entity->hasField('field_example')) {
  $value = $entity->get('field_example')->value;
}

// GOOD: Type guard
if ($items instanceof \Traversable) {
  foreach ($items as $item) { ... }
}

// GOOD: Null coalescing
$name = $entity->label() ?? t('Unknown');

// GOOD: Proper error handling
try {
  $result = $service->process();
} catch (\Exception $e) {
  $this->logger->error('Processing failed: @message', ['@message' => $e->getMessage()]);
  throw $e;
}
```

## Agent Decision Matrix

| Detection | Agent Action |
|-----------|--------------|
| Forbidden pattern in diff | **STOP** - Report as "Rejected: Contains [pattern]" |
| Suspicious pattern in diff | **WARN** - Include in report, suggest removal |
| Acceptable pattern only | **PROCEED** - Pattern is safe for contribution |

## Severity Levels

| Pattern | Severity | Action |
|---------|----------|--------|
| SQL injection risk | Critical | Do not submit |
| Access bypass | High | Needs strong justification |
| Cache disable | High | Usually better alternatives exist |
| Debug code | High | Must remove before submission |
| Hardcoded values | Medium | Make configurable |
| Exception swallow | Medium | Add proper handling |
| Commented code | Low | Remove for cleaner patch |
