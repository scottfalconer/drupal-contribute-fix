# Drupal Core Testing Guide

**This guide applies to Drupal core contributions only.** Contrib modules don't require tests, though they're encouraged.

**Philosophy:** "When making a patch to fix a bug, make sure that the bug fix patch includes a test that fails without the code change and passes with the code change."

## Test Requirements for Core

All Drupal core patches/MRs MUST include:
1. **Test coverage** for the changes being made
2. **Passing tests** - all existing tests must continue to pass
3. **Updated tests** - if behavior changes, update existing tests to match

## Choosing the Right Test Type

| Test Type | Base Class | When to Use |
|-----------|------------|-------------|
| **Unit** | `Drupal\Tests\UnitTestCase` | Isolated PHP logic, all dependencies can be mocked |
| **Kernel** | `Drupal\KernelTests\KernelTestBase` | Need database/services but not browser |
| **Functional** | `Drupal\Tests\BrowserTestBase` | Need full Drupal + simulated browser |
| **FunctionalJavascript** | `Drupal\FunctionalJavascriptTests\WebDriverTestBase` | Need JavaScript execution |

**Decision tree:**
1. Can all dependencies be mocked? → **Unit test**
2. Need database/services but not browser? → **Kernel test**
3. Need to test page output/forms? → **Functional test**
4. Need JavaScript/Ajax behavior? → **FunctionalJavascript test**

**Prefer kernel tests over functional tests when possible** - they run significantly faster.

## Test File Locations

**For Drupal core:**
```
core/tests/Drupal/
├── Tests/                   # Unit tests
├── KernelTests/             # Kernel tests
├── FunctionalTests/         # Browser tests
└── FunctionalJavascriptTests/  # JS tests
```

**For contrib modules (if adding tests):**
```
modules/contrib/your_module/tests/src/
├── Unit/                    # Unit tests
├── Kernel/                  # Kernel tests
├── Functional/              # Browser tests
└── FunctionalJavascript/    # JS tests
```

## Test Class Structure

**Required elements:**
- PHPDoc comment describing the test
- `#[Group('group_name')]` attribute (or `@group` annotation)
- `#[CoversClass(ClassName::class)]` for unit tests
- Test methods prefixed with `test`

## Unit Test Example

```php
<?php

declare(strict_types=1);

namespace Drupal\Tests\your_module\Unit;

use Drupal\Tests\UnitTestCase;
use Drupal\your_module\MyClass;

/**
 * Tests MyClass functionality.
 *
 * @group your_module
 * @coversDefaultClass \Drupal\your_module\MyClass
 */
class MyClassTest extends UnitTestCase {

  /**
   * Tests the calculate method.
   *
   * @covers ::calculate
   */
  public function testCalculate(): void {
    $myClass = new MyClass();
    $this->assertEquals(4, $myClass->calculate(2, 2));
  }

}
```

## Kernel Test Example

```php
<?php

declare(strict_types=1);

namespace Drupal\Tests\your_module\Kernel;

use Drupal\KernelTests\KernelTestBase;

/**
 * Tests MyService functionality.
 *
 * @group your_module
 */
class MyServiceTest extends KernelTestBase {

  /**
   * Modules to enable.
   *
   * @var array
   */
  protected static $modules = ['your_module', 'system'];

  /**
   * {@inheritdoc}
   */
  protected function setUp(): void {
    parent::setUp();
    // Install schema if needed.
    $this->installSchema('system', ['sequences']);
    // Install config if needed.
    $this->installConfig(['your_module']);
  }

  /**
   * Tests the service method.
   */
  public function testServiceMethod(): void {
    $service = $this->container->get('your_module.my_service');
    $result = $service->doSomething();
    $this->assertNotEmpty($result);
  }

}
```

## Functional (Browser) Test Example

