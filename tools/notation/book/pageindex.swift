// Read the large hymn numbers printed on each page of the scanned hymnal.
// Usage: pageindex <pdf> <first> <last>   prints one JSON line per page.
import PDFKit
import Vision
import AppKit

let args = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: args[1]))!
let first = Int(args[2])!, last = min(Int(args[3])!, doc.pageCount)

func render(_ page: PDFPage, scale: CGFloat) -> CGImage {
    let b = page.bounds(for: .mediaBox)
    let w = Int(b.width * scale), h = Int(b.height * scale)
    let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                        space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
    ctx.setFillColor(gray: 1, alpha: 1); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
    ctx.scaleBy(x: scale, y: scale)
    page.draw(with: .mediaBox, to: ctx)
    return ctx.makeImage()!
}

for i in first...last {
    guard let page = doc.page(at: i - 1) else { continue }
    let img = render(page, scale: 1400 / page.bounds(for: .mediaBox).width)
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    try? VNImageRequestHandler(cgImage: img).perform([req])
    var hits: [[String: Any]] = []
    for o in req.results ?? [] {
        guard let t = o.topCandidates(1).first?.string.trimmingCharacters(in: .whitespaces),
              t.range(of: "^\\d{1,3}$", options: .regularExpression) != nil else { continue }
        let bb = o.boundingBox
        hits.append(["n": Int(t)!, "x": Double(bb.minX), "y": Double(bb.minY), "h": Double(bb.height)])
    }
    let line = try! JSONSerialization.data(withJSONObject: ["page": i, "hits": hits])
    print(String(data: line, encoding: .utf8)!)
    fflush(stdout)
}
