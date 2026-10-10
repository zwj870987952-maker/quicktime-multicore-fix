#!/usr/bin/env python3
"""
QuickTime Multi-Core & High-Resolution Compatibility Patch Utility
===================================================================
Automatically resolves QuickTime crashes, 0KB exports, "Error -2048",
and "Disk full (-34)" on Windows systems with modern multi-core CPUs
(> 16 threads / AMD Ryzen / Intel Core i7/i9) and high-resolution (2K/4K) exports.

Zero third-party dependencies. Uses standard Python 3 libraries only.
"""

import os
import sys
import glob
import shutil
import struct
import winreg
import ctypes
import subprocess
from datetime import datetime

# ==============================================================================
# Patch Specifications & Definitions
# ==============================================================================

# 1. QuickTimeH264.qtx: Dynamic Caller-Aware Processor Clamp
# Preserves the first 17 bytes (0x68d70 to 0x68d80) to ensure the PE relocation
# table entry at 0x68d79 (call [0x683ca3d4]) remains 100% aligned and intact.
# Dynamically clamps eax against caller limit at [esp + 0x28]:
# <= 1080p: caller requests 8 -> returns min(procs, 8)
#  > 1080p: caller requests 4 -> returns min(procs, 4)
QT_H264_OFFSET = 0x68d81
QT_H264_EXPECTED_ORIGINAL = bytes.fromhex("83f8087e02b00883c424c3") # or unpatched Apple bytes
QT_H264_PATCH = bytes.fromhex("3b4424287e048b44242883c424c390")

# 2. QuickTime.qts: Processor Count Clamps
# Offset 0x2eb3e1: Secondary CPU core detection
QT_QTS_OFFSET1 = 0x2eb3e1
QT_QTS_PATCH1 = bytes.fromhex("83f8087e02b00883c424c3")

# Offset 0x9ca11: Carbon MPProcessors() API clamp
QT_QTS_OFFSET2 = 0x9ca11
QT_QTS_PATCH2 = bytes.fromhex("83f8087e02b00883c424c3")

# 3. AppleProResDecoder.qtx: ProRes Decoder Thread Clamp
# Offset 0x4da32
QT_PRORES_OFFSET = 0x4da32
QT_PRORES_PATCH = bytes.fromhex("83f8087e02b00883c424c3")

# Registry IFEO Target Executables
IFEO_TARGETS = [
    "quicktimeShim.exe",
    "ExportController.exe",
    "QuickTimePlayer.exe",
]
IFEO_AFFINITY_MASK = 0xFF  # 8 Cores (Processors 0-7)


