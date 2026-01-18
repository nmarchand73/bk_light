"""Protocol Explorer - Test different opcodes and commands for BK-Light devices.

Use this script to reverse engineer the BLE protocol and discover hidden features
like native GIF/animation support.
"""

import argparse
import asyncio
import binascii
import sys
from pathlib import Path
from typing import Optional

from bleak import BleakClient, BleakScanner
from bleak.exc import BleakError

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config

UUID_WRITE = "0000fa02-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "0000fa03-0000-1000-8000-00805f9b34fb"

# Known handshakes
HANDSHAKE_FIRST = bytes.fromhex("08 00 01 80 0E 06 32 00")
HANDSHAKE_SECOND = bytes.fromhex("04 00 05 80")

# Response collector
responses = []


def hex_dump(data: bytes, prefix: str = "") -> str:
    """Format bytes as hex dump."""
    hex_str = " ".join(f"{b:02X}" for b in data)
    ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in data)
    return f"{prefix}{hex_str}  |{ascii_str}|"


def notification_handler(sender: int, data: bytearray) -> None:
    """Capture all notifications from device."""
    payload = bytes(data)
    responses.append(payload)
    print(f"  <- NOTIFY: {hex_dump(payload)}")


async def send_and_wait(client: BleakClient, data: bytes, label: str, wait: float = 1.0) -> list[bytes]:
    """Send data and collect responses."""
    responses.clear()
    print(f"  -> SEND [{label}]: {hex_dump(data)}")
    await client.write_gatt_char(UUID_WRITE, data, response=False)
    await asyncio.sleep(wait)
    return list(responses)


async def test_handshake_variations(client: BleakClient) -> None:
    """Test variations of the handshake."""
    print("\n" + "="*60)
    print("TESTING HANDSHAKE VARIATIONS")
    print("="*60)

    # Standard handshake
    print("\n[1] Standard HANDSHAKE_FIRST:")
    await send_and_wait(client, HANDSHAKE_FIRST, "HANDSHAKE_FIRST")

    # Try different bytes in position 4 (currently 0x0E)
    print("\n[2] Testing byte 4 variations (device mode?):")
    for mode in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x0F, 0x10, 0x20]:
        test = bytearray(HANDSHAKE_FIRST)
        test[4] = mode
        await send_and_wait(client, bytes(test), f"mode=0x{mode:02X}", wait=0.5)

    # Try different bytes in position 2 (message type?)
    print("\n[3] Testing byte 2 variations (message type?):")
    for msg_type in [0x00, 0x02, 0x03, 0x04, 0x05, 0x06]:
        test = bytearray(HANDSHAKE_FIRST)
        test[2] = msg_type
        await send_and_wait(client, bytes(test), f"type=0x{msg_type:02X}", wait=0.5)


async def test_frame_types(client: BleakClient) -> None:
    """Test different frame type opcodes."""
    print("\n" + "="*60)
    print("TESTING FRAME TYPE OPCODES")
    print("="*60)

    # Small test payload (8x8 red PNG would be ideal, but let's use minimal data)
    test_payload = b"TEST_DATA_12345678"

    for opcode in [0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x10, 0x20, 0x40, 0x80]:
        print(f"\n[Frame opcode 0x{opcode:02X}]")

        # Do standard handshake first
        await send_and_wait(client, HANDSHAKE_FIRST, "HANDSHAKE", wait=0.3)
        await send_and_wait(client, HANDSHAKE_SECOND, "HANDSHAKE2", wait=0.3)

        # Build frame with different opcode
        data_length = len(test_payload)
        total_length = data_length + 15
        frame = bytearray()
        frame += total_length.to_bytes(2, "little")
        frame.append(opcode)  # Frame type - testing different values
        frame += b"\x00\x00"
        frame += data_length.to_bytes(2, "little")
        frame += b"\x00\x00"
        frame += binascii.crc32(test_payload).to_bytes(4, "little")
        frame += b"\x00\x65"
        frame += test_payload

        await send_and_wait(client, bytes(frame), f"FRAME opcode=0x{opcode:02X}", wait=0.5)


