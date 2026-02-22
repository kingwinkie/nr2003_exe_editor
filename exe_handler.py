#!/usr/bin/env python3
"""
EXE Memory Handler - Reads and writes physics values to the game EXE
Uses address mapping from exe_addresses.csv
"""

import struct
import csv
from pathlib import Path
from typing import Dict, Optional, Tuple


def get_addresses_file_path(filename: str):
    """Find addresses file - check current dir first, then fall back to script dir"""
    cwd = Path.cwd()
    script_dir = Path(__file__).parent.parent.parent

    path = cwd / filename
    if path.exists():
        return path
    path = script_dir / filename
    if path.exists():
        return path
    return cwd / filename


ADDRESSES_FILE = get_addresses_file_path("~Original - EXE.csv")
GARAGE_ADDRESSES_FILE = get_addresses_file_path("~Original - Garage Settings - EXE.csv")

SINGLE_FLOAT_SIZE = 4
LONG_INT_SIZE = 4


class ExeHandler:
    """Handles reading/writing values to the game EXE"""

    def __init__(self):
        self.address_map = {}
        self.garage_address_map = {}
        self.exe_path = None
        self.address_offset = -1  # CSV addresses appear to be 1 byte off
        self.load_address_map()
        self.load_garage_address_map()

    def load_address_map(self):
        """Load address map from CSV file"""
        try:
            with open(ADDRESSES_FILE, "r") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header

                for row in reader:
                    if len(row) >= 6:
                        addr_str = row[0].strip()
                        if addr_str.startswith("&H"):
                            addr = int(addr_str[2:], 16)
                            data_type = row[1].strip()
                            value = row[2].strip() if len(row) > 2 else ""
                            original = row[3].strip() if len(row) > 3 else ""
                            label = row[4].strip() if len(row) > 4 else "Unknown"
                            module = row[5].strip() if len(row) > 5 else "Unknown"

                            # Column 7: Car/chassis identifier
                            # For Chassis: "cup-5", "cup-0-5", "gns-1", "cts-5&1", "all-0-5"
                            # For Engine: "0", "1", "2"... engine ID
                            # For Wheel: wheel numbers
                            car_id = row[6].strip() if len(row) > 6 else ""

                            # Column 8: Field number
                            # For Engine/Wheel: "Field03", "Field02" (no space)
                            # For Chassis: "3", "4", "5"... (just the number)
                            field_col = row[7].strip() if len(row) > 7 else ""

                            # For Chassis: column 9+ has additional series info
                            # For Engine: column 9=series(cup/gns/cts/pta), 10=chassis_type, 11=mode(Qual/Race)
                            series_info = row[8].strip() if len(row) > 8 else ""
                            chassis_type = row[9].strip() if len(row) > 9 else ""
                            mode = row[10].strip() if len(row) > 10 else ""

                            # Parse car_id into series and car_idx
                            parsed_series = ""
                            parsed_car_idx = -1

                            if module.lower() == "chassis":
                                # car_id like "cup-5", "gns-0-5", "cts-5&1", "all-0-5"
                                parsed_car_idx = self._parse_chassis_car_id(car_id)
                                # Extract series from car_id
                                for s in ["cup", "gns", "cts", "pta"]:
                                    if s in car_id.lower():
                                        parsed_series = s
                                        break
                                if "all" in car_id.lower():
                                    parsed_series = "all"
                            elif module.lower() == "engine":
                                # car_id is engine number 0-15
                                try:
                                    parsed_car_idx = int(car_id)
                                except ValueError:
                                    parsed_car_idx = -1
                                parsed_series = series_info  # cup/gns/cts/pta
                            elif module.lower() == "wheel":
                                # car_id is wheel number
                                try:
                                    parsed_car_idx = int(car_id)
                                except ValueError:
                                    parsed_car_idx = -1

                            key = (module, car_id, label, addr)
                            self.address_map[key] = {
                                "address": addr,
                                "type": data_type,
                                "value": value,
                                "original": original,
                                "label": label,
                                "module": module,
                                "car_id": car_id,
                                "field_col": field_col,
                                "series": parsed_series,
                                "car_idx": parsed_car_idx,
                                "chassis_type": chassis_type,
                                "mode": mode,
                            }

            print(f"Loaded {len(self.address_map)} address mappings")

            # Group by module
            modules = {}
            for key, info in self.address_map.items():
                module = info["module"]
                if module not in modules:
                    modules[module] = []
                modules[module].append(info)

            for module, infos in modules.items():
                print(f"  {module}: {len(infos)} addresses")

        except FileNotFoundError:
            print(f"Address file not found: {ADDRESSES_FILE}")

    def load_garage_address_map(self):
        """Load garage settings address map from CSV file"""
        try:
            with open(GARAGE_ADDRESSES_FILE, "r") as f:
                reader = csv.reader(f)
                next(reader)  # Skip header

                for row in reader:
                    if len(row) >= 6:
                        addr_str = row[0].strip()
                        if addr_str.startswith("&H"):
                            addr = int(addr_str[2:], 16)
                            data_type = row[1].strip()
                            value = row[2].strip() if len(row) > 2 else ""
                            original = row[3].strip() if len(row) > 3 else ""
                            label = row[4].strip() if len(row) > 4 else "Unknown"
                            module = row[5].strip() if len(row) > 5 else "Garage"

                            # Field number
                            field_num = row[7].strip() if len(row) > 7 else ""

                            # Min/Max/Step/Default
                            param_type = row[8].strip() if len(row) > 8 else ""

                            key = (field_num, param_type)
                            self.garage_address_map[key] = {
                                "address": addr,
                                "type": data_type,
                                "value": value,
                                "original": original,
                                "label": label,
                                "module": module,
                                "field_num": field_num,
                                "param_type": param_type,
                            }

            print(f"Loaded {len(self.garage_address_map)} garage address mappings")

        except FileNotFoundError:
            print(f"Garage address file not found: {GARAGE_ADDRESSES_FILE}")

    def rva_to_file_offset(
        self, rva: int, dos_header: bytes, pe_header_offset: int
    ) -> int:
        """Convert RVA to file offset using PE headers"""
        # Read PE signature
        pe_sig = struct.unpack("<I", dos_header[60:64])[0]

        # Read number of sections
        num_sections = struct.unpack(
            "<H", dos_header[pe_header_offset + 6 : pe_header_offset + 8]
        )[0]

        # Size of optional header
        opt_header_size = struct.unpack(
            "<H", dos_header[pe_header_offset + 20 : pe_header_offset + 22]
        )[0]

        # Section table starts after optional header
        section_table_offset = pe_header_offset + 24 + opt_header_size

        # Read section headers
        for i in range(num_sections):
            section_start = section_table_offset + (i * 40)
            virtual_size = struct.unpack(
                "<I", dos_header[section_start + 8 : section_start + 12]
            )[0]
            virtual_addr = struct.unpack(
                "<I", dos_header[section_start + 12 : section_start + 16]
            )[0]
            raw_size = struct.unpack(
                "<I", dos_header[section_start + 16 : section_start + 20]
            )[0]
            raw_offset = struct.unpack(
                "<I", dos_header[section_start + 20 : section_start + 24]
            )[0]

            if virtual_addr <= rva < virtual_addr + max(virtual_size, raw_size):
                return raw_offset + (rva - virtual_addr)

        # Fallback: assume direct offset
        return rva

    def read_exe_value(
        self, exe_path: str, address: int, data_type: str
    ) -> Optional[float]:
        """Read a value from the EXE at the given RVA"""
        try:
            # Apply address offset correction
            address = address + self.address_offset

            with open(exe_path, "rb") as f:
                # Read enough data to parse PE headers
                data = f.read(8192)

                # Get PE header offset
                pe_offset = struct.unpack("<I", data[60:64])[0]

                # Convert RVA to file offset
                file_offset = self.rva_to_file_offset(address, data, pe_offset)

                if file_offset >= len(data):
                    # Need to read more data
                    f.seek(file_offset)
                    data = f.read(4096)

                f.seek(file_offset)

                if data_type == "Sing":
                    # Single precision float (4 bytes)
                    data = f.read(SINGLE_FLOAT_SIZE)
                    if len(data) == SINGLE_FLOAT_SIZE:
                        return struct.unpack("<f", data)[0]
                elif data_type == "Doub":
                    # Double precision float (8 bytes)
                    data = f.read(8)
                    if len(data) == 8:
                        return struct.unpack("<d", data)[0]
                elif data_type == "Long":
                    # 4-byte integer
                    data = f.read(LONG_INT_SIZE)
                    if len(data) == LONG_INT_SIZE:
                        return struct.unpack("<I", data)[0]

            return None
        except Exception as e:
            print(f"Error reading from EXE at {hex(address)}: {e}")
            return None

    def write_exe_value(
        self, exe_path: str, address: int, data_type: str, value: float
    ) -> bool:
        """Write a value to the EXE at the given RVA"""
        try:
            # Apply address offset correction
            address = address + self.address_offset

            with open(exe_path, "r+b") as f:
                # Read enough data to parse PE headers
                data = f.read(8192)

                # Get PE header offset
                pe_offset = struct.unpack("<I", data[60:64])[0]

                # Convert RVA to file offset
                file_offset = self.rva_to_file_offset(address, data, pe_offset)

                f.seek(file_offset)

                if data_type == "Sing":
                    # Single precision float (4 bytes)
                    data = struct.pack("<f", value)
                    f.write(data)
                    return True
                elif data_type == "Doub":
                    # Double precision float (8 bytes)
                    data = struct.pack("<d", value)
                    f.write(data)
                    return True
                elif data_type == "Long":
                    # 4-byte integer
                    data = struct.pack("<I", int(value))
                    f.write(data)
                    return True

            return False
        except Exception as e:
            print(f"Error writing to EXE at {hex(address)}: {e}")
            return False

    def get_address_for_field(
        self, module: str, series: str, car_idx: int, field_label: str
    ) -> Optional[Dict]:
        """Get address info for a specific field"""
        # Try to match using the matches_car_id logic
        for key, info in self.address_map.items():
            if info["module"].lower() == module.lower():
                if field_label.lower() in info["label"].lower():
                    if self.matches_car_id(info, module, series, car_idx):
                        return info

        return None

    def _parse_chassis_car_id(self, car_id: str) -> int:
        """Parse chassis car_id like 'cup-5', 'cup-0-5', 'cts-5&1' to extract car index"""
        car_id_lower = car_id.lower()
        # Extract the number after the series prefix
        # Examples: "cup-5" -> 5, "cup-0-5" -> 0 (first in range), "cts-5&1" -> 5
        for s in ["cup", "gns", "cts", "pta"]:
            if car_id_lower.startswith(s):
                rest = car_id_lower[len(s) :].strip("-& ")
                # Get first number
                nums = []
                for part in rest.replace(",", " ").split():
                    if part.isdigit():
                        return int(part)
                break
        return -1

    def matches_car_id(
        self, info: Dict, module: str, series: str, car_idx: int
    ) -> bool:
        """Check if address info matches the given module/series/car_idx"""
        car_id = info.get("car_id", "")
        info_car_idx = info.get("car_idx", -1)
        info_series = info.get("series", "")

        if module.lower() == "chassis":
            # For chassis, check if car_id matches the selected series and car
            car_id_lower = car_id.lower()
            series_lower = series.lower()

            # Check series matches
            series_match = False
            if series_lower in car_id_lower or "all" in car_id_lower:
                series_match = True

            if not series_match:
                return False

            # Check car index - car_id like "cup-5", "cup-0-5", "cts-5&1"
            # We need to check if car_idx is in the range
            if info_car_idx == -1:
                return True  # Wildcard

            # Parse car_id to get all car indices it applies to
            car_indices = self._get_chassis_car_indices(car_id)
            return car_idx in car_indices

        elif module.lower() == "engine":
            # For engine: car_id is engine number, info_car_idx is the engine ID
            if info_car_idx == -1 or info_car_idx == car_idx:
                return True
            return False

        elif module.lower() == "wheel":
            # For wheel: car_id is wheel number
            if info_car_idx == -1 or info_car_idx == car_idx:
                return True
            return False

        return False

    def _get_chassis_car_indices(self, car_id: str) -> list:
        """Get all car indices from a car_id like 'cup-5', 'cup-0-5', 'cts-5&1'"""
        car_id_lower = car_id.lower()
        indices = []

        # Extract series prefix
        series_prefix = ""
        for s in ["cup", "gns", "cts", "pta"]:
            if car_id_lower.startswith(s):
                series_prefix = s
                break

        if not series_prefix:
            return indices

        rest = car_id_lower[len(series_prefix) :]

        # Handle different formats:
        # "cup-5" -> [5]
        # "cup-0-5" -> [0,1,2,3,4,5]
        # "cup-1&5" -> [1,5]
        # "all-0-5" -> [0,1,2,3,4,5]

        rest = rest.strip("-& ")

        # Check for range format "0-5"
        if "-" in rest and not "&" in rest:
            parts = rest.split("-")
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                start = int(parts[0])
                end = int(parts[1])
                indices = list(range(start, end + 1))
        else:
            # Handle comma/ampersand separated or single number
            for part in rest.replace(",", " ").replace("&", " ").split():
                if part.isdigit():
                    indices.append(int(part))

        return indices if indices else [-1]  # Return -1 if no valid indices found

    def load_all_from_exe(
        self, exe_path: str, module: str, series: str, car_idx: int
    ) -> Dict:
        """Load all values for a module from EXE - keyed by address"""
        results = {}

        for key, info in self.address_map.items():
            if info["module"].lower() != module.lower():
                continue

            value = self.read_exe_value(exe_path, info["address"], info["type"])
            if value is not None:
                results[info["address"]] = value

        return results

    def save_all_to_exe(
        self, exe_path: str, module: str, series: str, car_idx: int, values: Dict
    ) -> int:
        """Save all values for a module to EXE - values dict keyed by field label"""
        count = 0

        for key, info in self.address_map.items():
            if info["module"].lower() != module.lower():
                continue

            label = info["label"]
            addr = info["address"]
            if label in values:
                try:
                    value = float(values[label])
                    if self.write_exe_value(exe_path, addr, info["type"], value):
                        count += 1
                except (ValueError, TypeError):
                    pass

        return count


def float_to_hex_bytes(value: float) -> str:
    """Convert float to hex bytes representation"""
    return " ".join(f"{b:02x}" for b in struct.pack("<f", value))


def hex_bytes_to_float(hex_str: str) -> float:
    """Convert hex bytes to float"""
    bytes_data = bytes.fromhex(hex_str.replace(" ", ""))
    return struct.unpack("<f", bytes_data)[0]


if __name__ == "__main__":
    handler = ExeHandler()
    print(f"\nSample addresses:")
    for i, (key, info) in enumerate(list(handler.address_map.items())[:10]):
        print(f"  {key}: {hex(info['address'])} ({info['type']})")
