"""Generate the demo QR code (SVG, no Pillow) for the golden-path entry point.
Usage: uv run python scripts/make_qr.py "http://192.168.0.22:8000/?site=HACKATHON-BOOTH-1"
Writes docs/demo-qr.svg and prints an ASCII preview."""
import os
import sys

import qrcode
from qrcode.image.svg import SvgImage

OUT = os.path.join(os.path.dirname(__file__), "..", "docs", "demo-qr.svg")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/"
    img = qrcode.make(url, image_factory=SvgImage)
    img.save(OUT)
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.print_ascii(invert=True)
    print("QR ->", url)
    print("saved:", os.path.abspath(OUT))


if __name__ == "__main__":
    main()
