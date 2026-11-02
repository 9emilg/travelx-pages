"""Generates the Bulgarian page, bg/index.html, from index.html.

    python tools/i18n.py            write bg/index.html
    python tools/i18n.py --check    only verify; exit 1 if bg/index.html is missing or stale

index.html (English) is the only page anyone edits. This script copies it and
replaces what its hooks mark, using content/bg.json:

  data-i18n                    the element's text (inline HTML such as <em> is part of
                               the text; an icon <svg> at its start or end is kept)
  data-i18n-attr="alt href"    those attributes: "values" in bg.json first (URLs,
                               language codes), then "strings"; for a mailto: link
                               only the subject is translated
  data-i18n-json="a b.c"       those fields of the JSON-LD block
  <!--bg:...-->                markup that exists on the Bulgarian page only

The three program panels are swapped for content/program-bg.html, after
checking that the English panels still match content/program-en.html (both
come from tools/program.py). Asset URLs get a ../ prefix, since the page lives
one folder down.

It refuses to write anything, and exits 1 with a list, when a marked string has
no translation, when the program has changed, or when any Latin-script word
not listed under "keep" is left in the Bulgarian page's text or attributes —
which is also what catches new English that was added without a hook.
"""
import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "index.html"
OUT = ROOT / "bg" / "index.html"
DICT = ROOT / "content" / "bg.json"
PROG_EN = ROOT / "content" / "program-en.html"
PROG_BG = ROOT / "content" / "program-bg.html"

VOID = {"meta", "link", "img", "source", "br", "hr", "input"}
HOOK = re.compile(r'<([a-zA-Z][\w-]*)\b[^<>]*?\sdata-i18n(?:-attr|-json)?\b[^<>]*>')
EDGE = re.compile(r'^(\s*(?:<svg\b.*?</svg>\s*)?)(.*?)(\s*(?:<svg\b.*?</svg>)?\s*)$', re.S)
# attributes a reader or a screen reader meets; checked for leftover English
TEXT_ATTRS = ("alt", "aria-label", "aria-roledescription", "title", "placeholder", "data-meta", "data-label")
TEXT_META = {"description", "og:title", "og:description", "twitter:title", "twitter:description"}

errors = []


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def load():
    d = json.loads(DICT.read_text(encoding="utf-8"))
    strings = {norm(k): v for k, v in d["strings"].items() if not k.startswith("//")}
    return strings, d.get("values", {}), set(d.get("keep", []))


STRINGS, VALUES, KEEP = load()
used = set()


def tr(text, where):
    k = norm(text)
    if k in STRINGS:
        used.add(k)
        return STRINGS[k]
    errors.append("no translation  %-28s %s" % (where, k))
    return text


def tr_attr(name, value, where):
    if value in VALUES.get(name, {}):
        return VALUES[name][value]
    if name == "href" and value.startswith("mailto:") and "subject=" in value:
        head, subj = value.split("subject=", 1)
        return head + "subject=" + quote(html.unescape(tr(unquote(subj), where)), safe="")
    return tr(value, where)


def get_attr(tag, name):
    m = re.search(r'(?<=\s)%s="([^"]*)"' % re.escape(name), tag)
    return m


def close_of(s, name, pos):
    """Index of the </name> matching an element whose start tag ends at pos."""
    depth, rx = 1, re.compile(r'<(/?)%s\b[^>]*>' % re.escape(name), re.I)
    for m in rx.finditer(s, pos):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return m.start(), m.end()
    raise ValueError("no closing </%s>" % name)


def line_of(s, i):
    return "line %d" % (s.count("\n", 0, i) + 1)


def program(s):
    ols = list(re.finditer(r'<ol class="timeline">.*?</ol>', s, re.S))
    en = re.findall(r'<ol class="timeline">.*?</ol>', PROG_EN.read_text(encoding="utf-8"), re.S)
    bg = re.findall(r'<ol class="timeline">.*?</ol>', PROG_BG.read_text(encoding="utf-8"), re.S)
    squash = lambda x: re.sub(r">\s+<", "><", norm(x))
    if not (len(ols) == len(en) == len(bg) == 3):
        errors.append("program: expected 3 day panels in index.html, program-en.html and program-bg.html; found %d / %d / %d" % (len(ols), len(en), len(bg)))
        return s
    for i, (m, e) in enumerate(zip(ols, en)):
        if squash(m.group(0)) != squash(e):
            errors.append("program: day %d in index.html differs from content/program-en.html — update program-bg.html (tools/program.py) to match, then copy the English fragment in" % (i + 1))
    for m, b in reversed(list(zip(ols, bg))):
        indent = s[s.rfind("\n", 0, m.start()) + 1:m.start()]
        s = s[:m.start()] + b.replace("\n", "\n" + indent) + s[m.end():]
    return s


