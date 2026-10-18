# Drupal test checks

Use this guide for changes to Drupal core or a contributed project.
Follow the target branch's test configuration and contribution instructions.
Add a regression test that fails for the original bug and passes with the fix.

## Select a test type

| Type | Use | Base class |
| --- | --- | --- |
| Unit | Test isolated logic with few dependencies. | `Drupal\Tests\UnitTestCase` |
| Kernel | Test services, entities, or database behavior with a Drupal kernel. | `Drupal\KernelTests\KernelTestBase` |
| Functional | Test behavior in a complete Drupal installation. | `Drupal\Tests\BrowserTestBase` |
| FunctionalJavascript | Test browser behavior that needs JavaScript. | `Drupal\FunctionalJavascriptTests\WebDriverTestBase` |

See Drupal's [types of tests](https://www.drupal.org/docs/develop/automated-testing/types-of-tests) for the supported frameworks.

Use the smallest test that proves the required behavior.
Use existing tests in the affected component as examples.
Match the target branch's metadata, namespace, and fixture conventions.
Do not copy test syntax from a different Drupal or PHPUnit version without verification.

## Prepare the environment

1. Install the development dependencies specified by the target project.
2. Read its PHPUnit configuration.
3. Configure the required database and site URL for integration tests.
4. Configure a WebDriver service if the test needs JavaScript.
5. Check that the test runner can find the selected test.

Use the project's documented command.
For a site with a `web/` document root, a targeted command can have this form:

```bash
vendor/bin/phpunit \
  -c web/core/phpunit.xml.dist \
  web/modules/contrib/PROJECT/tests/src/Kernel/ExampleTest.php
```

Replace the path and configuration with values from your checkout.
Run the command inside DDEV if the dependencies and database are in its container.

## Prove the change

1. Run the regression test against the original code.
2. Confirm that the failure matches the reported bug.
3. Run the same test with the fix.
4. Run related tests for behavior that could change.
5. Run the project's coding-standard and static-analysis checks.

If the bug affects a visible page, verify the affected task in a browser.
Use the relevant user role and permissions.
Record the action, expected result, observed result, and tested commit.
A browser check supplements automated tests. It does not replace regression coverage.

## Keep evidence

Record each exact command, exit status, environment, and observed result.
Keep raw logs when they help a reviewer reproduce the result.
Use `Not run` when a check did not execute.
State the missing dependency or other blocker.

Store local CI logs under the issue's `ci/` directory when useful.
Complete any generated `LOCAL_CI_PARITY_YYYY-MM-DD.md` template with actual evidence.
Do not claim full CI parity from a subset of jobs.

The Python tool's `package` command runs limited validation.
Its `test` command only writes supplied evidence to a comment draft.
Neither command runs the Drupal test suite.

GitLab jobs depend on the project's pipeline configuration.
Check the current [Drupal GitLab CI guidance](https://www.drupal.org/docs/develop/git/using-gitlab-to-contribute-to-drupal/gitlab-ci) and the project's actual job results.
