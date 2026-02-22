#!/usr/bin/env python3
"""
Read EXE file and export values to CSV in ~Original-EXE.csv format.

Usage:
    python read_exe_to_csv.py <exe_path> <output_csv>

Example:
    python read_exe_to_csv.py NR2003.exe values.csv
"""

import sys
import csv
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))
from exe_handler import ExeHandler


# Original CSV order reference - look in current working directory first, then script directory
def get_original_csv_path():
    """Find the original CSV file - check current dir first, then fall back to script dir"""
    cwd = Path.cwd()
    script_dir = Path(__file__).parent.parent.parent

    # Try common filenames in current directory
    possible_names = ["~Original - EXE.csv", "~Original-EXE.csv"]
    for name in possible_names:
        path = cwd / name
        if path.exists():
            return path
        path = script_dir / name
        if path.exists():
            return path

    # Return path to check in current directory
    return cwd / "~Original - EXE.csv"


ORIGINAL_CSV = get_original_csv_path()


def get_address_order():
    """Get the order of addresses from the original CSV"""
    order = []
    if ORIGINAL_CSV.exists():
        with open(ORIGINAL_CSV, "r") as f:
            reader = csv.reader(f)
            next(reader)  # Skip header
            for row in reader:
                if row and len(row) >= 2:
                    addr_str = row[0].strip()
                    if addr_str.startswith("&H"):
                        order.append(addr_str)
    return order


def read_exe_to_csv(exe_path, output_csv, module_filter=None):
    """Read all values from EXE and export to CSV.

    Args:
        exe_path: Path to EXE file
        output_csv: Path to output CSV file (or base name for multiple files)
        module_filter: If None, outputs all to one CSV and 4 separate files.
                       If a module name (chassis/engine/wheel/garage), only outputs that module.
    """

    if not Path(exe_path).exists():
        print(f"Error: EXE file not found: {exe_path}")
        return False

    handler = ExeHandler()

    # Get address order from original CSV
    address_order = get_address_order()
    print(f"Found {len(address_order)} addresses in original order")

    # Read all values by iterating through address_map directly
    address_values = {}

    print(f"Reading {len(handler.address_map)} addresses from EXE...")
    for key, info in handler.address_map.items():
        addr = info["address"]
        addr_hex = f"&H{addr:X}"
        value = handler.read_exe_value(exe_path, addr, info["type"])
        if value is not None:
            address_values[addr_hex] = {
                "Address": addr_hex,
                "Type": info["type"],
                "Value": value,
                "Original": info.get("original", value),
                "Label": info.get("label", "???"),
                "Module": info["module"],
                "ID": info.get("item_id", ""),
                "Field": info.get("field_num", ""),
                "Series": info.get("series", ""),
            }

    # Read Garage values
    print(f"Reading {len(handler.garage_address_map)} garage addresses...")
    garage_values = []
    for key, info in handler.garage_address_map.items():
        value = handler.read_exe_value(exe_path, info["address"], info["type"])
        if value is not None:
            garage_values.append(
                {
                    "Address": f"&H{info['address']:X}",
                    "Type": info["type"],
                    "Value": value,
                    "Original": info.get("original", value),
                    "Label": info.get("label", "???"),
                    "Module": "Garage",
                    "ID": "",
                    "Field": info.get("field_num", ""),
                    "Series": "",
                }
            )

    # Sort results: first by original order, then by address, then garage at end
    results = []

    # Add values in original order
    for addr in address_order:
        if addr in address_values:
            results.append(address_values[addr])

    # Add any remaining values not in original order (sorted by address)
    for addr in sorted(address_values.keys()):
        if addr not in [v["Address"] for v in results]:
            results.append(address_values[addr])

    # Add Garage values at the end
    results.extend(garage_values)

    # Group by module
    modules = {"Chassis": [], "Engine": [], "Wheel": [], "Garage": []}
    for row in results:
        module = row.get("Module", "")
        if module in modules:
            modules[module].append(row)
        elif module == "Garage":
            modules["Garage"].append(row)

    fieldnames = [
        "Address",
        "Type",
        "Value",
        "Original",
        "Label",
        "Module",
        "ID",
        "Field",
        "Series",
    ]

    if module_filter:
        # Output only the requested module
        module_filter_cap = module_filter.capitalize()
        if module_filter_cap not in modules:
            print(
                f"Error: Unknown module '{module_filter}'. Use: chassis, engine, wheel, or garage"
            )
            return False

        filtered_results = modules.get(module_filter_cap, [])
        print(
            f"Writing {len(filtered_results)} {module_filter} values to {output_csv}..."
        )
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(filtered_results)
        print(
            f"Done! Exported {len(filtered_results)} {module_filter} values to {output_csv}"
        )
    else:
        # Write combined CSV
        print(f"Writing {len(results)} values to {output_csv}...")
        with open(output_csv, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)
        print(f"Done! Exported {len(results)} values to {output_csv}")

        # Write separate CSV files for each module
        base_path = Path(output_csv)
        for mod_name, mod_results in modules.items():
            if mod_results:
                mod_filename = f"{base_path.stem}_{mod_name.lower()}{base_path.suffix}"
                print(
                    f"Writing {len(mod_results)} {mod_name} values to {mod_filename}..."
                )
                with open(mod_filename, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(mod_results)
                print(
                    f"Done! Exported {len(mod_results)} {mod_name} values to {mod_filename}"
                )

    return True


if __name__ == "__main__":
    module_filter = None

    if len(sys.argv) < 3:
        print("Read physics values from NR2003 EXE file to CSV")
        print("")
        print("Usage: python read_exe_to_csv.py <exe_file> <output.csv> [module]")
        print("")
        print("Modules: chassis, engine, wheel, garage")
        print("  - No module: writes all + separate files per module")
        print("  - With module: writes only that module")
        print("")
        print("Examples:")
        print("  python read_exe_to_csv.py NR2003.exe output.csv")
        print("  python read_exe_to_csv.py NR2003.exe chassis.csv chassis")
        print("  python read_exe_to_csv.py NR2003.exe wheel.csv wheel")
        sys.exit(1)

    exe_path = sys.argv[1]
    output_csv = sys.argv[2]

    if len(sys.argv) >= 4:
        module_filter = sys.argv[3].lower()

    if not Path(exe_path).exists():
        print(f"Error: EXE file not found: {exe_path}")
        sys.exit(1)

    read_exe_to_csv(exe_path, output_csv, module_filter)