async def test_raw_commands(client: BleakClient) -> None:
    """Test raw command sequences."""
    print("\n" + "="*60)
    print("TESTING RAW COMMANDS")
    print("="*60)

    # Commands to try (based on common BLE LED protocols)
    commands = [
        ("Clear/Reset?", bytes.fromhex("04 00 00 00")),
        ("Get Info?", bytes.fromhex("04 00 01 00")),
        ("Get Version?", bytes.fromhex("04 00 02 00")),
        ("Animation Mode?", bytes.fromhex("04 00 03 00")),
        ("Stop Animation?", bytes.fromhex("04 00 04 00")),
        ("Start Animation?", bytes.fromhex("04 00 05 00")),
        ("Set Brightness?", bytes.fromhex("05 00 06 00 FF")),
        ("GIF Mode?", bytes.fromhex("08 00 01 80 0E 06 32 01")),  # Last byte changed
        ("Multi-frame?", bytes.fromhex("08 00 01 80 0E 06 32 02")),
        ("Animation count?", bytes.fromhex("0A 00 01 80 0E 06 32 00 00 10")),  # Extra bytes
    ]

    for label, cmd in commands:
        print(f"\n[{label}]")
        await send_and_wait(client, cmd, label, wait=0.5)


async def test_gif_header(client: BleakClient, gif_path: Optional[Path] = None) -> None:
    """Test sending GIF data directly."""
    print("\n" + "="*60)
    print("TESTING GIF DATA")
    print("="*60)

    if gif_path and gif_path.exists():
        gif_data = gif_path.read_bytes()
        print(f"Loaded GIF: {len(gif_data)} bytes")

        # Try sending GIF with different frame types
        for opcode in [0x02, 0x03, 0x04, 0x05]:
            print(f"\n[GIF with opcode 0x{opcode:02X}]")

            # Handshake
            await send_and_wait(client, HANDSHAKE_FIRST, "HANDSHAKE", wait=0.3)
            await send_and_wait(client, HANDSHAKE_SECOND, "HANDSHAKE2", wait=0.3)

            # Build frame with GIF data
            data_length = len(gif_data)
            total_length = data_length + 15
            frame = bytearray()
            frame += total_length.to_bytes(2, "little")
            frame.append(opcode)
            frame += b"\x00\x00"
            frame += data_length.to_bytes(2, "little")
            frame += b"\x00\x00"
            frame += binascii.crc32(gif_data).to_bytes(4, "little")
            frame += b"\x00\x65"
            frame += gif_data

            await send_and_wait(client, bytes(frame), f"GIF frame", wait=2.0)
    else:
        print("No GIF file provided. Use --gif <path> to test GIF upload.")


async def test_multi_frame_sequence(client: BleakClient) -> None:
    """Test if there's a multi-frame/animation start command."""
    print("\n" + "="*60)
    print("TESTING MULTI-FRAME SEQUENCE")
    print("="*60)

    # Try announcing frame count before sending
    frame_counts = [2, 5, 10]

    for count in frame_counts:
        print(f"\n[Announcing {count} frames]")

        # Try different announcement formats
        announcements = [
            bytes.fromhex(f"05 00 01 80 {count:02X}"),
            bytes.fromhex(f"06 00 01 80 {count:02X} 00"),
            bytes.fromhex(f"08 00 01 80 0E 06 32 {count:02X}"),
            bytes.fromhex(f"09 00 01 80 0E 06 32 00 {count:02X}"),
        ]

        for i, announce in enumerate(announcements):
            await send_and_wait(client, announce, f"format {i+1}", wait=0.5)


