#!/usr/bin/env python3
"""
Helper script to clear the database
"""

import shutil
from pathlib import Path

BASE_DIR = Path.home() / ".queuectl"

if BASE_DIR.exists():
    print(f"Clearing database at {BASE_DIR}...")
    shutil.rmtree(BASE_DIR)
    print("✓ Database cleared successfully")
else:
    print("No database found. Nothing to clear.")