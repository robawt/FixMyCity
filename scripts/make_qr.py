"""Generate the demo QR code (PNG, dependency-light) for the golden-path entry point.
Usage: uv run python scripts/make_qr.py "http://192.168.0.22:8000/?site=HACKATHON-BOOTH-1"
Writes docs/demo-qr.png and prints an ASCII preview.
"""
import os
import struct
import sys
import zlib

import qrcode

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "demo-qr.png")


def chunk(kind: bytes, data: bytes) -> bytes:
    return (struct.pack(">I", len(data)) + kind + data +
            struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))


def make_png(payload: str, scale: int = 6, border: int = 4) -> bytes:
    qr = qrcode.QRCode(version=None, box_size=1, border=border,
                       error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(payload)
    qr.make(fit=True)
    matrix = qr.get_matrix()
    h, w = len(matrix) * scale, len(matrix[0]) * scale
    raw = bytearray()
    for row in matrix:
        pixels = bytearray()
        for dark in row:
            pixels.extend((0 if dark else 255,) * scale)
        for _ in range(scale):
            raw.append(0)
            raw.extend(pixels)
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) +
            chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b""))


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/?site=HACKATHON-BOOTH-1"
    data = make_png(url)
    with open(OUT, "wb") as fh:
        fh.write(data)
    print("QR ->", url)
    print("PNG ->", OUT)

    qr = qrcode.QRCode(version=None, box_size=1, border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


if __name__ == "__main__":
    main()