def hooks(s):
    for m in reversed(list(HOOK.finditer(s))):
        tag, name, where = m.group(0), m.group(1).lower(), line_of(s, m.start())
        new = tag
        # attributes
        a = get_attr(tag, "data-i18n-attr")
        if a:
            for attr in a.group(1).split():
                v = get_attr(new, attr)
                if not v:
                    errors.append("missing attribute %s on <%s> (%s)" % (attr, name, where)); continue
                t = tr_attr(attr, v.group(1), "%s [%s]" % (where, attr))
                new = new[:v.start(1)] + t.replace('"', "&quot;") + new[v.end(1):]
        new = re.sub(r'\sdata-i18n(?:-attr|-json)?(?:="[^"]*")?', "", new)
        end = m.end()
        # JSON-LD fields
        j = get_attr(tag, "data-i18n-json")
        if j:
            c0, c1 = close_of(s, name, end)
            data = json.loads(s[end:c0])
            for path in j.group(1).split():
                keys, obj = path.split("."), data
                for k in keys[:-1]:
                    obj = obj[k]
                v = obj[keys[-1]]
                obj[keys[-1]] = VALUES.get(keys[-1], {}).get(v) or tr(v, "%s [json %s]" % (where, path))
            s = s[:m.start()] + new + "\n" + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n" + s[c0:]
            continue
        # element text
        if re.search(r'\sdata-i18n(?:\s|>|=)', tag):
            if name in VOID:
                errors.append("data-i18n on a void <%s> (%s)" % (name, where)); continue
            c0, _ = close_of(s, name, end)
            inner = s[end:c0]
            if "data-i18n" in inner:
                errors.append("nested data-i18n inside <%s> (%s): mark the inner elements only" % (name, where)); continue
            lead, mid, trail = EDGE.match(inner).groups()
            ws = re.match(r"\s*", mid).group(0), mid[len(mid.rstrip()):]
            inner = lead + ws[0] + tr(mid, where) + ws[1] + trail
            s = s[:m.start()] + new + inner + s[c0:]
        else:
            s = s[:m.start()] + new + s[end:]
    return s


class Leftovers(HTMLParser):
    """Collects every Latin-script word outside "keep" in the page's text and
    reader-facing attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip, self.found = 0, []

    def check(self, text, where):
        bad = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", text) if w not in KEEP]
        if bad:
            self.found.append("%-12s %-34s %s" % (where, " ".join(dict.fromkeys(bad)), norm(text)[:90]))

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self.skip += 1
        where = "line %d" % self.getpos()[0]
        for k in TEXT_ATTRS:
            if a.get(k):
                self.check(a[k], where + " " + k)
        if tag == "meta" and (a.get("name") in TEXT_META or a.get("property") in TEXT_META):
            self.check(a.get("content", ""), where + " meta")
        if tag == "a" and (a.get("href") or "").startswith("mailto:") and "subject=" in a["href"]:
            self.check(unquote(a["href"].split("subject=", 1)[1]), where + " subject")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.check(data, "line %d" % self.getpos()[0])


def build():
    s = SRC.read_text(encoding="utf-8")
    s = hooks(s)      # first, so reported line numbers are index.html's
    s = program(s)
    s = re.sub(r"<!--bg:(.*?)-->", r"\1", s, flags=re.S)
    s = re.sub(r'(?<=["\'\s(,])assets/', "../assets/", s)
    s = s.replace("<!DOCTYPE html>\n", "<!DOCTYPE html>\n<!-- GENERATED by tools/i18n.py from index.html + content/bg.json. Do not edit: edit those and rebuild. -->\n", 1)
    p = Leftovers(); p.feed(s)
    errors.extend("English left     " + f for f in p.found)
    return s


def main():
    s = build()
    unused = sorted(set(STRINGS) - used)
    if unused:
        print("i18n: %d unused entr%s in content/bg.json (safe to delete once nothing needs them):" % (len(unused), "y" if len(unused) == 1 else "ies"))
        for k in unused:
            print("   ", k)
    if errors:
        print("i18n: FAILED — bg/index.html not written. %d problem(s):" % len(errors), file=sys.stderr)
        for e in errors:
            print("   ", e, file=sys.stderr)
        sys.exit(1)
    if "--check" in sys.argv:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != s:
            print("i18n: bg/index.html is stale — run python tools/i18n.py", file=sys.stderr); sys.exit(1)
        print("i18n: bg/index.html is up to date"); return
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(s, encoding="utf-8", newline="\n")
    print("i18n: bg/index.html  %d strings, %.0f KB" % (len(used), OUT.stat().st_size / 1024))


if __name__ == "__main__":
    main()
