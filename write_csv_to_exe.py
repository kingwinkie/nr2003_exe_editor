#!/usr/bin/env python3
"""
Write values from CSV to EXE file in ~Original-EXE.csv format.

Usage:
    python write_csv_to_exe.py <csv_path> <exe_path>

Example:
    python write_csv_to_exe.py values.csv NR2003.exe
"""

import sys
import csv
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from exe_handler import ExeHandler


def write_csv_to_exe(csv_path, exe_path, module_filter=None):
    """Read CSV and write values to EXE.

    Args:
        csv_path: Path to CSV file
        exe_path: Path to EXE file
        module_filter: Optional filter to only write rows matching this module
    """

    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}")
        return False

    if not Path(exe_path).exists():
        print(f"Error: EXE file not found: {exe_path}")
        return False

    handler = ExeHandler()

    # Read CSV
    print(f"Reading {csv_path}...")
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Found {len(rows)} rows")

    # Filter by module if specified
    if module_filter:
        module_filter = module_filter.lower()
        original_count = len(rows)
        rows = [r for r in rows if r.get("Module", "").lower() == module_filter]
        print(f"Filtered to {len(rows)} {module_filter} rows (from {original_count})")

    if not rows:
        print("No rows to write!")
        return False

    # Write values to EXE
    count = 0
    errors = 0

    for row in rows:
        addr_str = row.get("Address", "").strip()
        if not addr_str.startswith("&H"):
            continue

        try:
            address = int(addr_str[2:], 16)
            data_type = row.get("Type", "Sing").strip()
            value = float(row.get("Value", 0))

            if handler.write_exe_value(exe_path, address, data_type, value):
                count += 1
            else:
                errors += 1
                print(f"  Error writing to {addr_str}: {row.get('Label', '???')}")
        except Exception as e:
            errors += 1
            print(f"  Error: {e}")

    print(f"Done! Wrote {count} values to {exe_path}")
    if errors:
        print(f"Errors: {errors}")
    return True


if __name__ == "__main__":
    module_filter = None

    if len(sys.argv) < 3:
        print("Write physics values from CSV to NR2003 EXE file")
        print("")
        print("Usage: python write_csv_to_exe.py <input.csv> <exe_file> [module]")
        print("")
        print("Modules: chassis, engine, wheel, garage")
        print("  - No module: writes all rows from CSV")
        print("  - With module: writes only rows matching that module")
        print("")
        print("Examples:")
        print("  python write_csv_to_exe.py values.csv NR2003.exe")
        print("  python write_csv_to_exe.py chassis.csv NR2003.exe chassis")
        print("  python write_csv_to_exe.py wheel.csv NR2003.exe wheel")
        sys.exit(1)

    csv_path = sys.argv[1]
    exe_path = sys.argv[2]

    if len(sys.argv) >= 4:
        module_filter = sys.argv[3].lower()

    if not Path(csv_path).exists():
        print(f"Error: CSV file not found: {csv_path}")
        sys.exit(1)

    if not Path(exe_path).exists():
        print(f"Error: EXE file not found: {exe_path}")
        sys.exit(1)

    write_csv_to_exe(csv_path, exe_path, module_filter)
