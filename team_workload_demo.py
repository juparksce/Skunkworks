"""Summarize weekly task hours to spot team workload imbalances."""

from __future__ import annotations

import argparse
import csv
import io
import unittest
from typing import TextIO
from decimal import Decimal, InvalidOperation
from pathlib import Path

REQUIRED_COLUMNS = {"team_member", "task", "hours"}
DEMO_CSV = """team_member,task,hours
Avery,API migration,20
Avery,Code review,8
Jordan,Data import,24
Jordan,Release support,20
Morgan,On-call rotation,20
Morgan,Bug fixes,12
Casey,Planning,8
Casey,Onboarding,4
"""


def load_workloads(source: TextIO) -> dict[str, tuple[Decimal, int]]:
    """Return each member's total hours and number of assigned tasks."""
    reader = csv.DictReader(source)
    if reader.fieldnames is None or not REQUIRED_COLUMNS.issubset(reader.fieldnames):
        expected = ", ".join(sorted(REQUIRED_COLUMNS))
        raise ValueError(f"CSV must include these columns: {expected}")

    workloads: dict[str, tuple[Decimal, int]] = {}
    for line_number, row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in row.values() if value is not None):
            continue

        member = (row.get("team_member") or "").strip()
        task = (row.get("task") or "").strip()
        raw_hours = (row.get("hours") or "").strip()
        if not member or not task or not raw_hours:
            raise ValueError(f"row {line_number}: team_member, task, and hours are required")
        try:
            hours = Decimal(raw_hours)
        except InvalidOperation as error:
            raise ValueError(f"row {line_number}: hours must be a number") from error
        if not hours.is_finite() or hours < 0:
            raise ValueError(f"row {line_number}: hours must be a finite, non-negative number")

        previous_hours, previous_tasks = workloads.get(member, (Decimal("0"), 0))
        workloads[member] = (previous_hours + hours, previous_tasks + 1)

    return workloads


def workload_status(hours: Decimal, capacity: Decimal) -> str:
    if hours > capacity:
        return "OVER CAPACITY"
    if hours < capacity * Decimal("0.5"):
        return "UNDERALLOCATED"
    return "ON TRACK"


def render_report(
    workloads: dict[str, tuple[Decimal, int]], capacity: Decimal
) -> str:
    if not workloads:
        return "No assignments found.\n"

    lines = [
        f"{'TEAM MEMBER':<18} {'TASKS':>5} {'HOURS':>8} {'UTILIZATION':>12}  STATUS",
        "-" * 66,
    ]
    for member, (hours, task_count) in sorted(
        workloads.items(), key=lambda item: (-item[1][0], item[0].casefold())
    ):
        utilization = hours / capacity * Decimal("100")
        lines.append(
            f"{member:<18} {task_count:>5} {hours:>8.1f} {utilization:>11.0f}%  "
            f"{workload_status(hours, capacity)}"
        )

    team_hours = sum((hours for hours, _ in workloads.values()), Decimal("0"))
    team_capacity = capacity * len(workloads)
    team_utilization = team_hours / team_capacity * Decimal("100")
    lines.extend(
        [
            "-" * 66,
            f"Team total: {team_hours:.1f} / {team_capacity:.1f} hours "
            f"({team_utilization:.0f}% of capacity across {len(workloads)} people)",
        ]
    )
    return "\n".join(lines) + "\n"


class WorkloadReportTests(unittest.TestCase):
    def test_demo_totals_and_task_counts(self) -> None:
        workloads = load_workloads(io.StringIO(DEMO_CSV))
        self.assertEqual(workloads["Jordan"], (Decimal("44"), 2))
        self.assertEqual(workloads["Casey"], (Decimal("12"), 2))

    def test_report_flags_imbalanced_workloads(self) -> None:
        report = render_report(load_workloads(io.StringIO(DEMO_CSV)), Decimal("40"))
        self.assertIn("Jordan", report)
        self.assertIn("OVER CAPACITY", report)
        self.assertIn("UNDERALLOCATED", report)
        self.assertIn("116.0 / 160.0 hours", report)

    def test_invalid_hours_are_rejected(self) -> None:
        source = io.StringIO("team_member,task,hours\nAvery,Planning,-1\n")
        with self.assertRaisesRegex(ValueError, "non-negative"):
            load_workloads(source)

    def test_missing_columns_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "must include"):
            load_workloads(io.StringIO("team_member,hours\nAvery,4\n"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "csv_file",
        nargs="?",
        type=Path,
        help="CSV with team_member, task, and hours columns (uses built-in demo if omitted)",
    )
    parser.add_argument(
        "--capacity",
        type=Decimal,
        default=Decimal("40"),
        help="weekly hours available per team member (default: 40)",
    )
    parser.add_argument(
        "--test", action="store_true", help="run the built-in unit tests"
    )
    args = parser.parse_args()

    if args.test:
        result = unittest.TextTestRunner(verbosity=2).run(
            unittest.defaultTestLoader.loadTestsFromTestCase(WorkloadReportTests)
        )
        return 0 if result.wasSuccessful() else 1
    if not args.capacity.is_finite() or args.capacity <= 0:
        parser.error("--capacity must be a positive number")

    try:
        if args.csv_file:
            with args.csv_file.open(newline="", encoding="utf-8-sig") as source:
                workloads = load_workloads(source)
        else:
            workloads = load_workloads(io.StringIO(DEMO_CSV))
    except (OSError, ValueError) as error:
        parser.error(str(error))

    print(render_report(workloads, args.capacity), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
