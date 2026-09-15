"""One-off: download the three typefaces (latin subset, woff2) for local static serving."""

import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

FAMILIES = {
    "BodoniModa": "Bodoni+Moda:opsz,wght@6..96,400..900",
    "BodoniModa-Italic": "Bodoni+Moda:ital,opsz,wght@1,6..96,400..900",
    "SchibstedGrotesk": "Schibsted+Grotesk:wght@400..900",
    "SchibstedGrotesk-Italic": "Schibsted+Grotesk:ital,wght@1,400..900",
    "FragmentMono": "Fragment+Mono",
    "FragmentMono-Italic": "Fragment+Mono:ital@1",
}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
out = Path(__file__).resolve().parent.parent / "static" / "fonts"
out.mkdir(parents=True, exist_ok=True)

for name, spec in FAMILIES.items():
    css = urlopen(Request(f"https://fonts.googleapis.com/css2?family={spec}&display=swap", headers={"User-Agent": UA})).read().decode()
    blocks = re.findall(r"/\* (\w+) \*/\s*@font-face \{(.*?)\}", css, re.S)
    latin = [b for b in blocks if b[0] == "latin"]
    if not latin:
        print("no latin block for", name, file=sys.stderr)
        sys.exit(1)
    url = re.search(r"url\((https://[^)]+\.woff2)\)", latin[0][1]).group(1)
    data = urlopen(Request(url, headers={"User-Agent": UA})).read()
    (out / f"{name}.woff2").write_bytes(data)
    print(f"{name:26s} {len(data):7d} bytes  {url[-40:]}")
