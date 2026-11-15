#!/usr/bin/env python3
"""Script to capture real Linux hardware command outputs from the host machine."""

import subprocess
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "real"

COMMANDS_TO_CAPTURE = [
    ("lscpu.txt", ["lscpu"]),
    ("free_b.txt", ["free", "-b"]),
    ("lsblk_json.json", ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,MOUNTPOINT,MODEL,ROTA,TRAN"]),
    ("lspci_vmm.txt", ["lspci", "-vmm"]),
    ("uname_r.txt", ["uname", "-r"]),
]

PRIVILEGED_COMMANDS = [
    ("dmidecode_memory.txt", ["sudo", "-n", "dmidecode", "-t", "memory"]),
    ("dmidecode_baseboard.txt", ["sudo", "-n", "dmidecode", "-t", "baseboard"]),
    ("dmidecode_bios.txt", ["sudo", "-n", "dmidecode", "-t", "bios"]),
]


def capture() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Capturing real system hardware fixtures to {FIXTURES_DIR}...")

    # Capture standard commands
    for filename, argv in COMMANDS_TO_CAPTURE:
        target_file = FIXTURES_DIR / filename
        try:
            print(f"Running: {' '.join(argv)} -> {filename}")
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                target_file.write_text(proc.stdout, encoding="utf-8")
                print(f"  [OK] Saved {len(proc.stdout)} chars")
            else:
                print(f"  [WARN] Command exited with code {proc.returncode}: {proc.stderr.strip()}")
        except Exception as e:
            print(f"  [SKIP] Could not run {argv[0]}: {e}")

    # Capture privileged commands if possible
    for filename, argv in PRIVILEGED_COMMANDS:
        target_file = FIXTURES_DIR / filename
        try:
            print(f"Running (privileged): {' '.join(argv)} -> {filename}")
            proc = subprocess.run(argv, capture_output=True, text=True, timeout=5)
            if proc.returncode == 0:
                target_file.write_text(proc.stdout, encoding="utf-8")
                print(f"  [OK] Saved {len(proc.stdout)} chars")
            else:
                print(f"  [WARN] Sudo command exited with code {proc.returncode} (requires sudoers configuration)")
        except Exception as e:
            print(f"  [SKIP] Could not run {argv[0]}: {e}")

    # Create README marker in real directory
    readme = FIXTURES_DIR / "README.md"
    readme.write_text(
        "# Real System Hardware Fixtures\n\n"
        "Files in this directory were captured directly from a real Linux machine using `scripts/capture_system_fixtures.py`.\n",
        encoding="utf-8",
    )
    print("\nCapture completed.")


if __name__ == "__main__":
    capture()

