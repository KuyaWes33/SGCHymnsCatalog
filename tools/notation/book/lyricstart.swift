// Find the syllables of verse 1 under the first line of music. Each sits
// under its note, so their positions say where the notes are.
// Prints JSON {"y": top of the line, "syllables": [[left, right], ...]} as
// fractions of the image, left to right, or {} when there is no verse 1.
// Usage: lyricstart <image.png>
import Vision
import AppKit

let img = NSImage(contentsOfFile: CommandLine.arguments[1])!
var rect = NSRect(origin: .zero, size: img.size)
let cg = img.cgImage(forProposedRect: &rect, context: nil, hints: nil)!
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
try? VNImageRequestHandler(cgImage: cg).perform([req])
let found = req.results ?? []

// The line that starts "1.", highest on the page: the first system's verse 1.
var start: (VNRecognizedTextObservation, VNRecognizedText, String.Index)? = nil
for o in found {
    guard let c = o.topCandidates(1).first,
          let m = c.string.range(of: "^\\s*1\\s*[.,]\\s*", options: .regularExpression) else { continue }
    if start == nil || o.boundingBox.maxY > start!.0.boundingBox.maxY { start = (o, c, m.upperBound) }
}
guard let (line, _, _) = start else { print("{}"); exit(0) }
let mid = line.boundingBox.midY, tall = line.boundingBox.height

// The rest of that line may come back as several pieces; take every piece at
// the same height. Each word's box is reliable; a hyphenated word is shared
// out among its syllables by their length in letters.
var syl: [(Double, Double)] = []
for o in found where abs(o.boundingBox.midY - mid) < tall * 0.5 {
    guard let c = o.topCandidates(1).first else { continue }
    let s = c.string
    var i = s.startIndex
    if let m = s.range(of: "^\\s*1\\s*[.,]\\s*", options: .regularExpression) { i = m.upperBound }
    while i < s.endIndex {
        while i < s.endIndex, s[i] == " " { i = s.index(after: i) }
        var j = i
        while j < s.endIndex, s[j] != " " { j = s.index(after: j) }
        let word = String(s[i..<j])
        let pieces = word.split(whereSeparator: { "-\u{2013}".contains($0) }).map(String.init)
        if i < j, !pieces.isEmpty, let b = try? c.boundingBox(for: i..<j)?.boundingBox {
            let total = Double(word.count), left = Double(b.minX), width = Double(b.width)
            var at = 0.0
            for p in pieces {
                let k = Double(word.distance(from: word.startIndex, to: word.range(of: p, range: word.index(word.startIndex, offsetBy: Int(at))..<word.endIndex)!.lowerBound))
                let x0 = left + width * k / total, x1 = left + width * (k + Double(p.count)) / total
                syl.append((x0, x1))
                at = k + Double(p.count)
            }
        }
        i = j
    }
}
syl.sort { $0.0 < $1.0 }
// Overlapping pieces can report the same syllable twice.
var kept: [(Double, Double)] = []
for x in syl where kept.isEmpty || x.0 - kept.last!.0 > 0.004 { kept.append(x) }
syl = kept
let parts = syl.map { "[\($0.0), \($0.1)]" }.joined(separator: ", ")
print("{\"y\": \(1 - Double(line.boundingBox.maxY)), \"syllables\": [\(parts)]}")