```php
<?php

declare(strict_types=1);

namespace Drupal\Tests\your_module\Functional;

use Drupal\Tests\BrowserTestBase;

/**
 * Tests the admin UI.
 *
 * @group your_module
 */
class AdminUiTest extends BrowserTestBase {

  /**
   * Modules to enable.
   *
   * @var array
   */
  protected static $modules = ['your_module', 'node'];

  /**
   * Default theme (required since Drupal 8.8).
   *
   * @var string
   */
  protected $defaultTheme = 'stark';

  /**
   * Tests the settings page.
   */
  public function testSettingsPage(): void {
    $account = $this->drupalCreateUser(['administer your_module']);
    $this->drupalLogin($account);

    $this->drupalGet('admin/config/your_module/settings');
    $this->assertSession()->statusCodeEquals(200);
    $this->assertSession()->pageTextContains('Settings');

    // Submit form.
    $this->submitForm([
      'setting_name' => 'new_value',
    ], 'Save configuration');

    $this->assertSession()->pageTextContains('Configuration saved.');
  }

}
```

## KernelTestBase Key Methods

```php
// Enable modules during test.
$this->enableModules(['module_name']);

// Install database schema.
$this->installSchema('module', ['table_name']);

// Install module's default config.
$this->installConfig(['module_name']);

// Install entity schema.
$this->installEntitySchema('node');

// Access services.
$service = $this->container->get('service.name');
```

## Common Assertions

**Session assertions (Functional tests):**
```php
$this->assertSession()->statusCodeEquals(200);
$this->assertSession()->pageTextContains('Expected text');
$this->assertSession()->pageTextNotContains('Unexpected');
$this->assertSession()->addressEquals('node/1');
$this->assertSession()->fieldExists('field_name');
$this->assertSession()->linkExists('Link text');
$this->assertSession()->elementExists('css', '.my-class');
```

**General PHPUnit assertions:**
```php
$this->assertEquals($expected, $actual);
$this->assertNotEquals($expected, $actual);
$this->assertTrue($condition);
$this->assertFalse($condition);
$this->assertNull($value);
$this->assertNotNull($value);
$this->assertEmpty($value);
$this->assertNotEmpty($value);
$this->assertCount(3, $array);
$this->assertArrayHasKey('key', $array);
$this->assertInstanceOf(MyClass::class, $object);
$this->assertStringContainsString('needle', $haystack);
```

## Running Tests Locally

**Environment variables required:**
```bash
export SIMPLETEST_DB="mysql://user:pass@localhost/drupal_test"
export SIMPLETEST_BASE_URL="http://localhost"
```

**DDEV configuration:**
```bash
export SIMPLETEST_DB="mysql://db:db@db/db"
export SIMPLETEST_BASE_URL="http://your-site.ddev.site"
```

**Running tests:**
```bash
# Run specific test file
./vendor/bin/phpunit -c core/phpunit.xml.dist path/to/Test.php

# Run specific test method
./vendor/bin/phpunit -c core/phpunit.xml.dist --filter testMethodName path/to/Test.php

# Run by group
./vendor/bin/phpunit -c core/phpunit.xml.dist --group your_module

# Run all unit tests
./vendor/bin/phpunit -c core/phpunit.xml.dist --testsuite unit
```

**With DDEV:**
```bash
ddev exec ./vendor/bin/phpunit -c web/core/phpunit.xml.dist web/core/tests/path/to/Test.php
```

**With Lando:**
```bash
lando ssh -c "cd /app/web && ../vendor/bin/phpunit -c core/phpunit.xml.dist core/tests/path/to/Test.php"
```

## Test Coverage Checklist

Before submitting a core contribution:

- [ ] Test fails without the fix, passes with the fix
- [ ] Test covers the specific bug/feature, not unrelated code
- [ ] Test uses the simplest appropriate test type (Unit > Kernel > Functional)
- [ ] Test includes `@group` annotation matching module/component name
- [ ] Test method names clearly describe what's being tested
- [ ] All existing tests still pass
- [ ] Test includes `@see` reference to the issue URL in docblock
