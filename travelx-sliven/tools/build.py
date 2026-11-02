"""Packages the page as a WordPress plugin zip.

    python tools/build.py

Bump TXS_VERSION in wordpress/travelx-sliven.php before building an update —
WordPress republishes /sliven/ only when the version changes. Upload the zip
under Plugins → Add New → Upload Plugin ("Replace current with uploaded").
"""
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "travelx-sliven.php"
SITE = [ROOT / "index.html", ROOT / ".htaccess",
        *sorted(p for p in (ROOT / "assets").rglob("*") if p.is_file())]

php = PLUGIN.read_text(encoding="utf-8")
version = re.search(r"const TXS_VERSION\s*=\s*'([^']+)'", php).group(1)
php = re.sub(r"(\* Version:\s*)\S+", rf"\g<1>{version}", php, count=1)

out = ROOT / "dist" / f"travelx-sliven-{version}.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("travelx-sliven/travelx-sliven.php", php)
    for p in SITE:
        z.write(p, "travelx-sliven/site/" + p.relative_to(ROOT).as_posix())

print(f"{out.relative_to(ROOT).as_posix()}  {out.stat().st_size / 1024:.0f} KB  "
      f"({len(SITE)} site files, v{version})")
