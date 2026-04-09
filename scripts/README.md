# Provisioning Scripts

This directory contains provisioning scripts to help set up a consistent development environment for contributing to Drupal contrib modules.

## Overview

These scripts automate the workflow described in [this GitHub comment](https://github.com/ddev/ddev-drupal-contrib/pull/55#issuecomment-4171026900) for working on Drupal contrib merge requests and ensuring local CI parity with Drupal's GitLab CI.

## Scripts

### 1. `setup-mr-workspace.sh`

Sets up a workspace for working on an existing Drupal contrib merge request.

**Usage:**
```bash
./scripts/setup-mr-workspace.sh <module_name> <issue_id> <branch_name>
```

**Example:**
```bash
./scripts/setup-mr-workspace.sh recaptcha_v3 3580901 '3580901-pass-gitlab-ci'
```

**What it does:**
- Clones the module from drupalcode.org
- Adds the issue fork remote
- Lists available branches with last commit times
- Validates the specified branch exists
- Checks out the MR branch
- Provides helpful error messages if branch not found

### 2. `setup-ddev-contrib.sh`

Installs and configures ddev-drupal-contrib addon.

**Usage:**
```bash
cd <module_directory>
../scripts/setup-ddev-contrib.sh
```

**What it does:**
- Installs the ddev-drupal-contrib addon
- Restarts DDEV to apply changes
- Sets up git excludes for DDEV and generated files
- Provides access to commands like `ddev phpstan`, `ddev phpcs`, `ddev phpcbf`

**Requirements:**
- Must be run from a DDEV project directory

### 3. `setup-ddev-cspell.sh`

Installs the `ddev cspell` command for spell checking.

**Usage:**
```bash
cd <module_directory>
../scripts/setup-ddev-cspell.sh
```

**What it does:**
- Downloads the cspell command from the custom fork
- Installs Node dependencies in Drupal core
- Supports both npm and Yarn 4+ PnP

**Requirements:**
- Must be run from a DDEV project directory
- Drupal core must be installed at `web/core`

**Note:** This uses a custom fork with fixes for Yarn 4+ PnP support: https://github.com/jameswilson/ddev-drupal-contrib/tree/cspell

### 4. `setup-drupalorg-cli.sh`

Installs drupalorg-cli for Drupal.org issue and merge request management.

**Usage:**
```bash
./scripts/setup-drupalorg-cli.sh
```

**What it does:**
- Checks PHP version (requires 8.1+)
- Checks for Composer
- Installs drupalorg-cli globally via Composer
- Verifies PATH configuration
- Displays common commands

**Requirements:**
- PHP 8.1 or higher
- Composer

**Note:** This is a global installation, not project-specific.

### 5. `run-local-ci.sh`

Runs all local CI checks that mirror Drupal GitLab CI.

**Usage:**
```bash
cd <module_directory>
../scripts/run-local-ci.sh
```

**What it does:**
- Runs PHPStan (static analysis)
- Runs PHPCS (coding standards)
- Runs CSpell (spell checking)
- Provides a summary of results and suggested fixes

**Requirements:**
- Must be run from a DDEV project directory
- `setup-ddev-contrib.sh` must have been run first
- `setup-ddev-cspell.sh` must have been run first (for cspell)

## Complete Workflow

Here's the complete workflow for working on a Drupal contrib merge request:

```bash
# 1. Set up the workspace
./scripts/setup-mr-workspace.sh recaptcha_v3 3580901 '3580901-pass-gitlab-ci'

# 2. Initialize DDEV
cd recaptcha_v3
ddev config --project-type=drupal --docroot=web
ddev start

# 3. Set up development tools
../scripts/setup-ddev-contrib.sh
../scripts/setup-ddev-cspell.sh

# 4. (Optional) Install drupalorg-cli for issue/MR management
../scripts/setup-drupalorg-cli.sh

# 5. Make your changes
# Edit files...

# 6. Run local CI checks
../scripts/run-local-ci.sh

# 7. Fix any issues
ddev phpcbf  # Auto-fix coding standards
# Fix other issues manually

# 8. Run CI checks again
../scripts/run-local-ci.sh

# 9. Commit and push
git add .
git commit -m "Issue #3580901: Fix description"
git push
```

## Integration with drupalorg-cli

These scripts complement the `drupalorg-cli` tool mentioned in the main skill documentation. While `drupalorg-cli` handles issue/MR metadata and status checking, these scripts handle the local development environment setup and CI parity.

**Recommended combined workflow:**

```bash
# (Optional) Install drupalorg-cli if not already installed
./scripts/setup-drupalorg-cli.sh

# Use drupalorg-cli to inspect the issue/MR
drupalorg issue:show 3580901 --format=llm
drupalorg mr:list 3580901 --format=llm

# Use these scripts to set up and test
./scripts/setup-mr-workspace.sh recaptcha_v3 3580901 'branch-name'
cd recaptcha_v3
ddev config --project-type=drupal --docroot=web && ddev start
../scripts/setup-ddev-contrib.sh
../scripts/setup-ddev-cspell.sh
../scripts/run-local-ci.sh

# Use drupalorg-cli to monitor CI pipeline
drupalorg mr:status 3580901 <mr-iid> --format=llm
drupalorg mr:logs 3580901 <mr-iid>
```

## Troubleshooting

### cspell command not found

Make sure you've run `setup-ddev-cspell.sh` first:
```bash
../scripts/setup-ddev-cspell.sh
```

### Drupal core not found

The `setup-ddev-cspell.sh` script expects Drupal core at `web/core`. If your project uses a different structure (e.g., `docroot/core`), you'll need to adjust the script or create a symlink.

### Git push permission denied

Make sure you have SSH access configured for git.drupal.org:
```bash
ssh-add ~/.ssh/id_rsa  # or your key file
```

### DDEV commands not working

Make sure DDEV is running:
```bash
ddev start
```

And that you've installed ddev-drupal-contrib:
```bash
ddev get ddev/ddev-drupal-contrib
ddev restart
```

### drupalorg-cli not found after installation

If `drupalorg` command is not found after running `setup-drupalorg-cli.sh`:

1. Check that Composer's global bin directory is in your PATH:
   ```bash
   composer global config bin-dir --absolute
   ```

2. Add it to your shell profile (~/.bashrc or ~/.zshrc):
   ```bash
   export PATH="$PATH:$HOME/.composer/vendor/bin"
   ```

3. Reload your shell:
   ```bash
   source ~/.bashrc  # or source ~/.zshrc
   ```

### PHP version too old for drupalorg-cli

drupalorg-cli requires PHP 8.1+. If you have an older version:

1. Install a newer PHP version (via Homebrew, apt, etc.)
2. Update your PATH to use the newer version
3. Run `setup-drupalorg-cli.sh` again

## Credits

These scripts are based on the workflow documented by [@jameswilson](https://github.com/jameswilson) in [this comment](https://github.com/ddev/ddev-drupal-contrib/pull/55#issuecomment-4171026900).

The cspell command comes from the [custom fork](https://github.com/jameswilson/ddev-drupal-contrib/tree/cspell) which includes fixes for Yarn 4+ PnP support.
