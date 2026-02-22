NR2003 EXE Physics Editor
=======================

Reads and writes physics values to NR2003 EXE files.

Files
-----
read_exe_to_csv.py      Read values from EXE to CSV
write_csv_to_exe.py     Write values from CSV to EXE
exe_handler.py          Internal handler (required)
~Original - EXE.csv     Address definitions for physics
~Original - Garage Settings - EXE.csv   Address definitions for garage
readme.txt              This file

Read EXE to CSV
---------------
Usage: python read_exe_to_csv.py <exe_file> <output.csv> [module]

Modules: chassis, engine, wheel, garage
  - No module: writes all + separate files per module
  - With module: writes only that module

Examples:
  python read_exe_to_csv.py NR2003.exe output.csv
  python read_exe_to_csv.py NR2003.exe chassis.csv chassis
  python read_exe_to_csv.py NR2003.exe wheel.csv wheel

Output CSV columns:
  Address, Type, Value, Original, Label, Module, ID, Field, Series

Write CSV to EXE
---------------
Usage: python write_csv_to_exe.py <input.csv> <exe_file> [module]

Modules: chassis, engine, wheel, garage
  - No module: writes all rows from CSV
  - With module: writes only rows matching that module

Input CSV format (from read output):
  Address, Type, Value, ...
  &H2EE57D, Sing, 3400.5, ...

Examples:
  python write_csv_to_exe.py values.csv NR2003.exe
  python write_csv_to_exe.py chassis.csv NR2003.exe chassis
  python write_csv_to_exe.py wheel.csv NR2003.exe wheel

Workflow
--------
1. Read current values:
   python read_exe_to_csv.py NR2003.exe current.csv

2. Edit CSV with new values (modify Value column)

3. Write back to EXE:
   python write_csv_to_exe.py current.csv NR2003_modified.exe

4. Backup original EXE and rename modified one

Notes
----
- Always backup your original EXE file
- Address format: &HXXXXXXXX (hex)
- Types: Sing (float), Long (int32), Doub (double)
