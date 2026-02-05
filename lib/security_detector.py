"""
Security issue detection.

Identifies changes that may be security-related and should follow
the Drupal Security Team process instead of public issue queue.
"""

import re
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class SecurityIndicator:
    """A detected security indicator."""
    category: str
    pattern: str
    description: str
    severity: str  # "high", "medium", "low"
    line: str  # The matching line


# Patterns that indicate security-sensitive code
SECURITY_PATTERNS = [
    # SQL Injection risks
    (
        "sql_injection",
        r'db_query\s*\([^)]*\$',
        "Direct variable in db_query (potential SQL injection)",
        "high"
    ),
    (
        "sql_injection",
        r'->query\s*\([^)]*\.\s*\$',
        "String concatenation in query (potential SQL injection)",
        "high"
    ),
    (
        "sql_injection",
        r'->where\s*\([^)]*\.\s*\$',
        "String concatenation in where clause",
        "medium"
    ),

    # XSS risks
    (
        "xss",
        r'print\s+\$_(GET|POST|REQUEST)',
        "Direct output of user input (XSS risk)",
        "high"
    ),
    (
        "xss",
        r'echo\s+\$_(GET|POST|REQUEST)',
        "Direct echo of user input (XSS risk)",
        "high"
    ),
    (
        "xss",
        r'#markup.*\$',
        "Variable in #markup without sanitization",
        "medium"
    ),

    # Access control
    (
        "access_bypass",
        r'->bypassAccessCheck\s*\(\s*\)',
        "Access check bypass",
        "high"
    ),
    (
        "access_bypass",
        r"'#access'\s*=>\s*TRUE",
        "Hardcoded access grant",
        "medium"
    ),
    (
        "access_bypass",
        r'user_access\s*\(\s*[\'"]administer',
        "Admin permission check modification",
        "medium"
    ),

    # Authentication
    (
        "authentication",
        r'password|passwd|secret|credential',
        "Password/credential handling",
        "medium"
    ),
    (
        "authentication",
        r'session_id|session_start|session_regenerate',
        "Session handling modification",
        "medium"
    ),
    (
        "authentication",
        r'setcookie|set_cookie',
        "Cookie manipulation",
        "medium"
    ),

    # File operations
    (
        "file_access",
        r'file_put_contents\s*\([^)]*\$',
        "Dynamic file write path",
        "high"
    ),
    (
        "file_access",
        r'fopen\s*\([^)]*\$',
        "Dynamic file open path",
        "high"
    ),
    (
        "file_access",
        r'unlink\s*\([^)]*\$',
        "Dynamic file deletion",
        "high"
    ),
    (
        "file_access",
        r'chmod\s*\(',
        "Permission modification",
        "medium"
    ),

    # Code execution
    (
        "code_execution",
        r'\beval\s*\(',
        "eval() usage (code execution)",
        "high"
    ),
    (
        "code_execution",
        r'\bexec\s*\(',
        "exec() usage (command execution)",
        "high"
    ),
    (
        "code_execution",
        r'\bsystem\s*\(',
        "system() usage (command execution)",
        "high"
    ),
    (
        "code_execution",
        r'\bshell_exec\s*\(',
        "shell_exec() usage",
        "high"
    ),
    (
        "code_execution",
        r'\bpassthru\s*\(',
        "passthru() usage",
        "high"
    ),
    (
        "code_execution",
        r'\bproc_open\s*\(',
        "proc_open() usage",
        "medium"
    ),

    # Serialization
    (
        "serialization",
        r'\bunserialize\s*\([^)]*\$',
        "unserialize with user input (object injection risk)",
        "high"
    ),

    # Cryptography
    (
        "cryptography",
        r'\bmd5\s*\(',
        "MD5 usage (weak for passwords)",
        "low"
    ),
    (
        "cryptography",
        r'\bsha1\s*\(',
        "SHA1 usage (weak for passwords)",
        "low"
    ),
    (
        "cryptography",
        r'rand\s*\(|mt_rand\s*\(',
        "Non-cryptographic random (may be security context)",
        "low"
    ),

    # CSRF
    (
        "csrf",
        r'drupal_get_token|csrf_token',
        "CSRF token handling",
        "medium"
    ),

    # File paths that often indicate security context
    (
        "security_file",
        r'/(auth|login|logout|password|permission|access|session)/',
        "Security-related file path",
        "medium"
    ),
]


