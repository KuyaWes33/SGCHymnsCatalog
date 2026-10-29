# Sheet music from the tunes

These scripts turn the tune files in `tunes/` into printed-style scores, two
staves with soprano and alto above, tenor and bass below, so the app can
show notes without using the book's scans.

Nothing here is used by the app yet. The scores are written to `build/`,
which is not committed or published.

## Setting up

Python 3.11 or later, then:

```
python3 -m venv .venv
.venv/bin/pip install -r tools/notation/requirements.txt
```

## Making the scores

```
.venv/bin/python tools/notation/build.py          every tune
.venv/bin/python tools/notation/build.py 14 100   just those hymns
```

Each tune becomes `build/notation/<number>.musicxml`, and
`build/notation/report.json` says how each one went: the pickup and where it
came from, how many fermatas were found, and whether the hymn needs checking.

## What the converter has to undo

The OPC files were made by scanning the printed hymnal and then played back
with a little human timing. They hold the right notes, but:

| In the file | What the converter does |
| --- | --- |
| Every verse is played, with a silence between | Keeps the first verse, and the Amen from the last |
| One silent beat before the music | Drops it |
| Every note a little late, later after each breath | Follows the lateness as it grows, and snaps what is left to the beat |
| A fermata played as extra beats | Takes the beats back out and prints a fermata |
| A bar split across a line break, read as two short bars | Joins them |
| A pickup written as a short first bar, or not at all | Uses it when written; otherwise asks the book (see below) |
| The Amen played slowly | Writes it as even chords from the next barline |
| Two parts on the same note, struck as one key twice | Pairs each release with the right note |

Words are not under the notes. The tune files have none; the app shows the
verses beneath the music.

## Where the first barline goes

Most of what can go wrong comes down to the pickup: put the first barline in
the wrong place and every bar after it is wrong too. About 280 tunes say
where it is. For the rest, the book does:
`book-facts.json` records, for each hymn, how many syllables of verse 1
come before its first barline in print, and the tune says how many beats
those notes take. The music alone is used only when the book could not be
read, and a hymn is marked for checking when the two disagree.

Checked against the tunes that do say, the book and the music agreeing was
right 97 times in 100. Where they disagreed the book was right about three
times in four, and the hymn is marked for checking.

`book-facts.json` is made once, from the scanned book:

```
.venv/bin/python tools/notation/bookfacts.py "/path/to/Trinity Hymnal.pdf"
```

It holds only those counts, so a build needs no scans.

## Checking against the book

```
.venv/bin/python tools/notation/review.py --book "/path/to/Trinity Hymnal.pdf"
```

This makes `build/notation/review.html`: each hymn's opening from the
scanned book beside the score made from its tune, the doubtful ones first.
Open it in a browser. Add `--check` for only the doubtful ones, or hymn
numbers for just those.

Reading the book uses macOS's own PDF and text recognition, through the
small Swift programs in `book/`, compiled the first time. The scans and the
crops made from them stay in `build/`: the book's typesetting belongs to its
publisher, so it is for checking only and never goes in the app.

## Correcting a hymn

When a score is wrong, add the hymn to `overrides.json` and build it again:

```json
{
 "14": { "pickup": 2, "notes": "two-beat pickup, checked against the book" }
}
```

`pickup` is in beats; 0 means none. The key is the number in the tune's file
name, `tunes/Th1_014.mid`, without the leading zeros.

## Files

```
midi2score.py     the converter, for one tune
build.py          every tune, with the report
bookfacts.py      reads where each hymn's first barline falls from the book
book-facts.json   what bookfacts.py read
review.py         the page for checking against the book
render.py         a quick SVG of one score, for looking at
overrides.json    hand corrections, and hymns confirmed by eye
book/             Swift helpers that read the scanned book (macOS)
requirements.txt  the Python packages, at the versions used
```
