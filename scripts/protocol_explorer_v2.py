"""Protocol Explorer v2 - Focus on animation/GIF modes discovered.

Tests the mode byte (position 7) and chunked data transfer.
"""

import argparse
import asyncio
import binascii
import sys
from pathlib import Path

from bleak import BleakClient, BleakScanner

project_root = Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from bk_light.config import load_config

UUID_WRITE = "0000fa02-0000-1000-8000-00805f9b34fb"
UUID_NOTIFY = "0000fa03-0000-1000-8000-00805f9b34fb"

responses = []


def hex_dump(data: bytes, max_len: int = 50) -> str:
    """Format bytes as hex dump."""
    if len(data) > max_len:
        hex_str = " ".join(f"{b:02X}" for b in data[:max_len]) + f" ... ({len(data)} bytes)"
    else:
        hex_str = " ".join(f"{b:02X}" for b in data)
    return hex_str


def notification_handler(sender: int, data: bytearray) -> None:
    payload = bytes(data)
    responses.append(payload)
    print(f"  <- {hex_dump(payload)}")


async def send_and_wait(client: BleakClient, data: bytes, label: str, wait: float = 0.5) -> list[bytes]:
    responses.clear()
    print(f"  -> [{label}] {hex_dump(data)}")
    try:
        await client.write_gatt_char(UUID_WRITE, data, response=False)
    except Exception as e:
        print(f"     ERROR: {e}")
    await asyncio.sleep(wait)
    return list(responses)


async def test_animation_modes(client: BleakClient) -> None:
    """Test the discovered animation mode bytes."""
    print("\n" + "="*60)
    print("TESTING ANIMATION MODES (byte 7 of handshake)")
    print("="*60)

    # Test modes 0-10 in the handshake
    for mode in range(11):
        print(f"\n[Mode {mode}]")
        handshake = bytes.fromhex(f"08 00 01 80 0E 06 32 {mode:02X}")
        resp = await send_and_wait(client, handshake, f"HANDSHAKE mode={mode}")

        if resp:
            # Check if response echoes the mode
            if len(resp[0]) >= 8 and resp[0][7] == mode:
                print(f"     Mode {mode} ACCEPTED (echoed back)")


async def test_frame_count_announcement(client: BleakClient) -> None:
    """Test announcing frame count before sending."""
    print("\n" + "="*60)
    print("TESTING FRAME COUNT ANNOUNCEMENT")
    print("="*60)

    # Standard handshake first
    await send_and_wait(client, bytes.fromhex("08 00 01 80 0E 06 32 00"), "HANDSHAKE")

    # Try different ways to announce frame count
    for count in [5, 10]:
        print(f"\n[Announcing {count} frames]")

        # Format 1: Extra bytes after standard handshake
        await send_and_wait(client, bytes.fromhex(f"0A 00 01 80 0E 06 32 00 {count:02X} 00"), f"format1 count={count}")

        # Format 2: Using message type 0x03 (returned different response earlier)
        await send_and_wait(client, bytes.fromhex(f"05 00 03 80 {count:02X}"), f"format2 type=0x03 count={count}")

        # Format 3: Using message type 0x04
        await send_and_wait(client, bytes.fromhex(f"05 00 04 80 {count:02X}"), f"format3 type=0x04 count={count}")