async def test_footer_variations(client: BleakClient) -> None:
    """Test different footer bytes in frame."""
    print("\n" + "="*60)
    print("TESTING FOOTER VARIATIONS")
    print("="*60)

    test_payload = b"TEST"

    # Current footer is 0x00 0x65 - try others
    footers = [
        (0x00, 0x65),  # Current
        (0x00, 0x66),  # Animation?
        (0x00, 0x67),
        (0x01, 0x65),  # Frame index?
        (0x02, 0x65),
        (0x00, 0x00),
        (0xFF, 0xFF),
    ]

    for f1, f2 in footers:
        print(f"\n[Footer 0x{f1:02X} 0x{f2:02X}]")

        await send_and_wait(client, HANDSHAKE_FIRST, "HANDSHAKE", wait=0.3)
        await send_and_wait(client, HANDSHAKE_SECOND, "HANDSHAKE2", wait=0.3)

        data_length = len(test_payload)
        total_length = data_length + 15
        frame = bytearray()
        frame += total_length.to_bytes(2, "little")
        frame.append(0x02)
        frame += b"\x00\x00"
        frame += data_length.to_bytes(2, "little")
        frame += b"\x00\x00"
        frame += binascii.crc32(test_payload).to_bytes(4, "little")
        frame.append(f1)
        frame.append(f2)
        frame += test_payload

        await send_and_wait(client, bytes(frame), f"FRAME", wait=0.5)


async def interactive_mode(client: BleakClient) -> None:
    """Interactive mode to send custom commands."""
    print("\n" + "="*60)
    print("INTERACTIVE MODE")
    print("="*60)
    print("Enter hex bytes to send (e.g., '08 00 01 80 0E 06 32 00')")
    print("Commands: 'h1' = HANDSHAKE_FIRST, 'h2' = HANDSHAKE_SECOND")
    print("Type 'quit' to exit\n")

    while True:
        try:
            cmd = input(">>> ").strip()
            if cmd.lower() == 'quit':
                break
            elif cmd.lower() == 'h1':
                await send_and_wait(client, HANDSHAKE_FIRST, "HANDSHAKE_FIRST")
            elif cmd.lower() == 'h2':
                await send_and_wait(client, HANDSHAKE_SECOND, "HANDSHAKE_SECOND")
            elif cmd:
                try:
                    data = bytes.fromhex(cmd.replace("-", " "))
                    await send_and_wait(client, data, "CUSTOM")
                except ValueError:
                    print("Invalid hex format")
        except EOFError:
            break


async def run_explorer(address: str, gif_path: Optional[Path] = None, interactive: bool = False) -> None:
    """Main explorer routine."""
    print(f"Connecting to {address}...")

    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if not device:
        print(f"Device not found: {address}")
        return

    async with BleakClient(device) as client:
        print(f"Connected: {client.is_connected}")

        # Start notifications
        await client.start_notify(UUID_NOTIFY, notification_handler)
        print("Notification handler started\n")

        if interactive:
            await interactive_mode(client)
        else:
            await test_handshake_variations(client)
            await test_raw_commands(client)
            await test_frame_types(client)
            await test_footer_variations(client)
            await test_multi_frame_sequence(client)
            await test_gif_header(client, gif_path)

        await client.stop_notify(UUID_NOTIFY)

    print("\nExploration complete.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BK-Light Protocol Explorer")
    parser.add_argument("--address", help="Device BLE address")
    parser.add_argument("--config", type=Path, help="Config file")
    parser.add_argument("--gif", type=Path, help="GIF file to test upload")
    parser.add_argument("--interactive", "-i", action="store_true", help="Interactive mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    address = args.address
    if not address:
        config = load_config(args.config)
        address = config.device.address

    if not address:
        print("Error: No device address. Use --address or configure in config.yaml")
        sys.exit(1)

    try:
        asyncio.run(run_explorer(address, args.gif, args.interactive))
    except KeyboardInterrupt:
        print("\nAborted.")
