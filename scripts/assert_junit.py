"""Require a nonempty, successful JUnit run with no skipped required tests."""

import argparse
import xml.etree.ElementTree as ET
from pathlib import Path


def validate(path: Path) -> int:
    root = ET.parse(path).getroot()
    cases = list(root.iter("testcase"))
    if not cases:
        raise ValueError("Required verification selected zero tests")
    blocked = [
        case.attrib.get("name", "unknown")
        for case in cases
        if any(case.find(tag) is not None for tag in ("skipped", "failure", "error"))
    ]
    if blocked:
        raise ValueError("Required tests did not pass: " + ", ".join(blocked))
    return len(cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        count = validate(args.report)
    except (OSError, ValueError, ET.ParseError) as exc:
        parser.exit(1, f"FAIL: {exc}\n")
    print(f"PASS: all {count} required tests executed successfully")


if __name__ == "__main__":
    main()