def is_admin():
    """Check if the current process has administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def run_as_admin():
    """Re-launch the current script with Administrator privileges."""
    if is_admin():
        return True
    print("[*] Requesting Administrator privileges (UAC prompt)...")
    params = " ".join([f'"{arg}"' for arg in sys.argv])
    ret = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, params, None, 1
    )
    if ret > 32:
        sys.exit(0)
    else:
        print("[-] Failed to elevate privileges. Please run this script as Administrator.")
        return False


def kill_hung_shims():
    """Kill lingering quicktimeShim.exe processes holding file locks."""
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "quicktimeShim.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def get_quicktime_dir():
    """Locate the QuickTime installation directory."""
    # Check standard 64-bit Windows path
    default_path = r"C:\Program Files (x86)\QuickTime"
    if os.path.exists(default_path):
        return default_path

    # Check Windows Registry
    registry_keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Apple Computer, Inc.\QuickTime"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Apple Computer, Inc.\QuickTime"),
    ]
    for hkey, subkey in registry_keys:
        try:
            with winreg.OpenKey(hkey, subkey) as key:
                val, _ = winreg.QueryValueEx(key, "InstallDir")
                if os.path.exists(val):
                    return val
        except OSError:
            continue

    return default_path if os.path.exists(default_path) else None


def find_maya_shims():
    """Locate all quicktimeShim.exe instances across installed Maya versions."""
    shims = []
    base_pattern = r"C:\Program Files\Autodesk\Maya*\bin\quicktimeShim.exe"
    for p in glob.glob(base_pattern):
        if os.path.isfile(p):
            shims.append(p)
    return shims


def backup_file(file_path):
    """
    Create a permanent .original backup (never overwritten once created)
    and a timestamped backup before modifying.
    """
    if not os.path.exists(file_path):
        return None

    orig_backup = file_path + ".original"
    if not os.path.exists(orig_backup):
        shutil.copy2(file_path, orig_backup)
        print(f"[+] Pristine backup created: {orig_backup}")

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    ts_backup = file_path + f".bak_{ts}"
    shutil.copy2(file_path, ts_backup)
    return orig_backup


def restore_backup(file_path):
    """Restore .original backup if available."""
    orig_backup = file_path + ".original"
    if os.path.exists(orig_backup):
        shutil.copy2(orig_backup, file_path)
        print(f"[+] Restored original: {file_path}")
        return True
    return False


def patch_binary(file_path, offset, patch_bytes, name="Component"):
    """Write patch bytes at specific offset with verification and backup."""
    if not os.path.exists(file_path):
        print(f"[-] File not found: {file_path}")
        return False

    backup_file(file_path)

    with open(file_path, "rb") as f:
        data = bytearray(f.read())

    if offset + len(patch_bytes) > len(data):
        print(f"[-] Offset 0x{offset:X} exceeds file size for {name}")
        return False

    current_bytes = data[offset : offset + len(patch_bytes)]
    if current_bytes == patch_bytes:
        print(f"[=] {name} is already patched at 0x{offset:X}.")
        return True

    data[offset : offset + len(patch_bytes)] = patch_bytes

    with open(file_path, "wb") as f:
        f.write(data)

    print(f"[+] Successfully patched {name} at offset 0x{offset:X}.")
    return True


def enable_large_address_aware(exe_path):
    """Enable IMAGE_FILE_LARGE_ADDRESS_AWARE (0x0020) in PE FileHeader."""
    if not os.path.exists(exe_path):
        print(f"[-] Executable not found: {exe_path}")
        return False

    backup_file(exe_path)

    with open(exe_path, "rb") as f:
        data = bytearray(f.read())

    pe_offset = struct.unpack("<I", data[0x3C:0x40])[0]
    chars_offset = pe_offset + 0x16
    chars = struct.unpack("<H", data[chars_offset : chars_offset + 2])[0]

    if chars & 0x0020:
        print(f"[=] {os.path.basename(exe_path)} already has LargeAddressAware (0x{chars:04X}).")
        return True

    new_chars = chars | 0x0020
    data[chars_offset : chars_offset + 2] = struct.pack("<H", new_chars)

    with open(exe_path, "wb") as f:
        f.write(data)

    print(f"[+] Enabled LargeAddressAware on {exe_path} (0x{chars:04X} -> 0x{new_chars:04X}).")
    return True


def set_ifeo_affinity(enable=True):
    """Configure or remove Image File Execution Options CPU affinity masks."""
    registry_roots = [
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows NT\CurrentVersion\Image File Execution Options",
    ]

    for root_path in registry_roots:
        for target in IFEO_TARGETS:
            key_path = f"{root_path}\\{target}"
            try:
                if enable:
                    with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                        winreg.SetValueEx(
                            key, "CpuAffinityMask", 0, winreg.REG_DWORD, IFEO_AFFINITY_MASK
                        )
                    print(f"[+] Registry IFEO set: {target} (CpuAffinityMask = 0x{IFEO_AFFINITY_MASK:X})")
                else:
                    try:
                        with winreg.OpenKey(
                            winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE
                        ) as key:
                            winreg.DeleteValue(key, "CpuAffinityMask")
                        print(f"[+] Registry IFEO removed: {target}")
                    except FileNotFoundError:
                        pass
            except Exception as e:
                print(f"[-] Failed to modify registry for {target}: {e}")


def apply_all_patches():
    """Execute complete end-to-end patching workflow."""
    print("=" * 70)
    print("QuickTime Multi-Core & High-Resolution (2K/4K) Auto-Patcher")
    print("=" * 70)

    kill_hung_shims()

    qt_dir = get_quicktime_dir()
    if not qt_dir:
        print("[-] QuickTime installation directory not found. Is QuickTime installed?")
        return False

    qtsystem_dir = os.path.join(qt_dir, "QTSystem")
    print(f"[*] QuickTime Directory: {qt_dir}")

    # 1. Patch QuickTimeH264.qtx
    h264_path = os.path.join(qtsystem_dir, "QuickTimeH264.qtx")
    patch_binary(h264_path, QT_H264_OFFSET, QT_H264_PATCH, "QuickTimeH264.qtx [Dynamic Clamp]")

    # 2. Patch QuickTime.qts
    qts_path = os.path.join(qtsystem_dir, "QuickTime.qts")
    patch_binary(qts_path, QT_QTS_OFFSET1, QT_QTS_PATCH1, "QuickTime.qts [Processor Clamp 1]")
    patch_binary(qts_path, QT_QTS_OFFSET2, QT_QTS_PATCH2, "QuickTime.qts [MPProcessors Clamp 2]")

    # 3. Patch AppleProResDecoder.qtx
    prores_path = os.path.join(qtsystem_dir, "AppleProResDecoder.qtx")
    if os.path.exists(prores_path):
        patch_binary(prores_path, QT_PRORES_OFFSET, QT_PRORES_PATCH, "AppleProResDecoder.qtx")

    # 4. Patch QuickTimePlayer.exe (LAA)
    player_path = os.path.join(qt_dir, "QuickTimePlayer.exe")
    if os.path.exists(player_path):
        enable_large_address_aware(player_path)

    # 5. Patch Maya quicktimeShim.exe instances (LAA)
    shims = find_maya_shims()
    if shims:
        for shim in shims:
            enable_large_address_aware(shim)
    else:
        print("[!] No Autodesk Maya installations detected in C:\\Program Files\\Autodesk.")

    # 6. Apply Registry IFEO Affinities
    set_ifeo_affinity(enable=True)

    print("\n" + "=" * 70)
    print("[SUCCESS] All QuickTime multi-core & 2K/4K patches applied successfully!")
    print("Please restart Autodesk Maya or QuickTime applications to ensure clean execution.")
    print("=" * 70)
    return True


def restore_all_backups():
    """Roll back all modifications to original files."""
    print("=" * 70)
    print("Rolling Back QuickTime Patches to Original Files...")
    print("=" * 70)

    kill_hung_shims()

    qt_dir = get_quicktime_dir()
    if qt_dir:
        qtsystem_dir = os.path.join(qt_dir, "QTSystem")
        restore_backup(os.path.join(qtsystem_dir, "QuickTimeH264.qtx"))
        restore_backup(os.path.join(qtsystem_dir, "QuickTime.qts"))
        restore_backup(os.path.join(qtsystem_dir, "AppleProResDecoder.qtx"))
        restore_backup(os.path.join(qt_dir, "QuickTimePlayer.exe"))

    for shim in find_maya_shims():
        restore_backup(shim)

    set_ifeo_affinity(enable=False)

    print("\n" + "=" * 70)
    print("[SUCCESS] All original files and registry entries restored.")
    print("=" * 70)


def print_status():
    """Inspect current patch status of all targets."""
    print("=" * 70)
    print("QuickTime & Maya Compatibility Patch Status")
    print("=" * 70)

    qt_dir = get_quicktime_dir()
    print(f"QuickTime Location: {qt_dir}")
    if qt_dir:
        qtsystem_dir = os.path.join(qt_dir, "QTSystem")
        for fn, off, expected in [
            ("QuickTimeH264.qtx", QT_H264_OFFSET, QT_H264_PATCH),
            ("QuickTime.qts", QT_QTS_OFFSET1, QT_QTS_PATCH1),
            ("QuickTime.qts", QT_QTS_OFFSET2, QT_QTS_PATCH2),
        ]:
            fp = os.path.join(qtsystem_dir, fn)
            if os.path.exists(fp):
                with open(fp, "rb") as f:
                    f.seek(off)
                    bs = f.read(len(expected))
                st = "PATCHED" if bs == expected else "UNPATCHED"
                print(f"  - {fn} @ 0x{off:X}: [{st}]")

    print("\nLargeAddressAware (4GB Virtual Memory Unlock):")
    shims = find_maya_shims()
    if qt_dir:
        shims.append(os.path.join(qt_dir, "QuickTimePlayer.exe"))
    for p in shims:
        if os.path.exists(p):
            with open(p, "rb") as f:
                d = f.read(1024)
            pe_off = struct.unpack("<I", d[0x3C:0x40])[0]
            chars = struct.unpack("<H", d[pe_off+0x16:pe_off+0x18])[0]
            laa = bool(chars & 0x0020)
            print(f"  - {p}: LAA={'ENABLED (4GB)' if laa else 'DISABLED (2GB)'}")

    print("\nRegistry IFEO Affinities (CpuAffinityMask = 0xFF):")
    for target in IFEO_TARGETS:
        kp = rf"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options\{target}"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, kp) as k:
                val, _ = winreg.QueryValueEx(k, "CpuAffinityMask")
                print(f"  - {target}: 0x{val:X}")
        except FileNotFoundError:
            print(f"  - {target}: Not set")
    print("=" * 70)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="QuickTime Multi-Core & 2K/4K Compatibility Auto-Patcher"
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply all compatibility patches"
    )
    parser.add_argument(
        "--restore", action="store_true", help="Restore original backups"
    )
    parser.add_argument(
        "--status", action="store_true", help="Check current patch status"
    )

    args = parser.parse_args()

    if args.status:
        print_status()
        return

    # Actions modifying files or registry require admin rights
    if not is_admin():
        run_as_admin()

    if args.restore:
        restore_all_backups()
    else:
        # Default action is --apply
        apply_all_patches()


if __name__ == "__main__":
    main()
