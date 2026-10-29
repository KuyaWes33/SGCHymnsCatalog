"""Read the words of each verse from the scanned book, syllable by syllable,
with where each one sits in the music.

    python tools/notation/lyrics.py "/path/to/Trinity Hymnal.pdf" 1 100 122

For each hymn, writes build/notation/lyrics/<number>.json: for every verse
printed between the staves, its syllables in order, each with the bar it
falls in and how far along that bar it sits. The converter uses that to put
each syllable under its note.

The book only says where words break and where they sit; the spelling comes
from the app's own text, since reading print gets the odd letter wrong.
"""
import difflib, json, os, re, subprocess, sys
from collections import defaultdict
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from bookfacts import OUT, ROOT, tool, page_map, staves, spans

LYRICS = os.path.join(OUT, 'lyrics')


def hymn_image(pdf, starts, n):
    """The whole of hymn n as printed, from its number to the next hymn,
    running on to the following page when it does."""
    page, top = starts[n]
    nxt = starts.get(n + 1)
    pieces = []
    p, t = page, top
    while True:
        out = os.path.join(OUT, 'book', f'full-{n:03d}-{p}.png')
        bottom = nxt[1] if nxt and nxt[0] == p else 1.0
        if not os.path.exists(out):
            subprocess.run([tool('pagepng'), pdf, str(p), '1400', out, str(max(0.0, t - 0.01)), str(bottom)], check=True)
        pieces.append(Image.open(out).convert('L'))
        if not nxt or nxt[0] <= p or (nxt[0] == p + 1 and nxt[1] < 0.03):
            break
        p, t = p + 1, 0.0
    width = max(i.width for i in pieces)
    img = Image.new('L', (width, sum(i.height for i in pieces)), 255)
    y = 0
    for i in pieces:
        img.paste(i, (0, y)); y += i.height
    path = os.path.join(OUT, 'book', f'full-{n:03d}.png')
    img.save(path)
    return path


def read_lines(path):
    got = subprocess.run([tool('lyriclines'), path], capture_output=True, text=True, check=True).stdout
    return json.loads(got)


VERSE_NUMBER = re.compile(r'^\d+[.,]$')


def letters_of(text):
    return norm(' '.join(text) if isinstance(text, list) else text)


