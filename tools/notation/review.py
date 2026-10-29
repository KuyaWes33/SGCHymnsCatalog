"""A page for checking the scores against the printed book.

    python tools/notation/review.py --book "/path/to/Trinity Hymnal.pdf"
    python tools/notation/review.py --book ... 14 100      just those hymns
    python tools/notation/review.py --book ... --check     only the doubtful

Run build.py first. Writes build/notation/review.html: each hymn's opening
from the scanned book beside the score made from its tune, the doubtful ones
first, so a wrong pickup or a missing fermata is seen at a glance. Put any
fix in overrides.json and build again.

The scans stay in build/, which is never committed or published: the book's
typesetting belongs to its publisher. Reading the book needs macOS, for its
PDF and text recognition; without --book the page shows the scores alone.
"""
import argparse, html, json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bookfacts import OUT, page_map, crop


def book_crop(pdf, starts, n):
    path = crop(pdf, starts, n)
    return os.path.relpath(path, OUT) if path else None


def score_svg(name):
    import verovio
    src = os.path.join(OUT, name + '.musicxml')
    out = os.path.join(OUT, 'svg', name + '.svg')
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        tk = verovio.toolkit()
        tk.setOptions({'pageWidth': 2100, 'scale': 40, 'adjustPageHeight': True,
                       'header': 'none', 'footer': 'none', 'breaks': 'auto'})
        tk.loadFile(src)
        open(out, 'w').write(tk.renderToSVG(1))
    return os.path.relpath(out, OUT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', help='the scanned hymnal, as a PDF')
    ap.add_argument('--check', action='store_true', help='only the hymns marked for checking')
    ap.add_argument('hymns', nargs='*')
    a = ap.parse_args()

    report = json.load(open(os.path.join(OUT, 'report.json')))
    names = sorted(report)
    if a.hymns:
        keep = {h.zfill(3) for h in a.hymns}
        names = [n for n in names if n in keep or n[:3] in keep]
    if a.check:
        names = [n for n in names if report[n].get('check') or 'error' in report[n]]
    # The doubtful first, then the guessed pickups, then the rest.
    names.sort(key=lambda n: (not report[n].get('check'), report[n].get('pickup_source') != 'guessed', n))
    starts = page_map(a.book) if a.book else {}

    rows = []
    for n in names:
        r = report[n]
        num = int(n[:3]) if n[:3].isdigit() else None
        book = book_crop(a.book, starts, num) if a.book and num else None
        if 'error' in r:
            facts = 'Could not be converted: ' + r['error']
            score = ''
        else:
            facts = (f"pickup {r['pickup']:g} beat{'s' if r['pickup'] != 1 else ''} ({r['pickup_source']}) · "
                     f"{r['fermatas']} fermata{'s' if r['fermatas'] != 1 else ''} · {r['mode']}")
            score = f'<img loading="lazy" src="{score_svg(n)}" alt="Score made from the tune">'
        flag = ' check' if r.get('check') else ''
        rows.append(f'''<section class="hymn{flag}" id="h{n}">
  <h2>{html.escape(n)}{' <span>check</span>' if flag else ''}</h2>
  <p>{html.escape(facts)}</p>
  <div class="pair">
    <figure><figcaption>Printed</figcaption>{f'<img loading="lazy" src="{book}" alt="Printed page">' if book else '<em>not found in the book</em>'}</figure>
    <figure><figcaption>Made from the tune</figcaption>{score}</figure>
  </div>
</section>''')

    page = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Score review</title>
<style>
:root{{--bg:#F2F8F8;--card:#fff;--ink:#0E2627;--muted:#4F6F70;--rule:#C9DEDE;--flag:#0F7F81}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,system-ui,sans-serif}}
header{{padding:16px;border-bottom:1px solid var(--rule);background:var(--card)}}
h1{{margin:0;font-size:20px}} header p{{margin:4px 0 0;color:var(--muted)}}
.hymn{{background:var(--card);margin:16px;padding:12px 16px;border:1px solid var(--rule);border-radius:6px}}
.hymn.check{{border-left:4px solid var(--flag)}}
h2{{margin:0;font-size:18px}} h2 span{{font-size:12px;color:#fff;background:var(--flag);padding:1px 6px;border-radius:3px;vertical-align:middle}}
.hymn p{{margin:2px 0 10px;color:var(--muted)}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}
@media (max-width:900px){{.pair{{grid-template-columns:1fr}}}}
figure{{margin:0}} figcaption{{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em}}
figure img{{width:100%;height:auto;background:#fff;border:1px solid var(--rule)}}
</style></head><body>
<header><h1>Score review</h1>
<p>{len(names)} hymns. Marked ones first, then those whose pickup was guessed. Fixes go in tools/notation/overrides.json.</p></header>
{''.join(rows)}
</body></html>'''
    path = os.path.join(OUT, 'review.html')
    open(path, 'w').write(page)
    print(path)


if __name__ == '__main__':
    main()
