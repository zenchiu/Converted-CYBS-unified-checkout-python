#!/usr/bin/env python3
"""Run e2e test and write results to e2e_test_result.txt"""
import os
import subprocess
import sys

cwd = os.path.dirname(os.path.abspath(__file__))
result = subprocess.run(
    [sys.executable, "test_e2e.py"],
    cwd=cwd,
    capture_output=True,
    text=True,
    timeout=120,
)

with open(os.path.join(cwd, "e2e_test_result.txt"), "w") as f:
    f.write("=== STDOUT ===\n")
    f.write(result.stdout or "")
    f.write("\n=== STDERR ===\n")
    f.write(result.stderr or "")
    f.write(f"\n=== EXIT CODE: {result.returncode} ===\n")

sys.exit(result.returncode)
