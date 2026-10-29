"""Turn an OPC hymn tune (MIDI) into a two-stave SATB score in MusicXML.

The OPC files were made by scanning the printed hymnal and then played back
with a little human timing. So they hold the right notes, but:

  - every verse is played, separated by a short silence
  - the file opens with one silent beat
  - every note is a little late, and later still after each breath
  - a fermata is played as extra beats: sometimes the file writes those
    beats into a longer bar, sometimes it does not mark them at all
  - a pickup beat is sometimes written as a short first bar, sometimes not

This takes the first verse and the Amen, undoes each of those, and writes
the score. Where it has to guess, the report says so, and any hymn can be
put right by hand in overrides.json.

    python midi2score.py tunes/Th1_014.mid out.musicxml
"""
import json, os, sys
from collections import defaultdict, Counter
import mido
from music21 import (stream, note, meter, key, clef, layout, metadata,
                     expressions, tie, pitch as m21pitch)

Q = 240            # ticks per quarter note, after scaling
GRID = 60          # the finest note kept: a sixteenth
CLUSTER = 45       # onsets closer than this are one chord
VERSE_GAP = 180    # a silence longer than this separates verses
LEAD = 240         # the files open with one silent beat
BREATH = 8         # a jump in lateness this big marks a new line

HERE = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- reading

def load(path):
    """Notes as (on, off, staff, pitch), staff 0 treble, 1 bass, 2 the
    organ's doubled bass, which the score leaves out; and the time and key
    signatures."""
    m = mido.MidiFile(path)
    # Everything here counts in 240ths of a quarter; a few files use
    # another resolution, so scale them.
    k = Q / m.ticks_per_beat
    raw = []
    for t in m.tracks:
        tick = 0; on = defaultdict(list)
        for x in t:
            tick += x.time
            if x.type == 'note_on' and x.velocity > 0:
                on[(x.channel, x.note)].append(tick)
            elif x.type == 'note_off' or (x.type == 'note_on' and x.velocity == 0):
                # Two parts singing the same note strike the same key twice;
                # each release ends the earliest of them still sounding.
                if on[(x.channel, x.note)]:
                    s = on[(x.channel, x.note)].pop(0)
                    raw.append((round(s * k), round(tick * k), x.channel, x.note))
    # The parts are told apart by channel: the first is the treble staff,
    # the second the bass, and any other the organ's doubled bass line. Most
    # files give each its own track, but one puts all three in a single one.
    channels = sorted({c for *_, c, _ in raw})
    staff = {c: min(i, 2) for i, c in enumerate(channels)}
    notes = sorted((s, e, staff[c], p) for s, e, c, p in raw)
    meta = []
    for t in m.tracks[:1] if m.type == 1 else m.tracks:
        tick = 0
        for x in t:
            tick += x.time
            if x.type == 'time_signature':
                meta.append((round(tick * k), 'time', (x.numerator, x.denominator)))
            elif x.type == 'key_signature':
                meta.append((round(tick * k), 'key', x.key))
    return notes, meta


def verse_one(notes):
    """The notes of the first pass, the Amen if there is one, and the last
    pass, which the Amen belongs to."""
    # A silence starts a new verse only if what follows begins the way the
    # hymn begins; a rest inside the verse or the chorus is followed by
    # something else.
    def opening(at):
        top = {}
        for s, e, st, p in notes:
            if s >= at and st == 0 and s < at + 4 * Q * 4:
                q = s // CLUSTER
                top[q] = max(top.get(q, 0), p)
        return [top[q] for q in sorted(top)][:4]
    first = opening(notes[0][0])
    end = 0; starts = [notes[0][0]]
    for s, e, *_ in notes:
        if end and s > end + VERSE_GAP and opening(s) == first:
            starts.append(s)
        end = max(end, e)
    if len(starts) == 1:
        return notes, [], []
    v1 = [n for n in notes if n[0] < starts[1]]
    sounding = max(n[1] for n in v1) - starts[0]
    last = [n for n in notes if n[0] >= starts[-1]]
    # The last pass is a verse; anything that starts after a verse has
    # stopped sounding is the Amen.
    amen = [n for n in last if n[0] - starts[-1] > sounding - 120]
    return v1, amen, last