def detect_security_indicators(diff_content: str) -> List[SecurityIndicator]:
    """
    Detect security-related patterns in diff content.

    Only checks added lines (lines starting with +).

    Args:
        diff_content: Git diff content

    Returns:
        List of SecurityIndicator objects
    """
    indicators = []

    # Extract added lines with their content
    for line in diff_content.split('\n'):
        if not line.startswith('+'):
            continue
        if line.startswith('+++'):  # Skip file header
            continue

        line_content = line[1:]  # Remove the + prefix

        for category, pattern, description, severity in SECURITY_PATTERNS:
            if re.search(pattern, line_content, re.IGNORECASE):
                indicators.append(SecurityIndicator(
                    category=category,
                    pattern=pattern,
                    description=description,
                    severity=severity,
                    line=line_content.strip()[:100],  # Limit line length
                ))

    return indicators


def detect_security_in_files(file_paths: List[str]) -> List[SecurityIndicator]:
    """
    Detect security-related file paths.

    Args:
        file_paths: List of changed file paths

    Returns:
        List of SecurityIndicator objects
    """
    indicators = []

    security_path_patterns = [
        (r'auth', "Authentication-related file"),
        (r'login', "Login-related file"),
        (r'password', "Password-related file"),
        (r'permission', "Permission-related file"),
        (r'access', "Access control file"),
        (r'session', "Session-related file"),
        (r'security', "Security-related file"),
        (r'csrf', "CSRF-related file"),
        (r'token', "Token-related file"),
    ]

    for path in file_paths:
        path_lower = path.lower()
        for pattern, description in security_path_patterns:
            if pattern in path_lower:
                indicators.append(SecurityIndicator(
                    category="security_file",
                    pattern=pattern,
                    description=description,
                    severity="medium",
                    line=path,
                ))
                break  # Only one indicator per file

    return indicators


def is_security_related(
    diff_content: str,
    file_paths: List[str],
    threshold: str = "medium"
) -> Tuple[bool, List[SecurityIndicator]]:
    """
    Determine if changes are security-related.

    Args:
        diff_content: Git diff content
        file_paths: List of changed file paths
        threshold: Minimum severity to trigger ("high", "medium", "low")

    Returns:
        Tuple of (is_security_related, indicators)
    """
    severity_order = {"high": 3, "medium": 2, "low": 1}
    threshold_level = severity_order.get(threshold, 2)

    indicators = []

    # Check diff content
    content_indicators = detect_security_indicators(diff_content)
    indicators.extend(content_indicators)

    # Check file paths
    path_indicators = detect_security_in_files(file_paths)
    indicators.extend(path_indicators)

    # Filter by threshold
    relevant = [
        i for i in indicators
        if severity_order.get(i.severity, 0) >= threshold_level
    ]

    # Consider it security-related if we have high severity indicators
    # or multiple medium-severity *content* indicators.
    #
    # File-path heuristics ("access", "permission", etc.) are useful signals but
    # are too noisy to use as a hard stop on their own.
    high_count = sum(1 for i in relevant if i.severity == "high")
    medium_non_path_count = sum(
        1 for i in relevant if i.severity == "medium" and i.category != "security_file"
    )

    is_security = high_count > 0 or medium_non_path_count >= 2

    return is_security, indicators


def format_security_warning(indicators: List[SecurityIndicator]) -> str:
    """Format security indicators as a warning message."""
    lines = [
        "## Security Warning",
        "",
        "This change appears to be security-related. Security issues should",
        "NOT be posted publicly on drupal.org.",
        "",
        "**Follow the Drupal Security Team process instead:**",
        "https://www.drupal.org/drupal-security-team/security-team-procedures",
        "",
        "### Detected Security Indicators",
        "",
    ]

    # Group by severity
    high = [i for i in indicators if i.severity == "high"]
    medium = [i for i in indicators if i.severity == "medium"]
    low = [i for i in indicators if i.severity == "low"]

    if high:
        lines.append("**High Severity:**")
        for i in high:
            lines.append(f"- {i.description}")
            lines.append(f"  `{i.line}`")
        lines.append("")

    if medium:
        lines.append("**Medium Severity:**")
        for i in medium:
            lines.append(f"- {i.description}")
        lines.append("")

    if low:
        lines.append("**Low Severity:**")
        for i in low:
            lines.append(f"- {i.description}")
        lines.append("")

    return "\n".join(lines)
