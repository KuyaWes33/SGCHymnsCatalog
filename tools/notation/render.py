"""Draw scores as SVG, for a quick look: each x.musicxml becomes x.svg.

    python tools/notation/render.py build/notation/014.musicxml
"""
import sys
import verovio

tk = verovio.toolkit()
tk.setOptions({"pageWidth": 1400, "pageHeight": 4000, "scale": 45, "adjustPageHeight": True,
               "footer": "none", "header": "none", "breaks": "auto"})
for f in sys.argv[1:]:
    tk.loadFile(f)
    open(f.replace('.musicxml', '.svg'), 'w').write(tk.renderToSVG(1))
    print(f, 'pages', tk.getPageCount())
