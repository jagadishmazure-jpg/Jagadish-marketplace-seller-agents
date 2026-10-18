#!/usr/bin/env python3
"""Print the real test count. Run: python scripts/count_tests.py"""
import subprocess
import sys

out = subprocess.run([sys.executable, "-m", "pytest", "tests/",
                      "--tb=no", "-q"], capture_output=True, text=True)
print(out.stdout.strip().splitlines()[-1])
