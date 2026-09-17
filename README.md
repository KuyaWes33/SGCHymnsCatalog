# Trinity Hymnal Companion

The Trinity Hymnal, original 1961 edition, for a congregation to follow on
their own phones. It installs from a link, and once installed it works with
no signal at all, which is the point: the sanctuary is exactly where mobile
data tends to fail.

729 hymns. Tunes for every one of them. No account, no sign-up, no tracking,
no cost to run.

---

## Part one: installing it on a phone

This is the part to print on a card and hand out. The app is not in the App
Store or on Google Play, and it does not need to be. It installs straight
from the web address in about twenty seconds.

### iPhone and iPad

1. Open the link **in Safari**. This does not work from Chrome on an iPhone.
2. Tap the **Share** button at the bottom of the screen, the square with an
   arrow pointing up.
3. Scroll down the list and tap **Add to Home Screen**.
4. Tap **Add** in the top right.

The icon appears on the home screen like any other app.

### Android

1. Open the link in **Chrome**.
2. A bar usually appears at the bottom offering to install. Tap it.
3. If no bar appears, tap the **three dots** at the top right and choose
   **Install app**, or **Add to Home Screen**.

### On a computer

Open the link in any browser. It works as an ordinary web page. In Chrome or
Edge there is usually an install icon at the right-hand end of the address
bar if you want it in the applications list.

### Worth telling people

- **Open it once at home, while connected.** That first visit is when the
  hymns are stored on the phone. After that it opens without signal.
- **Open the installed icon, not a bookmark.** The installed version fills
  the screen with no address bar, which matters on a small phone.
- A QR code pointed at the address saves older members from typing. It
  removes the step where most people give up.

---

## Part two: what the app does

**Enter a hymn number.** The opening screen after Home is a large keypad,
because on a Sunday the whole task is usually "hymn four hundred and two".
The title appears as the number is typed, so a wrong digit is caught before
opening anything.

**Search the words.** Any line of any verse, including choruses. Useful when
someone remembers a phrase but not the number.

**Browse.** All 729 hymns by number, or alphabetically by first line.

**Save.** Keeps a short list for the day's service.

**Text size.** On the hymn screen itself rather than buried in settings,
adjustable from 16 to 34 point, and remembered.

**Keep screen on.** Stops the phone dimming mid-verse.

**Play the tune.** For learning a hymn that is unfamiliar. It plays all the
verses through, so it runs about three minutes.

**Dark mode.** Follows the phone's own setting, for when the lights go down.

---

## Part three: putting it online

The app is a folder of files. Any static host will serve it. These
instructions use GitHub Pages because it is free, it supports HTTPS, and it
takes a custom domain.

HTTPS is not optional. Offline support does not work without it.

### Steps

1. Create a **public repository** on GitHub.
2. Copy everything in this folder into it, keeping the folder structure.
3. In the repository, open **Settings**, then **Pages**, and set the source
   to the **main** branch.
4. Wait a minute, then open the address GitHub shows you.

### Getting the files in without the command line

Install **GitHub Desktop**, free for Windows and Mac. Clone the repository
once and it becomes an ordinary folder on your computer. Drop files in, type
a short note, click a button, and the change is live in about a minute.

The GitHub website also lets you drag files into a folder in the browser, but
it caps at 100 files per batch, and there are 761 tune files.

### A custom domain

Add it under Settings then Pages, point the domain's DNS at GitHub using the
records in their documentation, then tick **Enforce HTTPS** once the
certificate is issued. A `.org` reads right for a church.

### Limits

GitHub Pages allows a site of up to 1 GB and about 100 GB of traffic a month.
This app is roughly 8 MB including every tune, so neither is close.

---

## Part four: settings

Open `index.html` and find `var CONFIG` near the top of the script.

| Setting | What it does |
| --- | --- |
| `church` | The church name. Appears in the header, on the home screen, and in the About and Terms pages. |
| `logo` | Path to the church logo, for example `icons/logo.svg`. Leave empty and the app uses its own drawn mark. |
| `audio` | Already set up for the `tunes` folder. Nothing to change. |
| `scans` | Leave empty. See the copyright note below. |

Replace the files in `icons/` with the church logo when you have one. Keep
the same names and sizes. The maskable icon needs its artwork inside the
middle 60 percent, because Android crops the corners into a circle.

---