def systems(path, verses_text, refrain_text=None):
    """Each line of music: its two staves, its barlines, and the words
    printed between them, sorted out by verse, with any chorus apart.

    Which verse a piece of print belongs to is decided by what it says, read
    against the app's text of each verse; the page is often a little
    skewed, so its height alone mixes up rows. Height settles only pieces
    too short to tell, and words every verse shares."""
    ink = np.asarray(Image.open(path).convert('L')) < 128
    H, W = ink.shape
    st = staves(ink)
    lines = read_lines(path)
    texts = [letters_of(v) for v in verses_text]
    if refrain_text:
        texts.append(letters_of(refrain_text))
    CHORUS = len(verses_text) if refrain_text else None

    def score(piece, text):
        """How well a piece of print reads as some stretch of a verse: the
        best likeness to any run of the verse's letters as long as it."""
        if not piece or not text:
            return 0.0
        n, best = len(piece), 0.0
        sm = difflib.SequenceMatcher(autojunk=False)
        sm.set_seq2(piece)
        for start in range(0, max(1, len(text) - n + 1)):
            sm.set_seq1(text[start:start + n])
            if sm.real_quick_ratio() > best and sm.quick_ratio() > best:
                best = max(best, sm.ratio())
        return best

    out = []
    for i in range(0, len(st) - 1, 2):
        (t1, b1), (t2, b2) = st[i], st[i + 1]
        xs = [x for x in range(W) if spans(ink, t1, b1, x) and spans(ink, t2, b2, x)]
        bars = []
        for x in xs:
            if bars and x - bars[-1][-1] <= 3:
                bars[-1].append(x)
            else:
                bars.append([x])
        bars = [sum(g) / len(g) for g in bars]
        inside = [l for l in lines if b1 < l['top'] * H and l['bottom'] * H < t2 and l['syllables']]
        mid = lambda l: (l['top'] + l['bottom']) / 2 * H
        tall = sorted((l['bottom'] - l['top']) * H for l in inside)[len(inside) // 2] if inside else 1
        # Which verse a piece is, where its words say so clearly: it reads
        # well as that verse and plainly better than any other. Words that
        # several verses share leave it to height.
        owner, heights = {}, defaultdict(list)
        pieces = []
        for k, l in enumerate(inside):
            piece = norm(' '.join(x[2] for x in l['syllables'] if not VERSE_NUMBER.match(x[2])))
            scores = sorted(((score(piece, t), vi) for vi, t in enumerate(texts)), reverse=True)
            pieces.append(piece)
            if len(piece) >= 5 and scores and scores[0][0] >= 0.8 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= 0.15):
                owner[k] = scores[0][1]
                heights[scores[0][1]].append(mid(l))
        row = {vi: sorted(h)[len(h) // 2] for vi, h in heights.items()}
        # Every height a row of words sits at here, top to bottom; a verse
        # with no clear piece takes the free height in its place in order.
        levels = []
        for m in sorted(mid(l) for l in inside):
            if levels and m - levels[-1][-1] < 0.5 * tall:
                levels[-1].append(m)
            else:
                levels.append([m])
        levels = [sum(g) / len(g) for g in levels]
        free = [y for y in levels if all(abs(y - h) >= 0.5 * tall for h in row.values())]
        for vi in range(len(texts)):
            if vi in row or not free:
                continue
            above = [row[u] for u in row if u < vi]
            below = [row[u] for u in row if u > vi]
            fits = [y for y in free if (not above or y > max(above)) and (not below or y < min(below))]
            if fits:
                row[vi] = fits[0]
                free.remove(fits[0])
        for k, l in enumerate(inside):
            if k in owner or not row:
                continue
            vi = min(row, key=lambda vi: abs(row[vi] - mid(l)))
            if abs(row[vi] - mid(l)) < 0.8 * tall:
                owner[k] = vi
        verses, chorus = defaultdict(list), []
        for k, vi in owner.items():
            syl = [x for x in inside[k]['syllables'] if not VERSE_NUMBER.match(x[2])]
            (chorus if vi == CHORUS else verses[vi]).extend(syl)
        tidy = lambda syl: [{'x': x[0] * W, 'text': x[2], 'hyphen': x[3]} for x in sorted(syl, key=lambda x: x[0])]
        out.append({'bars': bars, 'width': W,
                    'verses': {vi: tidy(v) for vi, v in verses.items()}, 'chorus': tidy(chorus)})
    return out


def words_of(syllables):
    """Join syllables back into words: [(word, [syllable texts])]."""
    out, cur = [], []
    for s in syllables:
        cur.append(s)
        if not s['hyphen']:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def norm(w):
    # Reading print takes a capital O for a nought now and then.
    return re.sub(r"[^a-z]", '', w.lower().replace('0', 'o'))


def merge(printed, text):
    """The verse as sung, syllable by syllable: the app's spelling, broken
    and placed as the book prints it.

    `text` is the verse's lines from the app. The two are lined up letter by
    letter, so each printed syllable claims the app's letters it matches, and
    a word breaks wherever its letters pass from one printed syllable to the
    next. A word reading the print missed altogether is split by dictionary
    and left unplaced, for the converter to fit in between its neighbours."""
    import pyphen
    split = pyphen.Pyphen(lang='en_US')
    # The printed letters, each knowing its syllable.
    seen, owner = [], []
    for si, s in enumerate(printed):
        for ch in norm(s['text']):
            seen.append(ch); owner.append(si)
    # The app's words; a word it writes with a hyphen, heav'n-taught, is
    # two, the first running on to the second.
    words = []
    for w in ' '.join(text).split():
        parts = [p for p in re.split(r'[-\u2013]', w) if p]
        for k, p in enumerate(parts):
            words.append((p, k < len(parts) - 1))
    letters = [(wi, ci) for wi, (w, _) in enumerate(words) for ci, ch in enumerate(w) if norm(ch)]
    app = [norm(words[wi][0][ci]) for wi, ci in letters]
    claim = {}
    for a, b, size in difflib.SequenceMatcher(a=seen, b=app, autojunk=False).get_matching_blocks():
        for k in range(size):
            claim[letters[b + k]] = owner[a + k]
    # Which of the app's words each printed syllable's letters went to.
    spread = defaultdict(set)
    for (wi, ci), owner_of in claim.items():
        spread[owner_of].add(wi)
    out = []
    for wi, (word, runs_on) in enumerate(words):
        mine = [claim.get((wi, ci)) for ci in range(len(word))]
        if not any(m is not None for m in mine):
            core = re.match(r"^(\W*)(.*?)(\W*)$", word)
            pieces = [p for p in split.inserted(core.group(2)).split('-') if p] or [core.group(2)]
            pieces[0] = core.group(1) + pieces[0]
            pieces[-1] = pieces[-1] + core.group(3)
            for k, p in enumerate(pieces):
                out.append({'text': p, 'hyphen': k < len(pieces) - 1 or runs_on, 'system': None, 'x': None})
            continue
        # Letters the print did not account for go with the syllable before,
        # but at the start of a word, re- of rejoice when only "joice" was
        # read, they are syllables of their own, split by dictionary and
        # left unplaced.
        first = next(ci for ci, m in enumerate(mine) if m is not None)
        last = mine[first]
        for ci in range(first, len(word)):
            if mine[ci] is None:
                mine[ci] = last
            last = mine[ci]
        pieces, owners = [], []
        lead = word[:first]
        # Only where the dictionary agrees a syllable ends there: "re" of
        # rejoice is one, "do" of doth is not, just letters read wrong.
        core_at = len(re.match(r"^\W*", word).group(0))
        if norm(lead) and (first - core_at) in split.positions(word[core_at:].rstrip('.,;:!?')):
            pass
        else:
            mine = [mine[first]] * first + mine[first:]
            first, lead = 0, ''
        if norm(lead):
            for p in [p for p in split.inserted(lead).split('-') if p]:
                pieces.append(p); owners.append(None)
        # Leading punctuation alone, an opening quote, stays with the word.
        cur, cur_owner = (lead if not norm(lead) else ''), None
        for ch, m in zip(word[first:], mine[first:]):
            # Break only where the print breaks: the syllable so far runs on
            # with a hyphen, or both it and the next belong wholly to this
            # word, the hyphen between them missed in reading. Printed words
            # straddling the app's, as reading drifts, do not split it.
            # A missed hyphen only where the dictionary allows a break.
            core_at = len(re.match(r"^\W*", word).group(0))
            at = first + len(cur) - core_at
            whole = (spread[cur_owner] == {wi} and spread[m] == {wi}
                     and at in split.positions(word[core_at:].rstrip('.,;:!?')))
            if cur and norm(cur) and m != cur_owner and norm(ch) and (printed[cur_owner]['hyphen'] or whole):
                pieces.append(cur); owners.append(cur_owner); cur = ''
            if not norm(cur):
                cur_owner = m
            cur += ch
        pieces.append(cur); owners.append(cur_owner)
        for k, (p, m) in enumerate(zip(pieces, owners)):
            s = printed[m] if m is not None else {'system': None, 'x': None}
            out.append({'text': p, 'hyphen': k < len(pieces) - 1 or runs_on, 'system': s['system'], 'x': s['x']})
    return out


def read(pdf, n, verses_text, refrain_text=None):
    """Each printed verse as a list of syllables, each placed by system and
    x, and the chorus if there is one. `verses_text` is the app's text for
    the hymn, a list of verses; `refrain_text` its chorus."""
    starts = page_map(pdf)
    path = hymn_image(pdf, starts, n)
    sy = systems(path, verses_text, refrain_text)
    count = max((max(s['verses'], default=-1) + 1 for s in sy), default=0)
    verses = []
    for v in range(count):
        syl = [dict(x, system=si) for si, s in enumerate(sy) for x in s['verses'].get(v, [])]
        verses.append(merge(syl, verses_text[v]) if v < len(verses_text) else syl)
    printed = [dict(x, system=si) for si, s in enumerate(sy) for x in s['chorus']]
    refrain = merge(printed, refrain_text) if printed and refrain_text else []
    refrain_from = next((si for si, s in enumerate(sy) if s['chorus']), None) if refrain else None
    return {'systems': [{'bars': s['bars'], 'width': s['width'],
                         'start': min((v[0]['x'] for v in list(s['verses'].values()) + [s['chorus']] if v), default=0)}
                        for s in sy],
            'verses': verses, 'refrain': refrain, 'refrain_from': refrain_from}


def app_text():
    src = open(os.path.join(ROOT, 'index.html')).read()
    hymns = json.loads(re.search(r'var HYMNS = (\[.*?\]);\n', src, re.S).group(1))
    by = {h['n']: h for h in hymns}
    try:
        for h in json.load(open(os.path.join(ROOT, 'extra-hymns.json'))):
            by[h['n']] = h
    except FileNotFoundError:
        pass
    return by


def main(pdf, numbers):
    os.makedirs(LYRICS, exist_ok=True)
    text = app_text()
    for n in numbers:
        h = text.get(n)
        got = read(pdf, n, h['v'] if h else [], h.get('refrain') if h else None)
        json.dump(got, open(os.path.join(LYRICS, f'{n:03d}.json'), 'w'), indent=1)
        print(n, len(got['systems']), 'lines of music,', len(got['verses']), 'verses between the staves',
              '+ chorus' if got['refrain'] else '')


if __name__ == '__main__':
    main(sys.argv[1], [int(a) for a in sys.argv[2:]])
