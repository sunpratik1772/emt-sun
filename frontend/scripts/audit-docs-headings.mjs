import { readFileSync, readdirSync } from 'fs'
import { join } from 'path'

function loadMd(text) {
  text = text.replace(/^#\s+[^\n]+\n*/, '', 1)
  text = text.replace(/^(>\s*[^\n]+\n)+\n*/, '', text.trimStart())
  text = text.replace(/^---\s*\n+/, '', text.trimStart())
  return text.trim()
}

function slugify(text) {
  return String(text)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '')
}

function makeHeadingId(text, used) {
  const base = slugify(text) || 'section'
  const count = used.get(base) ?? 0
  used.set(base, count + 1)
  return count === 0 ? base : `${base}-${count + 1}`
}

function scanHeadings(md, { skipFences = false } = {}) {
  const used = new Map()
  const all = []
  const toc = []
  let inFence = false
  for (const line of md.split('\n')) {
    if (skipFences && /^```/.test(line.trim())) {
      inFence = !inFence
      continue
    }
    if (skipFences && inFence) continue
    const m = line.match(/^(#{1,3})\s+(.+)/)
    if (!m) continue
    const level = m[1].length
    const text = m[2].replace(/[`*_~]/g, '').trim()
    const id = makeHeadingId(text, used)
    all.push({ level, text, id, line })
    if (level >= 2) toc.push({ level, text, id, line })
  }
  return { all, toc }
}

const docsDir = join(import.meta.dirname, '../../docs')
const files = readdirSync(docsDir).filter((f) => f.endsWith('.md') && f !== 'README.md')

for (const f of files.sort()) {
  const raw = readFileSync(join(docsDir, f), 'utf8')
  const md = loadMd(raw)
  const naive = scanHeadings(md)
  const smart = scanHeadings(md, { skipFences: true })
  const diff = naive.all.length - smart.all.length
  console.log(`=== ${f} ===`)
  console.log(`naive: ${naive.all.length} headings, ${naive.toc.length} toc`)
  console.log(`smart: ${smart.all.length} headings, ${smart.toc.length} toc${diff ? ` (diff ${diff})` : ''}`)
  if (diff) {
    const smartLines = new Set(smart.all.map((h) => h.line))
    console.log('false positives:')
    naive.all.filter((h) => !smartLines.has(h.line)).forEach((h) => console.log(`  L: ${h.line.slice(0, 100)}`))
  }
  console.log('TOC ids:', smart.toc.map((t) => t.id).join(', '))
  console.log()
}