## Part five: how it works

**Offline.** A service worker stores the app and all the hymn text on the
phone at first visit. After that it opens from the phone's own storage.
Tunes are not stored up front, since that would be 7 MB nobody asked for.
Each tune is kept once someone plays it.

**Tunes.** The files are MIDI, which stores notes rather than sound, so all
761 come to 7 MB. Browsers cannot play MIDI on their own, so the app reads
the file and plays the notes itself using the browser's audio engine. No
player library, no soundfont to host, and the files keep the names the OPC
gave them. It sounds like a plain organ, which is what it is for.

Notes are scheduled a few seconds ahead rather than all at once, so a long
hymn does not stall an older phone when playback starts.

An iPhone files sound made this way under the same heading as a notification
chime, which the Ring/Silent switch mutes. That is why a tune would play on a
computer and be silent on a phone. The app now asks for the heading music
apps use, and keeps a silent clip running underneath the tune on older
phones that have no way to be asked, so the switch no longer decides whether
the congregation can hear the tune.

**Choruses.** The source prints a chorus once, unlabelled, straight after
verse one. Left alone, that makes the chorus look like verse two and pushes
the real verse two to three. 85 hymns now show the chorus separately, under
a Refrain heading, repeated after each verse. Hymn 218 carries a note
instead, because its repeat is in the singing rather than the printed text.

`chorus-check.txt` records what was decided for which hymn.

**Search.** Runs over all 16,367 lines in about 20 milliseconds, so it feels
instant while typing.

---

## Part six: changing things later

Edit, commit, and the change is live in about a minute. Phones that already
installed the app pick it up the next time they are opened with a
connection.

**When you change `index.html`, bump `VERSION` in `sw.js`** from `v1` to
`v2`, and so on. Without that, installed phones keep serving the old copy
from their own cache and your correction never arrives.

To change how a chorus is handled, edit `refrains.py` in the build tooling:
add the hymn number to `CONFIRMED_BLOCK2` to separate its chorus, or to
`NOT_A_CHORUS` to leave it numbered, then rerun the build.

---

## Part seven: what is not included, and why

**Hymn 27 is deliberately absent.** Unlike the rest of the 1961 edition,
which is public domain, its text is still under an active copyright held by
its publisher. The build script refuses to run if it is added back.

**The scanned pages from the printed hymnal are not included.** The hymn
texts are public domain, but the typesetting and layout of the book belong
to Great Commission Publications. Ask them in writing before adding scans.
Until `scans` is set, the Lyrics and Music page switch stays hidden, so
nobody meets a dead end.

**Check the edition.** This app follows the original 1961 numbering, which
runs to 730. If your congregation's books are a different edition, the
numbers will not match. The home screen names the edition on purpose, so a
mismatch is visible rather than quietly misleading.

---

## Part eight: files

```
index.html              the app, including all 729 hymns
manifest.webmanifest    makes it installable, sets the icon and launch screen
sw.js                   offline support
icons/                  app icons, placeholders until the church logo arrives
tunes/                  761 MIDI tunes from the OPC
chorus-check.txt        what was decided about each hymn's chorus
README.md               this file
```

---

## Part nine: if something goes wrong

**The app does not install on an iPhone.** It has to be Safari. Chrome on
iOS does not offer Add to Home Screen.

**A correction is not showing up.** Reopen the app with a connection: the
page is fetched fresh whenever there is one. If it still shows the old text,
the phone has no signal and is reading its stored copy.

**It does not work offline.** Check that the site is served over HTTPS and
that it has been opened at least once with a connection.

**A tune will not play.** Confirm the file exists in `tunes/` with the name
the app expects, `Th1_` plus the three digit hymn number, for example
`Th1_087.mid`.

**A tune is silent on a phone.** Check the volume first: the tune follows the
media volume, so turn it up with the side buttons while the tune is playing,
not before. On an iPhone, also check the Ring/Silent switch.

**A hymn looks wrong.** Report the number. Nearly everything is a one line
change in the data.

---

## Credits

Hymn texts and tunes are published freely by the Orthodox Presbyterian
Church at opc.org. The texts of the 1961 edition are public domain.

This app is not produced by, endorsed by, or affiliated with Great Commission
Publications or the Orthodox Presbyterian Church.

Typefaces are Source Serif 4 and Libre Franklin, both openly licensed.
