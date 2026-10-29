"""Read facts about each hymn's layout from the scanned book.

    python tools/notation/bookfacts.py "/path/to/Trinity Hymnal.pdf"

The tunes do not always say where the first barline falls, and the music
alone cannot always tell. The book can: count the syllables of verse 1 that
come before the first barline, and the tune says how many beats those notes
take. That count, one small number per hymn, is all this keeps, in
book-facts.json beside it, so a build needs no scans at all.

Reading the book needs macOS, for its PDF and text recognition, through the
Swift helpers in book/. Page images go to build/, which is never committed:
the book's typesetting belongs to its publisher.
"""
import json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, 'build', 'notation')
BIN = os.path.join(OUT, 'bin')
FACTS = os.path.join(HERE, 'book-facts.json')


def tool(name):
    """Compile one of the small Swift helpers in book/ the first time."""
    exe = os.path.join(BIN, name)
    src = os.path.join(HERE, 'book', name + '.swift')
    if not os.path.exists(exe) or os.path.getmtime(exe) < os.path.getmtime(src):
        os.makedirs(BIN, exist_ok=True)
        subprocess.run(['swiftc', '-O', src, '-o', exe], check=True)
    return exe


def page_map(pdf):
    """Where each hymn starts in the book: {number: [page, top]}, top as a
    fraction of the page from the top. Read once and kept."""
    path = os.path.join(OUT, 'book', 'pages.json')
    if os.path.exists(path):
        return {int(k): v for k, v in json.load(open(path)).items()}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = subprocess.run([tool('pageindex'), pdf, '1', '9999'], capture_output=True, text=True, check=True).stdout
    found = []
    for line in lines.splitlines():
        p = json.loads(line)
        for h in p['hits']:
            # Hymn numbers are the big ones in the outer margins.
            if h['h'] >= 0.017 and (h['x'] < 0.12 or h['x'] > 0.8):
                found.append((p['page'], 1 - h['y'] - h['h'], h['n']))
    found.sort()
    starts, last = {}, 0
    for page, top, n in found:
        # They run in order; anything out of step is a stray number.
        if last < n <= last + 6:
            starts[n] = [page, round(top, 3)]
            last = n
    json.dump(starts, open(path, 'w'))
    return starts


def crop(pdf, starts, n):
    """The opening of hymn n as printed, down to the next hymn or the end of
    its page, at most about half a page. Returns the image's path."""
    if n not in starts:
        return None
    out = os.path.join(OUT, 'book', f'{n:03d}.png')
    if not os.path.exists(out):
        page, top = starts[n]
        nxt = starts.get(n + 1)
        bottom = nxt[1] if nxt and nxt[0] == page and nxt[1] > top else 1.0
        bottom = min(bottom, top + 0.5)
        subprocess.run([tool('pagepng'), pdf, str(page), '1100', out,
                        str(max(0.0, top - 0.01)), str(bottom)], check=True)
    return out


# ---------------------------------------------------------------- the image

def staves(ink):
    """(top line, bottom line) of each five-line staff, top to bottom."""
    rows = ink.mean(axis=1)
    groups = []
    for y in np.nonzero(rows > 0.45)[0]:
        if groups and y - groups[-1][-1] <= 2:
            groups[-1].append(y)
        else:
            groups.append([y])
    ys = [sum(g) / len(g) for g in groups]
    out, i = [], 0
    while i <= len(ys) - 5:
        gaps = np.diff(ys[i:i + 5])
        if gaps.min() > 5 and gaps.max() - gaps.min() <= 2.5:
            out.append((ys[i], ys[i + 4])); i += 5
        else:
            i += 1
    return out


def spans(ink, top, bottom, x):
    """Whether column x is a barline across this staff: inked from the top
    line to the bottom one and stopping there, where a stem runs on."""
    t, b = int(round(top)), int(round(bottom))
    space = (bottom - top) / 4

    def run(y, step):
        n = 0
        while 0 <= y < ink.shape[0] and ink[y, x]:
            n += 1; y += step
        return n
    covered = ink[t:b + 1, max(0, x - 1):x + 2].any(axis=1).mean()
    return covered >= 0.97 and run(t - 2, -1) < 0.3 * space and run(b + 2, 1) < 0.3 * space


def barlines(path):
    """x of each barline through the first system, which in this book runs
    through treble and bass staves alike."""
    ink = np.asarray(Image.open(path).convert('L')) < 128
    st = staves(ink)
    if len(st) < 2:
        return [], ink.shape[1]
    (t1, b1), (t2, b2) = st[0], st[1]
    xs = [x for x in range(ink.shape[1]) if spans(ink, t1, b1, x) and spans(ink, t2, b2, x)]
    out = []
    for x in xs:
        if out and x - out[-1][-1] <= 3:
            out[-1].append(x)
        else:
            out.append([x])
    return [sum(g) / len(g) for g in out], ink.shape[1]


def syllables(path):
    """Centre x of each syllable of verse 1 on the first system."""
    got = json.loads(subprocess.run([tool('lyricstart'), path], capture_output=True, text=True).stdout or '{}')
    return [(a + b) / 2 for a, b in got.get('syllables', [])]


def before_first_bar(path):
    """How many syllables of verse 1 come before the first barline, or None
    when the image cannot say."""
    bars, width = barlines(path)
    syl = [c * width for c in syllables(path)]
    if not syl:
        return None
    after = [b for b in bars if b > syl[0]]
    if not after:
        return None
    return sum(1 for c in syl if c < after[0])


def main(pdf):
    starts = page_map(pdf)
    numbers = sorted(n for n in starts if n <= 731)

    def one(n):
        path = crop(pdf, starts, n)
        return n, (before_first_bar(path) if path else None)

    with ThreadPoolExecutor(max_workers=6) as pool:
        found = dict(pool.map(one, numbers))
    facts = {str(n): {'syllables_before_first_bar': m} for n, m in sorted(found.items()) if m is not None}
    facts = {'_about': 'Read from the scanned book by bookfacts.py. For each hymn, how many '
                       'syllables of verse 1 come before the first barline.', **facts}
    json.dump(facts, open(FACTS, 'w'), indent=1)
    print(f'{len(facts) - 1} hymns read, {sum(1 for m in found.values() if m is None)} could not be')


if __name__ == '__main__':
    main(sys.argv[1])
