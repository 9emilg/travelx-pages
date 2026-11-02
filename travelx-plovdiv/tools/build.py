"""Packages the page as a WordPress plugin zip.

    python tools/build.py

Regenerates the Bulgarian page (bg/index.html, via tools/i18n.py) first and
stops if any English string lacks a translation in content/bg.json.

Bump TXPV_VERSION in wordpress/travelx-plovdiv.php before building an update —
WordPress republishes /plovdiv/ only when the version changes. Upload the zip
under Plugins → Add New → Upload Plugin ("Replace current with uploaded").
"""
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "wordpress" / "travelx-plovdiv.php"

# the Bulgarian page is generated, never edited: rebuild it from index.html
if subprocess.run([sys.executable, str(ROOT / "tools" / "i18n.py")]).returncode:
    sys.exit("build: stopped — fix the i18n problems above (content/bg.json)")

SITE = [ROOT / "index.html", ROOT / "bg" / "index.html", ROOT / ".htaccess",
        *sorted(p for p in (ROOT / "assets").rglob("*")
                if p.is_file() and not any(part.startswith("_") for part in p.relative_to(ROOT).parts))]
# assets/_raw and assets/_legacy-* are working files, never shipped

php = PLUGIN.read_text(encoding="utf-8")
version = re.search(r"const TXPV_VERSION\s*=\s*'([^']+)'", php).group(1)
php = re.sub(r"(\* Version:\s*)\S+", rf"\g<1>{version}", php, count=1)

out = ROOT / "dist" / f"travelx-plovdiv-{version}.zip"
out.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("travelx-plovdiv/travelx-plovdiv.php", php)
    for p in SITE:
        z.write(p, "travelx-plovdiv/site/" + p.relative_to(ROOT).as_posix())

print(f"{out.relative_to(ROOT).as_posix()}  {out.stat().st_size / 1024:.0f} KB  "
      f"({len(SITE)} site files, v{version})")
