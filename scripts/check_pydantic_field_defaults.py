"""Check that all pydantic Field() calls use the default= keyword for default values.

Positional defaults like Field(0, description="...") are harder to read at a glance
and inconsistent with the rest of the codebase. Required fields using Field(...) are fine.
"""

import re
import sys
from pathlib import Path

# Matches Field( where first non-whitespace content is neither ... nor a keyword=.
# \s* allows for multi-line calls where the value starts on the next line.
_PATTERN = re.compile(r"\.Field\((?!\s*\.\.\.)(?!\s*\w+=)")


def check_default_is_set() -> int:
    """Run check.

    Returns:
        int: 0 if no violations, 1 otherwise
    """
    violations: list[str] = []
    for path in Path("habapp_rules").rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        for match in _PATTERN.finditer(content):
            lineno = content[: match.start()].count("\n") + 1
            violations.append(f"{path}:{lineno}: {lines[lineno - 1].strip()}")

    if violations:
        print("ERROR: pydantic Field() must use the default= keyword for default values:")  # noqa: T201
        for violation in violations:
            print(f"  {violation}")  # noqa: T201
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(check_default_is_set())