async def test_chunked_gif(client: BleakClient, gif_path: Path) -> None:
    """Test sending GIF in chunks."""
    print("\n" + "="*60)
    print("TESTING CHUNKED GIF TRANSFER")
    print("="*60)

    gif_data = gif_path.read_bytes()
    print(f"GIF size: {len(gif_data)} bytes")

    # Test 1: Try animation mode handshake first
    print("\n[Test 1: Animation mode (0x01) then GIF header]")
    await send_and_wait(client, bytes.fromhex("08 00 01 80 0E 06 32 01"), "HANDSHAKE mode=1")
    await send_and_wait(client, bytes.fromhex("04 00 05 80"), "HANDSHAKE2")

    # Send just the GIF header (first 128 bytes) to see response
    gif_header = gif_data[:128]
    frame = build_frame(gif_header, opcode=0x02)
    await send_and_wait(client, frame, "GIF header only", wait=1.0)

    # Test 2: Try with opcode 0x03
    print("\n[Test 2: Opcode 0x03 for animation?]")
    await send_and_wait(client, bytes.fromhex("08 00 01 80 0E 06 32 01"), "HANDSHAKE mode=1")
    await send_and_wait(client, bytes.fromhex("04 00 05 80"), "HANDSHAKE2")

    frame = build_frame(gif_header, opcode=0x03)
    await send_and_wait(client, frame, "GIF header opcode=0x03", wait=1.0)

    # Test 3: Send GIF in chunks with frame index
    print("\n[Test 3: Chunked transfer with frame index in footer]")
    chunk_size = 400  # Safe size for BLE
    chunks = [gif_data[i:i+chunk_size] for i in range(0, min(len(gif_data), 2000), chunk_size)]

    await send_and_wait(client, bytes.fromhex("08 00 01 80 0E 06 32 01"), "HANDSHAKE mode=1")
    await send_and_wait(client, bytes.fromhex("04 00 05 80"), "HANDSHAKE2")

    for i, chunk in enumerate(chunks):
        # Try frame index in footer byte
        frame = build_frame_indexed(chunk, frame_index=i, total_frames=len(chunks))
        await send_and_wait(client, frame, f"chunk {i+1}/{len(chunks)}", wait=0.5)


def build_frame(data: bytes, opcode: int = 0x02) -> bytes:
    """Build a frame with specified opcode."""
    data_length = len(data)
    total_length = data_length + 15
    frame = bytearray()
    frame += total_length.to_bytes(2, "little")
    frame.append(opcode)
    frame += b"\x00\x00"
    frame += data_length.to_bytes(2, "little")
    frame += b"\x00\x00"
    frame += binascii.crc32(data).to_bytes(4, "little")
    frame += b"\x00\x65"
    frame += data
    return bytes(frame)


def build_frame_indexed(data: bytes, frame_index: int, total_frames: int, opcode: int = 0x02) -> bytes:
    """Build a frame with index info in footer."""
    data_length = len(data)
    total_length = data_length + 15
    frame = bytearray()
    frame += total_length.to_bytes(2, "little")
    frame.append(opcode)
    frame += b"\x00\x00"
    frame += data_length.to_bytes(2, "little")
    frame += b"\x00\x00"
    frame += binascii.crc32(data).to_bytes(4, "little")
    # Try frame index and total in footer
    frame.append(frame_index)
    frame.append(total_frames)
    frame += data
    return bytes(frame)


