"""
Code validation for patch quality assurance.

Runs PHP lint, PHPCS, and other checks on changed files.
"""

import os
import subprocess
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation check."""
    tool: str
    command: str
    passed: bool
    output: str
    not_run_reason: Optional[str] = None


def find_executable(name: str) -> Optional[str]:
    """Find an executable in PATH."""
    return shutil.which(name)


def run_php_lint(file_paths: List[Path]) -> ValidationResult:
    """
    Run PHP syntax check on files.

    Args:
        file_paths: List of PHP file paths

    Returns:
        ValidationResult
    """
    php_path = find_executable("php")
    if not php_path:
        return ValidationResult(
            tool="PHP Lint",
            command="php -l",
            passed=False,
            output="",
            not_run_reason="PHP not found in PATH",
        )

    php_files = [p for p in file_paths if str(p).endswith(".php")]
    if not php_files:
        return ValidationResult(
            tool="PHP Lint",
            command="php -l",
            passed=True,
            output="No PHP files to check",
            not_run_reason=None,
        )

    errors = []
    checked = 0

    for php_file in php_files:
        if not php_file.exists():
            continue

        try:
            result = subprocess.run(
                [php_path, "-l", str(php_file)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            checked += 1

            if result.returncode != 0:
                errors.append(f"{php_file}: {result.stdout.strip()}")
        except subprocess.TimeoutExpired:
            errors.append(f"{php_file}: Timeout during syntax check")
        except Exception as e:
            errors.append(f"{php_file}: Error - {e}")

    if errors:
        return ValidationResult(
            tool="PHP Lint",
            command="php -l <files>",
            passed=False,
            output="\n".join(errors),
        )

    return ValidationResult(
        tool="PHP Lint",
        command="php -l <files>",
        passed=True,
        output=f"Checked {checked} file(s) - no syntax errors",
    )


def run_phpcs(
    file_paths: List[Path],
    standard: str = "Drupal",
    extensions: str = "php,module,inc,install,test,profile,theme"
) -> ValidationResult:
    """
    Run PHP CodeSniffer on files.

    Args:
        file_paths: List of file paths
        standard: Coding standard to use
        extensions: File extensions to check

    Returns:
        ValidationResult
    """
    # Try to find phpcs
    phpcs_path = find_executable("phpcs")
    if not phpcs_path:
        # Try common locations
        common_paths = [
            "vendor/bin/phpcs",
            "./vendor/bin/phpcs",
            "../vendor/bin/phpcs",
        ]
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                phpcs_path = path
                break

    if not phpcs_path:
        return ValidationResult(
            tool="PHP CodeSniffer",
            command="phpcs",
            passed=False,
            output="",
            not_run_reason="phpcs not found in PATH or vendor/bin",
        )

    # Filter to relevant files
    valid_extensions = set(extensions.split(","))
    check_files = []
    for p in file_paths:
        ext = str(p).split(".")[-1] if "." in str(p) else ""
        if ext in valid_extensions and p.exists():
            check_files.append(str(p))

    if not check_files:
        return ValidationResult(
            tool="PHP CodeSniffer",
            command="phpcs",
            passed=True,
            output="No files to check",
        )

    try:
        cmd = [
            phpcs_path,
            f"--standard={standard}",
            f"--extensions={extensions}",
            "--report=summary",
        ] + check_files

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        # PHPCS returns non-zero if there are warnings/errors
        passed = result.returncode == 0
        output = result.stdout.strip()

        if result.stderr:
            output += "\n" + result.stderr.strip()

        return ValidationResult(
            tool="PHP CodeSniffer",
            command=f"phpcs --standard={standard}",
            passed=passed,
            output=output,
        )

    except subprocess.TimeoutExpired:
        return ValidationResult(
            tool="PHP CodeSniffer",
            command="phpcs",
            passed=False,
            output="Timeout during check",
        )
    except Exception as e:
        return ValidationResult(
            tool="PHP CodeSniffer",
            command="phpcs",
            passed=False,
            output=str(e),
        )


def run_phpstan(
    file_paths: List[Path],
    level: int = 5
) -> ValidationResult:
    """
    Run PHPStan static analysis.

    Args:
        file_paths: List of file paths
        level: Analysis level (0-9)

    Returns:
        ValidationResult
    """
    phpstan_path = find_executable("phpstan")
    if not phpstan_path:
        common_paths = [
            "vendor/bin/phpstan",
            "./vendor/bin/phpstan",
        ]
        for path in common_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                phpstan_path = path
                break

    if not phpstan_path:
        return ValidationResult(
            tool="PHPStan",
            command="phpstan",
            passed=False,
            output="",
            not_run_reason="phpstan not found",
        )

    php_files = [str(p) for p in file_paths if str(p).endswith(".php") and p.exists()]
    if not php_files:
        return ValidationResult(
            tool="PHPStan",
            command="phpstan",
            passed=True,
            output="No PHP files to analyze",
        )

    try:
        cmd = [
            phpstan_path,
            "analyse",
            f"--level={level}",
            "--no-progress",
            "--error-format=table",
        ] + php_files

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        passed = result.returncode == 0
        output = result.stdout.strip()

        return ValidationResult(
            tool="PHPStan",
            command=f"phpstan analyse --level={level}",
            passed=passed,
            output=output,
        )

    except subprocess.TimeoutExpired:
        return ValidationResult(
            tool="PHPStan",
            command="phpstan",
            passed=False,
            output="Timeout during analysis",
        )
    except Exception as e:
        return ValidationResult(
            tool="PHPStan",
            command="phpstan",
            passed=False,
            output=str(e),
        )


def validate_files(
    file_paths: List[Path],
    run_phpcs_check: bool = True,
    run_phpstan_check: bool = False,
) -> List[ValidationResult]:
    """
    Run all applicable validation checks on files.

    Args:
        file_paths: List of file paths to validate
        run_phpcs_check: Whether to run PHPCS
        run_phpstan_check: Whether to run PHPStan

    Returns:
        List of ValidationResult objects
    """
    results = []

    # Always run PHP lint
    results.append(run_php_lint(file_paths))

    # PHPCS if requested
    if run_phpcs_check:
        results.append(run_phpcs(file_paths))

    # PHPStan if requested
    if run_phpstan_check:
        results.append(run_phpstan(file_paths))

    return results
