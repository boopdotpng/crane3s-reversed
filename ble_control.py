import asyncio, random
from bleak import BleakScanner, BleakClient

WRITE_UUID  = "d44bc439-abfd-45a2-b575-925416129600"
NOTIFY_UUID = "d44bc439-abfd-45a2-b575-925416129601"
DEVICE_NAME = "CRANE 3-S_F67F"

HEADER = bytes((0x24, 0x3C, 0x08, 0x00))
CMD    = bytes((0x18, 0x12))

def crc16(buf: bytes) -> int:
    crc = 0
    for b in buf:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc

def encode(v: float) -> int:
    """-1.0 … +1.0  ->  0x0000 … 0x0FFF  with centre 0x0800"""
    v = max(-1.0, min(1.0, v))
    return 2048 + int(v * 2047)

def build(seq: int, axis_id: int, value: int) -> bytes:
    pl = CMD + bytes((seq & 0xFF, 0x01, axis_id, 0x10,
                      value & 0xFF, (value >> 8) & 0xFF))
    crc = crc16(pl).to_bytes(2, "little")
    return HEADER + pl + crc

async def find_crane3s():
    print("🔍 Scanning for Crane 3s...")
    devices = await BleakScanner.discover()
    for d in devices:
        if d.name == DEVICE_NAME:
            print(f"✅ Found {DEVICE_NAME}: {d.address}")
            return d.address
    raise RuntimeError("❌ 'Crane 3s' not found")

async def stream(client, pan_speed=0.0, tilt_speed=0.0,
                 duration=1.0, rate=25, verbose=False):
    dt = 1.0 / rate
    ticks = int(duration * rate)
    seq = random.randint(0, 250)

    pan_val  = encode(pan_speed)
    tilt_val = encode(tilt_speed)
    centre   = 0x0800

    for _ in range(ticks):
        for axis, val in ((0x01, tilt_val), (0x02, centre), (0x03, pan_val)):
            pkt = build(seq, axis, val)
            if verbose:
                print(f"SEQ {seq:02X} AXIS {axis} VAL {val:04X} ->",
                      pkt.hex(" "))
            await client.write_gatt_char(WRITE_UUID, pkt, response=False)
            seq = (seq + 1) & 0xFF
        await asyncio.sleep(dt)

    # clean stop
    for axis in (0x01, 0x02, 0x03):
        pkt = build(seq, axis, 0x0800)
        await client.write_gatt_char(WRITE_UUID, pkt, response=False)
        seq = (seq + 1) & 0xFF

async def main():
    address = await find_crane3s()
    async with BleakClient(address) as c:
        if not c.is_connected:
            print("❌ connect fail"); return
        await c.start_notify(NOTIFY_UUID,
                             lambda _, d: print("<-", d.hex(":")))

        await stream(c, pan_speed=+0.9, duration=1.0, verbose=True)
        await asyncio.sleep(0.5)
        await stream(c, pan_speed=-0.9, duration=1.0, verbose=True)
        await stream(c, tilt_speed=+0.8, duration=1.0)
        await asyncio.sleep(0.5)
        await stream(c, tilt_speed=-0.8, duration=1.0)

if __name__ == "__main__":
    asyncio.run(main())
