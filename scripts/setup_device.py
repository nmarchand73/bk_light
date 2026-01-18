"""BLE device scanner and config updater for BK-Light LED panels."""

import argparse
import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config


async def scan_devices(timeout: float) -> list[tuple[str, str]]:
    """Scan for BLE devices with names starting with LED_BLE."""
    try:
        from bleak import BleakScanner
    except ImportError:
        print("Error: bleak is required. Install it with: pip install bleak")
        sys.exit(1)

    print(f"Scanning for BK-Light devices ({timeout:.0f}s)...")
    devices = await BleakScanner.discover(timeout=timeout)
    matches = []
    for device in devices:
        name = device.name or ""
        if name.startswith("LED_BLE"):
            matches.append((device.address, name))
    return sorted(matches, key=lambda x: x[1])


def prompt_selection(devices: list[tuple[str, str]]) -> tuple[str, str]:
    """Prompt user to select a device, or auto-select if only one found."""
    if len(devices) == 1:
        address, name = devices[0]
        print(f"\nFound 1 device: {address}  ({name})")
        print("Auto-selecting...")
        return address, name

    print(f"\nFound {len(devices)} device(s):")
    for i, (address, name) in enumerate(devices, start=1):
        print(f"  [{i}] {address}  ({name})")

    while True:
        try:
            choice = input(f"\nSelect device [1-{len(devices)}]: ").strip()
            index = int(choice) - 1
            if 0 <= index < len(devices):
                return devices[index]
            print(f"Please enter a number between 1 and {len(devices)}")
        except ValueError:
            print("Please enter a valid number")
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            sys.exit(0)


def update_config(config_path: Path, address: str) -> None:
    """Update config.yaml with the selected device address."""
    try:
        import yaml
    except ImportError:
        print("Error: PyYAML is required. Install it with: pip install PyYAML")
        sys.exit(1)

    if not config_path.exists():
        data = {}
    else:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    if "device" not in data:
        data["device"] = {}
    data["device"]["address"] = address

    if "panels" not in data:
        data["panels"] = {}
    if "list" not in data["panels"] or not data["panels"]["list"]:
        data["panels"]["list"] = [address]
    else:
        data["panels"]["list"][0] = address

    config_path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


async def main(config_path: Path, timeout: float | None) -> None:
    """Main entry point."""
    config = load_config(config_path if config_path.exists() else None)
    scan_timeout = timeout if timeout is not None else config.device.scan_timeout

    devices = await scan_devices(scan_timeout)

    if not devices:
        print("\nNo BK-Light devices found.")
        print("Make sure your LED panel is powered on and in range.")
        sys.exit(1)

    address, name = prompt_selection(devices)
    update_config(config_path, address)

    print(f"\nConfig updated! Device address set to: {address}")
    print("Run: python scripts/production.py")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scan for BK-Light LED panels and update config.yaml"
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config.yaml"),
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        help="Scan timeout in seconds (default: from config or 6s)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    asyncio.run(main(args.config, args.timeout))
