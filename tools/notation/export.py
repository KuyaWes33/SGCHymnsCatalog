"""Put the scores in the app: one drawing per hymn in notes/.

    python tools/notation/build.py
    python tools/notation/export.py

Takes the scores build.py made and draws each as notes/<number>.svg, sized
for a phone, the app scales it to the screen. Only hymns that converted
cleanly and are not marked for checking go in; the rest are left out until
they are checked. notes/notes.json tells the app which hymns have music,
and which of those carry their words between the staves, so the app can
show the verses below the music for the others.
"""
import json, os, re, sys
import verovio

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
BUILD = os.path.join(ROOT, 'build', 'notation')
NOTES = os.path.join(ROOT, 'notes')


def hymn_of(name):
    """The hymn a tune file is the music for: Th1_014 is hymn 14, and of a
    hymn printed with two tunes, Th1_549f and Th1_549s, the first."""
    m = re.fullmatch(r'(\d{3})(f?)', name)
    return int(m.group(1)) if m else None


def shrink(svg):
    """Drop what a drawing shown as a picture never uses: the ids of every
    element, kept only where something refers to them, and data attributes."""
    styles = ''.join(re.findall(r'<style[^>]*>(.*?)</style>', svg, re.S))
    used = (set(re.findall(r'href="#([^"]+)"', svg)) | set(re.findall(r'url\(#([^)]+)\)', svg))
            | set(re.findall(r'#([A-Za-z][\w-]*)[\s,{.]', styles)))
    svg = re.sub(r'\sid="([^"]*)"', lambda m: m.group(0) if m.group(1) in used else '', svg)
    svg = re.sub(r'\sdata-[a-z-]+="[^"]*"', '', svg)
    return re.sub(r'>\s+<', '><', svg)


def main():
    report = json.load(open(os.path.join(BUILD, 'report.json')))
    tk = verovio.toolkit()
    tk.setOptions({'pageWidth': 1100, 'pageHeight': 60000, 'scale': 40, 'adjustPageHeight': True,
                   'header': 'none', 'footer': 'none', 'breaks': 'auto', 'lyricSize': 3.6,
                   'pageMarginLeft': 30, 'pageMarginRight': 30, 'pageMarginTop': 20, 'pageMarginBottom': 20,
                   'svgViewBox': True, 'svgRemoveXlink': True})
    os.makedirs(NOTES, exist_ok=True)
    have, words, skipped = [], [], []
    for name in sorted(report):
        n, r = hymn_of(name), report[name]
        # The app plays Th1_077.mid over Th1_077f.mid when both exist, so
        # the music shown must be that one too.
        if n is None or (name.endswith('f') and name[:-1] in report):
            continue
        if 'error' in r or r.get('check'):
            skipped.append(n)
            continue
        tk.loadFile(os.path.join(BUILD, name + '.musicxml'))
        svg = shrink(tk.renderToSVG(1))
        open(os.path.join(NOTES, f'{n:03d}.svg'), 'w').write(svg)
        have.append(n)
        if '<g class="verse"' in svg or 'class="syl"' in svg:
            words.append(n)
    # A drawing left from an earlier export for a hymn now held back goes.
    for f in os.listdir(NOTES):
        m = re.fullmatch(r'(\d{3})\.svg', f)
        if m and int(m.group(1)) not in have:
            os.remove(os.path.join(NOTES, f))
    json.dump({'have': sorted(have), 'words': sorted(words)}, open(os.path.join(NOTES, 'notes.json'), 'w'))
    size = sum(os.path.getsize(os.path.join(NOTES, f)) for f in os.listdir(NOTES))
    print(f'{len(have)} hymns with music, {len(words)} with their words; '
          f'{len(set(skipped))} held back for checking; {size / 1e6:.1f} MB')


if __name__ == '__main__':
    main()