def quantize(notes, start=None):
    """Snap onsets to the sixteenth-note grid.

    Every note is played a little late, by an amount that holds steady for a
    line and then grows at each breath. Track that lateness as it goes and
    snap what is left, so it never builds up into a wrong beat. Returns where
    each played onset belongs, and the onsets that follow a breath."""
    on = sorted({n[0] for n in notes})
    clusters = []
    for t in on:
        if clusters and t - clusters[-1][-1] < CLUSTER:
            clusters[-1].append(t)
        else:
            clusters.append([t])
    raw = [c[0] for c in clusters]
    # The music starts one silent beat into the file, so the first note's
    # distance past that beat is how late the playing starts. Lateness only
    # grows from there, so it cannot be read from later notes.
    shift = raw[0] - LEAD if raw[0] >= LEAD else raw[0] % GRID
    def landing(at, lateness):
        """How many of the next notes land on an eighth-note grid if the
        playing is this late from note `at` on. Hymns seldom move in
        sixteenths, so a wrong reading of a pause shows as many of them."""
        good, late = 0, lateness
        for t in raw[at:at + 8]:
            r = t - late
            qt = (r + GRID // 2 - 10) // GRID * GRID
            late += r - qt
            good += (qt % (2 * GRID) == 0)
        return good

    q, breaths = [], []
    for i, t in enumerate(raw):
        r = t - shift
        # Lateness only ever grows, by up to half a sixteenth at a breath,
        # so a note that is ambiguous belongs to the earlier grid point.
        qt = (r + GRID // 2 - 10) // GRID * GRID
        # A longer pause, before a chorus say, can be more than that. It
        # comes after a long note, at the end of a line: there, when this
        # note is late, try reading up to an eighth more of it as pause and
        # keep whichever puts what follows back on the beat.
        floor = r // GRID * GRID
        if i and r - floor >= BREATH and t - raw[i - 1] >= 2 * Q - GRID:
            default = qt
            # The plain rounding, or more of the lateness read as pause:
            # never less.
            options = [c for c in {default, floor, floor - GRID, floor - 2 * GRID} if c > q[-1] and c <= default]
            qt = max(options, key=lambda c: (landing(i + 1, shift + r - c), -abs(c - default)))
        if i and r - qt >= BREATH:
            breaths.append(qt)
        shift += r - qt
        q.append(qt)
    base = q[0] - (start or 0)
    where = {}
    for c, qt in zip(clusters, q):
        for t in c:
            where[t] = qt - base
    return where, [b - base for b in breaths]


# ---------------------------------------------------------------- voices

def voices(notes, where):
    """Split each staff into its upper and lower voice: soprano and alto,
    tenor and bass. Each note is [onset, length, pitch, fermata]."""
    parts = {0: [[], []], 1: [[], []]}
    by = defaultdict(list)
    for s, e, st, p in notes:
        if st < 2:
            by[(st, where[s])].append((p, e - s))
    for (st, qt), ps in sorted(by.items(), key=lambda kv: kv[0][1]):
        longest = {}
        for p, d in ps:
            longest[p] = max(d, longest.get(p, 0))
        ps = sorted(longest.items(), key=lambda x: -x[0])
        hi, lo = ps[0], ps[-1]
        v = parts[st]
        free = [i for i in (0, 1) if not v[i] or v[i][-1][0] + v[i][-1][1] <= qt]
        if len(ps) >= 2 or len(free) != 1:
            v[0].append([qt, hi[1], hi[0], False]); v[1].append([qt, lo[1], lo[0], False])
        else:
            v[free[0]].append([qt, ps[0][1], ps[0][0], False])
    # Played lengths are short of written ones; round up, never past the next
    # note, and close any gap smaller than a sixteenth.
    for st in parts:
        for seq in parts[st]:
            for a, b in zip(seq, seq[1:] + [None]):
                d = max(GRID, round(a[1] / 0.88 / GRID) * GRID)
                if b:
                    d = min(d, b[0] - a[0])
                    if b[0] - a[0] - d < GRID:
                        d = b[0] - a[0]
                a[1] = d
    return parts


def all_notes(parts):
    return [n for st in parts for seq in parts[st] for n in seq]


def remove_hold(parts, at, extra):
    """Take a fermata's extra beats back out: the chord at `at` is shortened
    by `extra` and marked, and everything after it moves earlier."""
    for n in all_notes(parts):
        if n[0] > at:
            n[0] -= extra
        elif n[0] + n[1] > at + extra:
            # Starts at the held chord, or is sounding through it.
            n[1] -= extra
            if n[0] == at:
                n[3] = True


# ---------------------------------------------------------------- bars

def time_map(meta):
    ts = [(t, num, den) for t, kind, v in meta if kind == 'time' for num, den in [v]]
    return ts or [(0, 4, 4)]


def bars_of(ts, until):
    """(start, length, num, den) for every bar the time signatures describe."""
    out = []
    for i, (t, num, den) in enumerate(ts):
        length = num * 4 * Q // den
        stop = ts[i + 1][0] if i + 1 < len(ts) else until + 4 * length
        b = t
        while b < stop:
            out.append((b, length, num, den)); b += length
    return out


def melody(parts):
    return parts[0][0]


def plan_bars(parts, meta, breaths, report, override, book=None):
    """Decide where the bar lines go, taking fermata holds out as it goes.

    Returns the bars as (start, length, num, den), and the hymn's usual bar
    as (length, num, den)."""
    ts = time_map(meta)
    # Bars up to the one that holds the last melody note; the held chord
    # spills past it, into bars that belong to nothing.
    last_note = melody(parts)[-1][0]
    bars = [b for b in bars_of(ts, song_end(parts)) if b[0] <= last_note]
    body = bars[1:-1] or bars
    L, num, den = Counter(b[1:] for b in body).most_common(1)[0][0]
    beat = 4 * Q // den
    mel = melody(parts)

    # A bar split across a line break was read as two short bars. Join them
    # back; if together they come to more than a bar, the extra is a fermata
    # and is dealt with next.
    joined = [bars[0]]
    for b in bars[1:]:
        p = joined[-1]
        if len(joined) > 1 and p[1] < L and b[1] < L:
            joined[-1] = (p[0], p[1] + b[1], num, den)
        else:
            joined.append(b)
    bars = joined

    # Fermatas the file wrote as a longer bar. The held chord is the longest
    # in that bar, the latest of them if several tie; the bar goes back to
    # its usual length.
    kept, moved = [], 0
    for i, (b0, blen, bn, bd) in enumerate(bars):
        start = b0 - moved
        if i and blen > L:
            extra = blen - L
            inside = [n for n in mel if start <= n[0] < start + blen and n[1] - extra >= 2 * GRID]
            if inside:
                held = max(inside, key=lambda n: (n[1], n[0]))
                remove_hold(parts, held[0], extra)
                moved += extra
                report['fermatas'] += 1
                kept.append((start, L, num, den))
                continue
        kept.append((start, blen, bn, bd))

    # Any other bar of a different length, apart from the first and last, is
    # a real change of meter: keep the file's bars as they are.
    if any(b[1] != L for b in kept[1:-1]):
        report['mode'] = 'mixed meter'
        report['pickup'] = kept[0][1] / beat if kept[0][1] < L else 0
        report['pickup_source'] = 'file'
        return extend(kept, song_end(parts), ts), (L, num, den)

    report['mode'] = 'regular'
    # Holds the file did not mark: where a line is not a whole number of
    # bars long, its last note was held over.
    ends = line_ends(mel, breaths, beat)
    if not report['fermatas']:
        line_start = 0
        for n in ends:
            i = mel.index(n)
            if i + 1 >= len(mel):
                break
            nxt = mel[i + 1][0]
            extra = (nxt - line_start) % L
            if extra and n[1] - extra >= beat:
                remove_hold(parts, n[0], extra)
                report['fermatas'] += 1
            line_start = mel[i + 1][0]

    first = kept[0][1]
    if override.get('pickup') is not None:
        pickup = round(override['pickup'] * beat)
        report['pickup_source'] = 'overrides.json'
    elif first < L:
        pickup = first
        report['pickup_source'] = 'file'
    else:
        # The file does not say. The book does, when its first line could be
        # read: the notes for the syllables before the first barline make up
        # the pickup. Checked against the files that do say, the book and
        # the tune agreeing is right 97 times in 100; when they differ, the
        # book is right three times in four.
        guess, sure = guess_pickup(mel, ends, L, beat)
        read = from_book(mel, book, L, beat)
        if read is None:
            pickup = guess
            report['pickup_source'] = 'tune' if sure else 'unsure'
        elif read == guess:
            pickup = read
            report['pickup_source'] = 'book and tune'
        else:
            pickup = read
            report['pickup_source'] = 'book, not tune'
    report['pickup'] = pickup / beat

    # Bars up to the one holding the last melody note; its held chord gets
    # trimmed to fit later.
    last = mel[-1][0]
    out, b = ([(0, pickup, num, den)] if pickup else []), pickup
    while b <= last:
        out.append((b, L, num, den)); b += L
    # A hymn with a pickup ends on a short bar that makes up the difference.
    if pickup and last < out[-1][0] + L - pickup:
        out[-1] = (out[-1][0], L - pickup, num, den)
    return out, (L, num, den)


def song_end(parts):
    return max(n[0] + n[1] for n in all_notes(parts))


def extend(bars, until, ts):
    """Add bars in the last time signature until `until` is covered."""
    bars = list(bars)
    while bars[-1][0] + bars[-1][1] < until:
        b0, blen, bn, bd = bars[-1]
        bars.append((b0 + blen, bn * 4 * Q // bd, bn, bd))
    return [b for b in bars if b[0] < until]


def line_ends(mel, breaths, beat):
    """The melody notes that end a line, in order."""
    if breaths:
        ends = []
        for b in breaths:
            before = [n for n in mel if n[0] < b]
            if before and (not ends or before[-1] is not ends[-1]):
                ends.append(before[-1])
        return ends
    # No breaths in this file: a line ends on a long note, three beats or
    # more.
    return [n for n in mel[:-1] if n[1] >= 3 * beat]


def from_book(mel, syllables, L, beat):
    """The pickup the book shows, from how many syllables of verse 1 come
    before its first barline. A syllable sung over two notes shows as one,
    so the bar starts at the first note on a beat from there on."""
    if syllables is None:
        return None
    start = next((n[0] for n in mel[syllables:] if n[0] % beat == 0), 0)
    return start % L


def guess_pickup(mel, ends, L, beat):
    """The pickup that puts the most line endings on a downbeat, with long
    notes on strong beats to break a tie. Returns it and whether the winner
    was clear."""
    at = {n[0] for n in ends} | {mel[-1][0]}
    half = L // 2 if (L // beat) % 2 == 0 else None

    def score(k):
        off = (L - k) % L
        downs = sum(1 for e in at if (e + off) % L == 0)
        accent = sum(n[1] * (2 if (n[0] + off) % L == 0 else 1 if (n[0] + off) % L == half else 0)
                     for n in mel if n[1] >= 2 * beat)
        return (downs, accent)

    ranked = sorted(((score(k), k) for k in range(0, L, beat)), key=lambda x: x[0], reverse=True)
    sure = len(ranked) == 1 or ranked[1][0] < ranked[0][0]
    return ranked[0][1], sure


# ---------------------------------------------------------------- words

def book_bars(lyrics):
    """The book's bars in order through every line of music. Each is a list
    of pieces (line, left, right) in pixels: one piece, or two when the bar
    is split across a line break."""
    out = []
    for si, s in enumerate(lyrics['systems']):
        left = s['start'] - 6
        # The line's opening stroke, before the first syllable, is no barline;
        # a double bar counts once.
        xs = []
        for x in s['bars']:
            if x <= left:
                continue
            if xs and x - xs[-1] < 15:
                xs[-1] = x
            else:
                xs.append(x)
        for x in xs:
            out.append([(si, left, x)]); left = x
        if s['width'] - left > 40:
            out.append([(si, left, s['width'])])
    return out


def width(bar):
    return sum(b - a for _, a, b in bar)


def fit_bars(book, count):
    """Make the book's bars as many as the score's. First, a bar split
    across a line break shows as a short piece ending one line and another
    starting the next: join those. Then a barline the reading missed leaves
    one bar twice as wide, so split the widest; a stroke taken for a barline
    leaves two narrow ones, so join the narrowest pair."""
    book = [list(b) for b in book]
    if len(book) > count:
        typical = sorted(width(b) for b in book)[len(book) // 2]
        i = 0
        while i < len(book) - 1 and len(book) > count:
            a, b = book[i], book[i + 1]
            if a[-1][0] != b[0][0] and width(a) < 0.8 * typical and width(b) < 0.8 * typical:
                book[i:i + 2] = [a + b]
            i += 1
    while len(book) < count:
        i = max(range(len(book)), key=lambda i: width(book[i]) if len(book[i]) == 1 else 0)
        (si, a, b), = book[i]
        book[i:i + 1] = [[(si, a, (a + b) / 2)], [(si, (a + b) / 2, b)]]
    while len(book) > count:
        pairs = [i for i in range(len(book) - 1) if book[i][-1][0] == book[i + 1][0][0]]
        if not pairs:
            break
        i = min(pairs, key=lambda i: width(book[i]) + width(book[i + 1]))
        (si, a, _), (_, _, b) = book[i][-1], book[i + 1][0]
        book[i:i + 2] = [book[i][:-1] + [(si, a, b)] + book[i + 1][1:]]
    return book


PAD = 0.06          # a bar's first note sits a little past its barline


def place_words(parts, bars, lyrics, beat, report):
    """Which soprano note each syllable of each verse goes under. Returns
    {id(note): [(verse, text, syllabic)]}."""
    mel = [n for n in melody(parts) if n[0] < bars[-1][0] + bars[-1][1]]
    book = fit_bars(book_bars(lyrics), len(bars))
    report['words'] = {'bars': 'matched' if len(book) == len(bars) else f'{len(book)} in the book, {len(bars)} here'}
    placed = {}

    def when(s):
        """The moment in the score a printed syllable sits at."""
        if s['x'] is None:
            return None
        best = None
        for g, bar in enumerate(book[:len(bars)]):
            done = 0
            for si, a, b in bar:
                if si == s['system']:
                    d = 0 if a <= s['x'] < b else min(abs(s['x'] - a), abs(s['x'] - b))
                    if best is None or d < best[0]:
                        best = (d, g, (done + (s['x'] - a)) / max(1, width(bar)), bar)
                done += b - a
        if best is None:
            return None
        _, g, f, bar = best
        # A bar's first note sits a little past its barline.
        f = max(0.0, min(1.0, (f - PAD) / (1 - PAD))) if len(bar) == 1 else max(0.0, min(1.0, f))
        return bars[g][0] + f * bars[g][1]

    unmatched = 0

    def align(syl, notes):
        """Each syllable to a note, in order; notes passed over are a
        syllable held across several, so cost a little, not much."""
        nonlocal unmatched
        if not syl or not notes:
            return []
        t = [when(s) for s in syl]
        # A syllable the print did not show sits between its neighbours.
        known = [i for i, x in enumerate(t) if x is not None]
        if not known:
            t = [notes[0][0]] * len(t)
        for i in range(len(t)):
            if t[i] is None:
                lo = max((k for k in known if k < i), default=None)
                hi = min((k for k in known if k > i), default=None)
                if lo is not None and hi is not None:
                    t[i] = t[lo] + (t[hi] - t[lo]) * (i - lo) / (hi - lo)
                else:
                    t[i] = t[lo if lo is not None else hi]
        S, N, SKIP = len(syl), len(notes), 0.15
        if S > N:
            unmatched += S - N
            syl, t, S = syl[:N], t[:N], N
        INF = float('inf')
        # A short note off the beat is most often the second half of a
        # syllable held over two, so it costs more to give it one of its own.
        off = [0.35 if (n[0] % beat and n[1] < beat) else 0.0 for n in notes]
        cost = [[INF] * N for _ in range(S)]
        back = [[-1] * N for _ in range(S)]
        for j in range(N):
            cost[0][j] = abs(t[0] - notes[j][0]) / beat + off[j] + SKIP * j
        for i in range(1, S):
            best, arg = INF, -1
            for j in range(N):
                if j - 1 >= 0 and cost[i - 1][j - 1] - SKIP * (j - 1) < best:
                    best, arg = cost[i - 1][j - 1] - SKIP * (j - 1), j - 1
                if arg >= 0:
                    cost[i][j] = abs(t[i] - notes[j][0]) / beat + off[j] + best + SKIP * (j - 1)
                    back[i][j] = arg
        j = min(range(N), key=lambda j: cost[S - 1][j])
        chosen = [0] * S
        for i in range(S - 1, -1, -1):
            chosen[i] = j
            j = back[i][j]
        return list(zip(syl, (notes[j] for j in chosen)))

    def label(pairs, verse):
        for i, (s, n) in enumerate(pairs):
            before = i > 0 and pairs[i - 1][0]['hyphen']
            syllabic = ('middle' if before else 'begin') if s['hyphen'] else ('end' if before else 'single')
            placed.setdefault(id(n), []).append((verse, s['text'], syllabic))

    # The chorus starts at the first bar of its first line of music; the
    # verses have the notes before it, the chorus the notes from there on.
    chorus_at = None
    if lyrics.get('refrain') and lyrics.get('refrain_from') is not None:
        g = next((g for g, bar in enumerate(book) if bar[0][0] == lyrics['refrain_from']), None)
        if g is not None and g < len(bars):
            chorus_at = bars[g][0]
    verse_notes = [n for n in mel if chorus_at is None or n[0] < chorus_at]
    for vi, syl in enumerate(lyrics['verses']):
        label(align(syl, verse_notes), vi + 1)
    if chorus_at is not None:
        label(align(lyrics['refrain'], [n for n in mel if n[0] >= chorus_at]), 1)
        report['words']['chorus'] = True
    report['words']['verses'] = len(lyrics['verses'])
    if unmatched:
        report['words']['left over'] = unmatched
    return placed


# ---------------------------------------------------------------- writing

SHARPS = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
FLATS = ['C', 'D-', 'D', 'E-', 'E', 'F', 'G-', 'G', 'A-', 'A', 'B-', 'B']


def make_key(name):
    if not name:
        return None
    return key.Key(name[:-1].lower()) if name.endswith('m') else key.Key(name)


def spell(midi, k):
    """Name a MIDI pitch the way the key would write it: the key's own notes
    first, then sharps in sharp keys and flats in flat keys."""
    pc, octave = midi % 12, midi // 12 - 1
    name = None
    if k is not None:
        for p in k.getScale().getPitches('C1', 'B1'):
            if p.pitchClass == pc:
                name = p.name
                break
    if name is None:
        name = (FLATS if k is not None and k.sharps < 0 else SHARPS)[pc]
    pt = m21pitch.Pitch(name)
    # B# and Cb sit in the octave next door to their sound.
    pt.octave = octave + (1 if name.startswith('C-') else -1 if name.startswith('B#') else 0)
    return pt


# Note values a score can show as one note, longest first.
VALUES = [1440, 960, 720, 480, 360, 240, 180, 120, 60]


def pieces(length):
    out = []
    while length >= GRID:
        v = next(v for v in VALUES if v <= length)
        out.append(v); length -= v
    return out


def accidentals(part, k):
    """Both voices on a staff share one bar's worth of accidentals, as in print."""
    in_key = {p.step: p.alter for p in k.alteredPitches} if k is not None else {}
    for m in part.getElementsByClass(stream.Measure):
        state = {}
        for n in sorted((n for v in m.voices for n in v.notes), key=lambda n: n.offset):
            p = n.pitch
            slot = (p.step, p.octave)
            have = state.get(slot, in_key.get(p.step, 0))
            if p.alter != have:
                if p.accidental is None:
                    p.accidental = m21pitch.Accidental('natural')
                p.accidental.displayStatus = True
            elif p.accidental is not None:
                p.accidental.displayStatus = False
            # A tied-over note carries on the pitch without restating it.
            if n.tie is not None and n.tie.type in ('stop', 'continue') and p.accidental is not None:
                p.accidental.displayStatus = False
            state[slot] = p.alter


def build(parts, bars, meta, title, words=None):
    sc = stream.Score()
    sc.metadata = metadata.Metadata(title=title)
    ks = next((v for _, kind, v in meta if kind == 'key'), None)
    k = make_key(ks)
    has_pickup = len(bars) > 1 and bars[0][1] < bars[1][1]
    staffs = []
    for st, cl in ((0, clef.TrebleClef), (1, clef.BassClef)):
        part = stream.Part()
        last_ts = None
        for bi, (b0, blen, num, den) in enumerate(bars):
            m = stream.Measure(number=bi if has_pickup else bi + 1)
            b1 = b0 + blen
            if bi == 0:
                m.insert(0, cl())
                if k is not None:
                    m.insert(0, key.KeySignature(k.sharps))
            # A pickup bar, and the short bar that answers it at the end, are
            # shown under the hymn's own time signature, not one of their own.
            short = has_pickup and (bi == 0 or bi == len(bars) - 1) and blen < bars[1][1]
            ts = bars[1][2:] if short else (num, den)
            if ts != last_ts:
                m.insert(0, meter.TimeSignature(f'{ts[0]}/{ts[1]}'))
                last_ts = ts
            if bi == 0 and has_pickup:
                m.paddingLeft = (bars[1][1] - blen) / Q
            elif short:
                m.paddingRight = (bars[1][1] - blen) / Q
            for vi, seq in enumerate(parts[st]):
                v = stream.Voice(id=str(vi + 1))
                pos = b0
                for item in seq:
                    on, length, p, ferm = item[:4]
                    s, e = max(on, b0), min(on + length, b1)
                    if s >= e:
                        continue
                    if s > pos:
                        for r in pieces(s - pos):
                            rest = note.Rest(quarterLength=r / Q)
                            rest.style.hideObjectOnPrint = (vi == 1)
                            v.insert((pos - b0) / Q, rest); pos += r
                        pos = s
                    chunks = pieces(e - s)
                    for ci, c in enumerate(chunks):
                        n = note.Note(spell(p, k), quarterLength=c / Q)
                        n.stemDirection = 'up' if vi == 0 else 'down'
                        first_piece = (s == on and ci == 0)
                        last_piece = (e == on + length and ci == len(chunks) - 1)
                        if not (first_piece and last_piece):
                            n.tie = tie.Tie('start' if first_piece else 'stop' if last_piece else 'continue')
                        # The words sit under the soprano, so between the
                        # staves, as printed.
                        if first_piece and words and id(item) in words:
                            for verse, text, syllabic in words[id(item)]:
                                n.lyrics.append(note.Lyric(text=text, number=verse, syllabic=syllabic))
                        # One fermata a staff, as printed: over the treble's
                        # upper voice, under the bass's lower one.
                        if ferm and last_piece and vi == st:
                            f = expressions.Fermata()
                            f.type = 'upright' if st == 0 else 'inverted'
                            n.expressions.append(f)
                        v.insert((pos - b0) / Q, n); pos += c
                if pos < b1:
                    for r in pieces(b1 - pos):
                        rest = note.Rest(quarterLength=r / Q)
                        rest.style.hideObjectOnPrint = True
                        v.insert((pos - b0) / Q, rest); pos += r
                m.insert(0, v)
            part.append(m)
        accidentals(part, k)
        staffs.append(part)
    for p in staffs:
        sc.insert(0, p)
    sc.insert(0, layout.StaffGroup(staffs, symbol='brace', barTogether=True))
    return sc


# ---------------------------------------------------------------- whole

def load_book_facts():
    """From book-facts.json: {hymn number: syllables of verse 1 before the
    first barline}, as read from the scanned book by bookfacts.py."""
    try:
        got = json.load(open(os.path.join(HERE, 'book-facts.json')))
    except FileNotFoundError:
        return {}
    return {k: v['syllables_before_first_bar'] for k, v in got.items() if not k.startswith('_')}


def load_overrides():
    path = os.path.join(HERE, 'overrides.json')
    try:
        return {str(k): v for k, v in json.load(open(path)).items() if not str(k).startswith('_')}
    except FileNotFoundError:
        return {}


def end_at_barlines(parts, bars):
    """The last chord of each voice is held past its written length; end it
    at its barline."""
    for st in parts:
        for seq in parts[st]:
            if seq:
                n = seq[-1]
                stop = next((b[0] + b[1] for b in bars if b[0] <= n[0] < b[0] + b[1]), n[0] + n[1])
                n[1] = min(n[1], stop - n[0])


def convert(path, out, title, override=None, book=None, lyrics=None):
    """Write the score for one tune and return a report on how it went."""
    override = override or {}
    report = {'fermatas': 0, 'pickup': 0, 'pickup_source': None, 'mode': None, 'amen': False}
    notes, meta = load(path)
    v1, amen, last = verse_one(notes)
    where, breaths = quantize(v1)
    parts = voices(v1, where)
    bars, (L, num, den) = plan_bars(parts, meta, breaths, report, override, book)
    end_at_barlines(parts, bars)
    bars = [b for b in bars if b[0] < song_end(parts)]
    verse_end = bars[-1][0] + bars[-1][1]
    words = place_words(parts, bars, lyrics, 4 * Q // den, report) if lyrics else None

    if amen:
        # The Amen is played slowly, each chord held for a bar or more, so its
        # timing says nothing about how it is written. Hymnals set it as even
        # chords from the barline after the verse: two to a bar in duple
        # time, a bar each in triple.
        chords = sorted({n[0] for n in amen})
        groups = []
        for t in chords:
            if groups and t - groups[-1][-1] < CLUSTER:
                groups[-1].append(t)
            else:
                groups.append([t])
        beat = 4 * Q // den
        each = L // 2 if (L // beat) % 2 == 0 else L
        aw = {t: verse_end + i * each for i, g in enumerate(groups) for t in g}
        ap = voices(amen, aw)
        for n in all_notes(ap):
            n[1] = each
        abars, b0 = [], verse_end
        while b0 < song_end(ap):
            abars.append((b0, L, num, den)); b0 += L
        for st in parts:
            for i in (0, 1):
                parts[st][i] += ap[st][i]
        bars += abars
        report['amen'] = True
        # "A-men" goes under the Amen, on the first verse's line.
        if words is not None:
            sop = [n for n in parts[0][0] if n[0] >= verse_end][:2]
            for n, (text, syl) in zip(sop, [('A', 'begin'), ('men.', 'end')] if len(sop) == 2 else [('Amen.', 'single')]):
                words[id(n)] = [(1, text, syl)]

    if override.get('notes'):
        report['note'] = override['notes']
    sc = build(parts, bars, meta, title, words)
    sc.write('musicxml', fp=out)
    report['bars'] = len(bars)
    return report


if __name__ == '__main__':
    src, out = sys.argv[1:3]
    n = os.path.basename(src)[4:-4]
    key = n.lstrip('0')
    print(json.dumps(convert(src, out, 'Hymn ' + n, load_overrides().get(key), load_book_facts().get(key))))