async def test_multi_frame_protocol(client: BleakClient, gif_path: Path) -> None:
    """Test multi-frame protocol with small PNG frames."""
    print("\n" + "="*60)
    print("TESTING MULTI-FRAME PROTOCOL")
    print("="*60)

    from PIL import Image
    from io import BytesIO

    # Load GIF and extract first 3 frames as PNGs
    gif = Image.open(gif_path)
    frames = []
    for i in range(min(3, getattr(gif, 'n_frames', 1))):
        gif.seek(i)
        buffer = BytesIO()
        gif.convert("RGB").resize((32, 32)).save(buffer, format="PNG", optimize=True)
        frames.append(buffer.getvalue())

    print(f"Extracted {len(frames)} frames")

    # Test 1: Announce frames then send
    print("\n[Test 1: Announce frame count, then send frames]")

    # Try announcing with mode byte
    await send_and_wait(client, bytes.fromhex(f"08 00 01 80 0E 06 32 {len(frames):02X}"), f"HANDSHAKE frames={len(frames)}")
    await send_and_wait(client, bytes.fromhex("04 00 05 80"), "HANDSHAKE2")

    for i, png_data in enumerate(frames):
        print(f"\n  Frame {i+1}/{len(frames)} ({len(png_data)} bytes)")
        frame = build_frame(png_data, opcode=0x02)
        await send_and_wait(client, frame, f"frame {i+1}", wait=0.3)

    # Test 2: Use footer for frame index
    print("\n[Test 2: Frame index in reserved bytes]")
    await send_and_wait(client, bytes.fromhex("08 00 01 80 0E 06 32 00"), "HANDSHAKE")
    await send_and_wait(client, bytes.fromhex("04 00 05 80"), "HANDSHAKE2")

    for i, png_data in enumerate(frames):
        # Put frame index in the reserved bytes (positions 3-4)
        data_length = len(png_data)
        total_length = data_length + 15
        frame = bytearray()
        frame += total_length.to_bytes(2, "little")
        frame.append(0x02)
        frame.append(i)  # Frame index
        frame.append(len(frames))  # Total frames
        frame += data_length.to_bytes(2, "little")
        frame += b"\x00\x00"
        frame += binascii.crc32(png_data).to_bytes(4, "little")
        frame += b"\x00\x65"
        frame += png_data

        await send_and_wait(client, bytes(frame), f"indexed frame {i+1}", wait=0.3)


async def interactive_test(client: BleakClient) -> None:
    """Interactive mode for custom testing."""
    print("\n" + "="*60)
    print("INTERACTIVE MODE")
    print("="*60)
    print("Commands:")
    print("  h1        - Standard handshake")
    print("  h2        - Second handshake")
    print("  m<N>      - Handshake with mode N (e.g., m1, m2)")
    print("  <hex>     - Send raw hex bytes")
    print("  quit      - Exit")
    print()

    while True:
        try:
            cmd = input(">>> ").strip().lower()
            if cmd == 'quit':
                break
            elif cmd == 'h1':
                await send_and_wait(client, bytes.fromhex("08 00 01 80 0E 06 32 00"), "HANDSHAKE")
            elif cmd == 'h2':
                await send_and_wait(client, bytes.fromhex("04 00 05 80"), "HANDSHAKE2")
            elif cmd.startswith('m') and len(cmd) > 1:
                mode = int(cmd[1:])
                await send_and_wait(client, bytes.fromhex(f"08 00 01 80 0E 06 32 {mode:02X}"), f"HANDSHAKE mode={mode}")
            elif cmd:
                try:
                    data = bytes.fromhex(cmd.replace("-", " ").replace(":", " "))
                    await send_and_wait(client, data, "CUSTOM")
                except ValueError:
                    print("Invalid hex")
        except EOFError:
            break


async def run_explorer(address: str, gif_path: Path = None, interactive: bool = False) -> None:
    print(f"Connecting to {address}...")

    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if not device:
        print(f"Device not found")
        return

    async with BleakClient(device) as client:
        print(f"Connected!\n")
        await client.start_notify(UUID_NOTIFY, notification_handler)

        if interactive:
            await interactive_test(client)
        else:
            await test_animation_modes(client)
            await test_frame_count_announcement(client)

            if gif_path and gif_path.exists():
                await test_chunked_gif(client, gif_path)
                await test_multi_frame_protocol(client, gif_path)

        await client.stop_notify(UUID_NOTIFY)

    print("\nDone.")


def parse_args():
    parser = argparse.ArgumentParser(description="Protocol Explorer v2")
    parser.add_argument("--address", help="Device address")
    parser.add_argument("--config", type=Path, help="Config file")
    parser.add_argument("--gif", type=Path, help="GIF file")
    parser.add_argument("-i", "--interactive", action="store_true", help="Interactive mode")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    address = args.address
    if not address:
        config = load_config(args.config)
        address = config.device.address

    if not address:
        print("No address configured")
        sys.exit(1)

    try:
        asyncio.run(run_explorer(address, args.gif, args.interactive))
    except KeyboardInterrupt:
        print("\nAborted.")
