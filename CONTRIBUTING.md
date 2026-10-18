# Contribute to drupal-contribute-fix

Keep each change focused on one problem.
Explain the observed behavior and the expected result.
Include reproduction steps when you report a bug.

## Development checks

The Python code uses only the standard library.
Run the test suite from the repository root:

```bash
python3 -m unittest discover -s tests -v
```

Check shell syntax after changes to setup scripts:

```bash
for script in scripts/*.sh; do
  bash -n "$script" || exit
done
```

Run each changed command with `--help`.
GitHub Actions also checks Python 3.8, 3.12, and 3.14.
A local result does not establish the status of a remote CI run.
Run the relevant behavior tests for code changes.
Record the exact commands and their results in the pull request.
State which checks did not run and why.

Tests that mock Drupal.org, Git, DDEV, or Composer do not prove a live integration.
Describe a live check separately when you perform one.

## Documentation and generated text

Use [ASD-STE100, Issue 9, 15 January 2025](https://www.asd-ste100.org/) as the writing standard.
Apply it to README files, reference guides, skill instructions, help text, comments, and generated reports.
Preserve exact command names, API identifiers, quotations, and legal text.

Use these rules during each edit:

- Use active voice.
- Give one instruction in each procedural sentence.
- Start an instruction with a verb.
- Put a condition before the instruction that it controls.
- Use no more than 20 words in a procedural sentence.
- Use no more than 25 words in a descriptive sentence.
- Use the same term for the same item.
- Define a technical term or abbreviation before its first use.
- Use approved words with their approved meanings.
- Keep technical names and technical verbs consistent.
- Replace vague claims with an action, an observable result, or a stated limit.

Use numbered lists for procedures.
Use tables when readers must compare options.
Keep each paragraph on one subject.
Keep examples consistent with current command help and actual behavior.

The full standard includes writing rules and a controlled dictionary.
Use the [official copy and review resources](https://www.asd-ste100.org/STE_downloads.html) for a full language review.
A short checklist or automated check does not establish ASD-STE100 compliance.
Do not claim verified compliance without a complete review against the standard and dictionary.

## Evidence in reports

Distinguish facts from candidate matches and recommendations.
Do not describe a proposed procedure as a completed test.
Do not infer application behavior from a successful syntax check.
Do not infer RTBC status from one passing test.

For each completed check, record:

- The tested commit, MR, or patch.
- The environment and relevant versions.
- The exact command.
- The exit status and observed output.
- The path to retained evidence, when available.

Use `Not run` for a check that did not execute.
State its blocker.
Keep placeholders visible until a reviewer supplies the missing evidence.

## Pull requests

Describe the problem and the resulting behavior.
Include the tests you ran and their results.
Update the documentation when commands or behavior change.
Keep unrelated formatting changes outside the pull request.
