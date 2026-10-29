// Render one page of the scanned hymnal to PNG at a chosen width, optionally
// cropped to a band given as fractions of the page height from the top.
// Usage: pagepng <pdf> <page> <width in pixels> <out.png> [topFraction bottomFraction]
import PDFKit
import AppKit

let a = CommandLine.arguments
let doc = PDFDocument(url: URL(fileURLWithPath: a[1]))!
let page = doc.page(at: Int(a[2])! - 1)!
let scale = CGFloat(Double(a[3])!) / page.bounds(for: .mediaBox).width
let b = page.bounds(for: .mediaBox)
let w = Int(b.width * scale), h = Int(b.height * scale)
let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
                    space: CGColorSpaceCreateDeviceGray(), bitmapInfo: CGImageAlphaInfo.none.rawValue)!
ctx.setFillColor(gray: 1, alpha: 1); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))
ctx.scaleBy(x: scale, y: scale)
page.draw(with: .mediaBox, to: ctx)
var img = ctx.makeImage()!
if a.count >= 7 {
    let top = Double(a[5])!, bottom = Double(a[6])!
    img = img.cropping(to: CGRect(x: 0, y: Int(Double(h) * top), width: w, height: Int(Double(h) * (bottom - top))))!
}
let rep = NSBitmapImageRep(cgImage: img)
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[4]))
