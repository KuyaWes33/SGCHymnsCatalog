// Read every line of text on a page image, with each syllable's position.
// Prints JSON: a list of lines, each {"top", "bottom", "syllables": [[left,
// right, text, hyphen after], ...]}, positions as fractions of the image.
// Usage: lyriclines <image.png>
import Vision
import AppKit

let img = NSImage(contentsOfFile: CommandLine.arguments[1])!
var rect = NSRect(origin: .zero, size: img.size)
let cg = img.cgImage(forProposedRect: &rect, context: nil, hints: nil)!
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
req.usesLanguageCorrection = false
try? VNImageRequestHandler(cgImage: cg).perform([req])

func esc(_ s: String) -> String {
    s.replacingOccurrences(of: "\\", with: "\\\\").replacingOccurrences(of: "\"", with: "\\\"")
}

var lines: [String] = []
for o in req.results ?? [] {
    guard let c = o.topCandidates(1).first else { continue }
    let s = c.string
    var syl: [String] = []
    var i = s.startIndex
    while i < s.endIndex {
        while i < s.endIndex, s[i] == " " { i = s.index(after: i) }
        var j = i
        while j < s.endIndex, s[j] != " " { j = s.index(after: j) }
        guard i < j, let b = try? c.boundingBox(for: i..<j)?.boundingBox else { i = j; continue }
        // A hyphenated word is shared out among its syllables by their
        // length in letters; each word's own box is the reliable one.
        let word = String(s[i..<j])
        let left = Double(b.minX), width = Double(b.width), total = Double(word.count)
        var start = 0
        let chars = Array(word)
        var k = 0
        while k <= chars.count {
            if k == chars.count || chars[k] == "-" || chars[k] == "\u{2013}" {
                if k > start {
                    let piece = String(chars[start..<k])
                    let x0 = left + width * Double(start) / total
                    let x1 = left + width * Double(k) / total
                    let hyphen = k < chars.count
                    syl.append("[\(x0), \(x1), \"\(esc(piece))\", \(hyphen)]")
                } else if k < chars.count, !syl.isEmpty {
                    // A hyphen standing alone: the syllable before it runs on.
                    syl[syl.count - 1] = syl[syl.count - 1].replacingOccurrences(of: ", false]", with: ", true]")
                }
                start = k + 1
            }
            k += 1
        }
        i = j
    }
    let top = 1 - Double(o.boundingBox.maxY), bottom = 1 - Double(o.boundingBox.minY)
    lines.append("{\"top\": \(top), \"bottom\": \(bottom), \"syllables\": [\(syl.joined(separator: ", "))]}")
}
print("[\(lines.joined(separator: ",\n"))]")
