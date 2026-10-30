# Sheet music from the tunes

These scripts turn the tune files in `tunes/` into printed-style scores, two
staves with soprano and alto above, tenor and bass below, so the app can
show notes without using the book's scans.

The scores are built in `build/`, which is not committed; `export.py` puts
the checked ones in `notes/`, where the app finds them.

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

The tune files have no words. Those come from the book, below.

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

## The words between the staves

As in the hymnal, each verse runs between the treble and bass staves, a
syllable under each note, with the chorus under its own music.

```
.venv/bin/python tools/notation/lyrics.py "/path/to/Trinity Hymnal.pdf" 1 14 677
.venv/bin/python tools/notation/build.py 1 14 677
```

`lyrics.py` reads each hymn's printed page: where each word breaks into
syllables, and where each syllable sits. The spelling always comes from the
app's own text, so a misread letter never reaches the score; a word the
reading missed is split by dictionary and fitted between its neighbours.
What it reads goes to `build/notation/lyrics/`, and `build.py` uses it
wherever it is there.

Tried on 11 hymns so far; 8 match the book. Known gaps:

- A chorus that starts part way through a line of music (441).
- Some syllables a note early after a dotted rhythm (13), or a bar early
  in a long line (78).
- Verses the book prints below the music, not between the staves, are left
  out for now.

## Putting the music in the app

```
.venv/bin/python tools/notation/export.py
```

Draws each score as `notes/<number>.svg`, sized for a phone, and writes
`notes/notes.json`: which hymns have music, and which carry their words.
Only hymns that converted cleanly and are not marked for checking go in;
checking one, and noting it in `overrides.json`, adds it at the next
export. A hymn whose words are wrong can keep its music without them:
`"words": false` in `overrides.json`.

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
lyrics.py         reads the words of each verse from the book
export.py         draws the checked scores into notes/ for the app
book-facts.json   what bookfacts.py read
review.py         the page for checking against the book
render.py         a quick SVG of one score, for looking at
overrides.json    hand corrections, and hymns confirmed by eye
book/             Swift helpers that read the scanned book (macOS)
requirements.txt  the Python packages, at the versions used
```
