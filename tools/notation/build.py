"""Convert every tune in tunes/ to a score, and report how each one went.

    python tools/notation/build.py            all tunes, into build/notation
    python tools/notation/build.py 14 100     just those hymns

Writes build/notation/<file>.musicxml for each tune and report.json beside
them. A hymn is marked for checking when its pickup is in doubt (the book
and the tune disagree, or neither is clear) or the file changes meter part
way.
"""
import json, os, sys, traceback
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import midi2score as M

TUNES = os.path.join(ROOT, 'tunes')
OUT = os.path.join(ROOT, 'build', 'notation')


def one(name):
    n = name[4:-4]                      # Th1_014.mid -> 014
    key = n.lstrip('0')
    over = M.load_overrides().get(key) or {}
    # The book's first line shows the hymn's first tune, Th1_549 or Th1_549f;
    # a second tune (Th1_549s) is printed further on, so it says nothing there.
    book, words = None, None
    if key.isdigit() or (key.endswith('f') and key[:-1].isdigit()):
        book = M.load_book_facts().get(key.rstrip('f'))
        # The words, where lyrics.py has read them from the book.
        path = os.path.join(OUT, 'lyrics', key.rstrip('f').zfill(3) + '.json')
        if os.path.exists(path) and over.get('words') is not False:
            words = json.load(open(path))
    try:
        r = M.convert(os.path.join(TUNES, name), os.path.join(OUT, n + '.musicxml'), 'Hymn ' + n, over, book, words)
        r['check'] = r['pickup_source'] in ('unsure', 'book, not tune') or r['mode'] == 'mixed meter'
        return n, r
    except Exception as e:
        return n, {'error': f'{type(e).__name__}: {e}', 'where': traceback.format_exc().splitlines()[-3].strip()}


def main(wanted):
    os.makedirs(OUT, exist_ok=True)
    names = sorted(f for f in os.listdir(TUNES) if f.startswith('Th1_') and f.endswith('.mid'))
    if wanted:
        keep = {w.zfill(3) for w in wanted}
        names = [f for f in names if f[4:-4] in keep or f[4:7] in keep]
    with ProcessPoolExecutor() as pool:
        results = dict(pool.map(one, names))
    path = os.path.join(OUT, 'report.json')
    old = json.load(open(path)) if wanted and os.path.exists(path) else {}
    old.update(results)
    json.dump(old, open(path, 'w'), indent=1, sort_keys=True)

    errors = [n for n, r in results.items() if 'error' in r]
    check = [n for n, r in results.items() if r.get('check')]
    print(f'{len(results) - len(errors)} converted, {len(errors)} failed, {len(check)} to check')
    for n in errors:
        print(f'  failed {n}: {results[n]["error"]}  ({results[n]["where"]})')


if __name__ == '__main__':
    main(sys.argv[1:])
