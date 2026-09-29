import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url'

export interface PositionedText {
  str: string
  x: number
  y: number
}

/** Group positioned text into visual lines: top to bottom, then left to right. */
export function groupTextItems(items: PositionedText[], tolerance = 2.5): string[] {
  const sorted = items.filter((i) => i.str.trim()).sort((a, b) => b.y - a.y || a.x - b.x)
  const lines: PositionedText[][] = []
  for (const item of sorted) {
    const current = lines[lines.length - 1]
    const baseline = current?.[0]?.y
    if (current && baseline !== undefined && Math.abs(baseline - item.y) <= tolerance) current.push(item)
    else lines.push([item])
  }
  return lines.map((line) =>
    line
      .sort((a, b) => a.x - b.x)
      .map((i) => i.str.trim())
      .join(' '),
  )
}

/**
 * Read a PDF's text lines in the browser. The file never leaves the device: pdf.js runs in a
 * worker served by this app, and nothing is uploaded.
 */
export async function readPdfLines(file: File): Promise<string[]> {
  const pdfjs = await import('pdfjs-dist')
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl
  const task = pdfjs.getDocument({ data: new Uint8Array(await file.arrayBuffer()) })
  try {
    const doc = await task.promise
    const lines: string[] = []
    for (let n = 1; n <= doc.numPages; n++) {
      const content = await (await doc.getPage(n)).getTextContent()
      const items: PositionedText[] = []
      for (const item of content.items) {
        if ('str' in item) items.push({ str: item.str, x: Number(item.transform[4]), y: Number(item.transform[5]) })
      }
      lines.push(...groupTextItems(items))
    }
    return lines
  } finally {
    await task.destroy()
  }
}
