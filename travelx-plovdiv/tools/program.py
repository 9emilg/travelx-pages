"""Builds the program timeline (EN + BG) from content/TRAVEL_X_2027_Program.xlsx.

    python tools/program.py

Writes content/program-en.html and content/program-bg.html: the three day
panels' <ol class="timeline"> fragments. Rows are grouped by the sheet's
"ДЕН 1/2/3" headings, not by their date cells (several dates in the sheet
are off by a day). The "suitable participants" column is internal and is
never published; keyword lines are left out to keep the timeline readable.
"""
import html
import json
import re
import warnings
from pathlib import Path

import openpyxl

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "content" / "TRAVEL_X_2027_Program.xlsx"

# the sheet's format column → display label, per language
FORMAT = {
    "REGISTRATION": (None, None),  # the title already says it
    "OPENING": (None, None),
    "KEYNOTE PRESENTATION": ("Keynote", "Основна лекция"),
    "PAUSE": (None, None),
}
# rows whose whole text sits in the format column (breaks and evening events)
PLAIN = {
    "Coffee & Networking": ("Coffee &amp; Networking", "Кафе и нетуъркинг"),
    "Lunch": ("Lunch break", "Обяд"),
    "TravelX Welcome Reception Party & Networking": ("TravelX Welcome Reception Party &amp; Networking", "TravelX парти за добре дошли и нетуъркинг"),
    "TRAVEL X Official Cocktail & Awards": ("TravelX Official Cocktail &amp; Awards", "Официален коктейл на TravelX и награди"),
}
# corrections to the sheet's copy
FIX_EN = {
    "AI Is Changing Travel. How does it affects the industry?": "AI Is Changing Travel. How Does It Affect the Industry?",
    "The Data Language of a Destination You Can’t Manage What You Don’t Measure": "The Data Language of a Destination: You Can’t Manage What You Don’t Measure",
    "Finding a Common Voice:\nThe Identity of a Destination\nPlovdiv presents its new city branding strategy": "Finding a Common Voice: The Identity of a Destination",
}
FIX_BG = {
    "Езикът на данните в една дестинация - Не можеш да управляваш това, което не измерваш": "Езикът на данните в една дестинация: не можеш да управляваш това, което не измерваш",
}
# the sheet's BG opening description is cut short; the EN one, translated
BG_DESC = {
    "Official Opening": "Официално откриване на TravelX 2027 с участието на представители на Министерството на туризма, Община Пловдив и TravelX.",
}
LEAD = {  # a line shown before the description
    "Finding a Common Voice: The Identity of a Destination": ("Plovdiv presents its new city branding strategy.", "Пловдив представя новата си стратегия за градски бранд."),
}


def clean(v):
    return re.sub(r"\s+", " ", str(v)).strip() if v not in (None, "") else ""


def times(t):
    t = clean(t).replace(".", ":").replace("—", "–")
    a, b = re.split(r"\s*[-–]\s*", t)
    fmt = lambda x: "%02d:%s" % (int(x.split(":")[0]), x.split(":")[1])
    return "%s – %s" % (fmt(a), fmt(b))


def fmt_label(f, lang):
    f = clean(f)
    m = re.match(r"PANEL (\d+)", f)
    if m:
        return ("Panel %s" % m.group(1), "Панел %s" % m.group(1))[lang]
    return FORMAT.get(f, (f.title(), f.title()))[lang]


rows = list(openpyxl.load_workbook(SRC, data_only=True).worksheets[0].iter_rows(values_only=True))
days, day = {1: [], 2: [], 3: []}, None
for r in rows:
    first = clean(r[0])
    m = re.match(r"ДЕН (\d)", first)
    if m:
        day = int(m.group(1)); continue
    if not day or not clean(r[1]):
        continue
    days[day].append(r)

out = {0: [], 1: []}
for lang in (0, 1):
    for d in (1, 2, 3):
        items = []
        for r in days[d]:
            _, t, f, en, bg, _kw, _kwbg, den, dbg, _who = (list(r) + [None] * 10)[:10]
            f, en, bg = clean(f), (en or "").strip(), clean(bg)
            if f == "REGISTRATION":
                items.append('<li class="slot slot--break"><span class="slot__time">%s</span><span class="slot__title">%s</span></li>' % (times(t), html.escape((en, bg)[lang], quote=False)))
                continue
            if f.rstrip() in PLAIN or (f == "PAUSE"):
                label = PLAIN.get(f.rstrip(), ("Lunch break", "Обяд"))[lang]
                items.append('<li class="slot slot--break"><span class="slot__time">%s</span><span class="slot__title">%s</span></li>' % (times(t), label))
                continue
            if d == 3 and "CITY TOUR" in en:  # the sheet splits this one across three rows
                k = ("Exclusive city tour", "Ексклузивен тур")[lang]
                title = ("The Living City: A Journey Through the Ages", "Живият град: пътуване през епохите")[lang]
                desc = ("An immersive exploration of Plovdiv’s history with an audio guide. Pre-registration required.",
                        "Потапящо пътешествие през историята на Пловдив с аудиогид. С предварително записване.")[lang]
            else:
                en = FIX_EN.get(en, clean(en))
                title = (en, FIX_BG.get(bg, bg))[lang]
                k = fmt_label(f, lang)
                desc = (clean(den), BG_DESC.get(en, clean(dbg)))[lang]
                lead = LEAD.get(en)
                if lead:
                    desc = lead[lang] + " " + desc
            kk = '<b class="k">%s</b><i>|</i>' % html.escape(k) if k else ""
            dd = '<span class="slot__desc">%s</span>' % html.escape(desc, quote=False) if desc else ""
            items.append('<li class="slot"><span class="slot__time">%s</span><span class="slot__title">%s%s%s</span></li>'
                         % (times(t), kk, html.escape(title, quote=False), dd))
        out[lang].append(items)

for lang, name in ((0, "en"), (1, "bg")):
    p = ROOT / "content" / ("program-%s.html" % name)
    p.write_text("\n\n".join('<!-- day %d -->\n<ol class="timeline">\n  %s\n</ol>' % (i + 1, "\n  ".join(its)) for i, its in enumerate(out[lang])), encoding="utf-8")
    print(p.name, [len(x) for x in out[lang]])
