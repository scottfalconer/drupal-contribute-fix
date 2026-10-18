# Command and setup scripts

Run the Python tool directly from a repository checkout:

```bash
python3 scripts/contribute_fix.py --help
```

See the [README](../README.md#commands) for its commands and limits.

The shell scripts are optional environment helpers.
They can create directories, install dependencies, or restart DDEV.
Read the relevant section before you run a setup command.
All four scripts support `--help` without setup changes.

## Set the script path

Set `DCF_ROOT` to the absolute path of this repository:

```bash
DCF_ROOT=/absolute/path/to/drupal-contribute-fix
```

Run workspace commands from the directory specified below.
Do not use the tool's repository as the target Drupal project.

## Create an issue-fork workspace

Requirements: Git, network access, an existing issue fork, and an existing branch in that fork.

Use the exact project machine name, issue number, and branch name from Drupal.org.
Run this command from the parent directory for the new workspace:

```bash
bash "$DCF_ROOT/scripts/setup-mr-workspace.sh" PROJECT ISSUE_ID BRANCH
```

The script creates a new `PROJECT/` directory.
It refuses to use an existing destination.
It adds the upstream project as `origin`.
It adds the issue fork as `PROJECT-ISSUE_ID`.
It fetches the specified branch and creates a local branch that tracks it.
Both remotes use HTTPS.

The script does not create an issue fork or obtain push access.
It does not choose a branch automatically.
Check the issue page if the requested branch is absent.

## Configure a DDEV contrib project

Requirements: DDEV, a working container provider, network access, and a configured DDEV project.

Run this command from the target project's root, where `.ddev/config.yaml` exists:

```bash
bash "$DCF_ROOT/scripts/setup-ddev-contrib.sh"
```

The script executes these commands in order:

```bash
ddev add-on get ddev/ddev-drupal-contrib
ddev restart
ddev poser
ddev symlink-project
```

These commands install the official contrib add-on and prepare the project dependencies.
They change local project files and restart the DDEV environment.
Review `git status` after setup.
Keep generated environment files outside the contribution diff unless the project requires them.

Use the [official add-on instructions](https://github.com/ddev/ddev-drupal-contrib) to create or adjust the DDEV configuration.

## Install drupalorg-cli

Requirements: PHP 8.1 or later, Composer, and network access.
The selected CLI version can require a newer PHP version.

```bash
bash "$DCF_ROOT/scripts/setup-drupalorg-cli.sh"
```

The script runs this command:

```bash
composer global require --no-interaction --no-plugins --no-scripts mglaman/drupalorg-cli
```

This installs or updates the CLI in your global Composer project.
Composer plugins and scripts are disabled for these commands.
The script does not change your plugin policy.
It then checks the installed binary with `--version`.
If needed, it prints the directory to add to your shell's `PATH`.
It does not change your shell configuration.

Read the installed command help before an issue or MR operation:

```bash
drupalorg --help
```

Use the [drupalorg-cli documentation](https://github.com/mglaman/drupalorg-cli) for authentication and command details.

## Run selected local checks

Requirements: a configured DDEV project with `ddev phpstan` and `ddev phpcs` commands.

Run this command from the DDEV project root:

```bash
bash "$DCF_ROOT/scripts/run-local-ci.sh"
```

The script runs PHPStan and PHP_CodeSniffer.
It attempts both checks even if one fails.
A failed or unavailable check produces a nonzero exit status.

To include an existing `ddev cspell` command:

```bash
bash "$DCF_ROOT/scripts/run-local-ci.sh" --cspell
```

The script does not install cspell.
If `--cspell` is selected and the command is unavailable, the check fails.

These checks do not run PHPUnit or browser tests.
They do not establish full GitLab CI parity.
Run the project's tests and review its pipeline separately.

## Record results

Save each exact command and exit status with the issue evidence.
Record which checks passed, failed, or did not run.
Do not describe setup success as evidence that a Drupal bug is fixed.
