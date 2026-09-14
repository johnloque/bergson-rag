// rehype plugin (react-markdown `rehypePlugins`, alongside
// lib/highlightPlugin.ts): wraps each `[chunk_id]` citation the generated
// answer contains in a link to Screen 4's chunk detail view
// (routes/ChunkDetail.tsx), focused on that chunk — but only when the
// chunk_id is confirmed present in the generation's actual input chunk set.
// That check is Layer 1's own (`src/generation/guardrail.py`'s
// `check_structure`, `StructuralCheck.unknown_citations`) — reused directly
// via the `unknownCitations` argument below, not recomputed a second,
// independent time: a citation already in that list keeps its existing
// `CitationFlag` treatment (docs/anti_hallucination_guardrails.md) and is
// left as plain text here.
//
// Display text is untouched — the link's text content is the bare chunk_id
// string, exactly as the model wrote it (`src/generation/prompt.py`'s
// `CITATION_INSTRUCTION`, e.g. `[1907_EC_c5]`), never reformatted to the
// work+year+paragraph citation format `lib/citation.ts:formatCitation` uses
// elsewhere (chunk rail, included-chunks bullet list) — chunk_id strings
// have a roughly constant length, which keeps inline paragraph flow stable;
// the full citation format's length varies too much (especially for
// anthology-work text citations) to substitute inline without disrupting
// layout. Only the surrounding brackets/separators stay as plain text; the
// `<a>` wraps just the chunk_id token itself, so its `textContent` is
// exactly the chunk_id.
//
// Same split-per-text-leaf approach as lib/highlightPlugin.ts: markdown
// structure is already parsed into the HAST tree by the time this runs, so
// a citation bracket inside a bold run or list item is still just text at
// that leaf — `<strong>`/`<li>` stay intact and the `<a>` nests inside them
// rather than being stripped or misplaced. `walk` below recurses into every
// non-text child regardless of tag name, including a `<mark>` produced by
// `rehypeHighlightClaims` when it runs first in the `rehypePlugins` array
// (components/AnswerCard.tsx) — this is what lets a citation bracket
// sitting inside a faithfulness-flagged quote still become a link nested
// inside the `<mark>`, rather than one transform clobbering the other.
//
// A single bracket may cite more than one chunk_id, comma/semicolon-
// separated (confirmed against real `generate_from_chunks` output, e.g.
// `[1888_EDIC_c1, 1934_PM_c23, 1934_PM_c39]`) — mirrors
// `src/generation/guardrail.py`'s `_extract_citations`, which splits on the
// same `[,;]\s*` pattern and checks each token independently. Each token is
// linked/left-plain independently here too, so a mixed bracket (one known
// id, one Layer-1-flagged unknown one) renders correctly: only the known
// token becomes a link, the rest of the bracket (brackets, separators, the
// unknown token) stays plain text.
//
// `CITATION_BRACKET_PATTERN` below is shape-agnostic on purpose — any
// bracketed text, not a chunk_id-shaped pattern — for the same two reasons
// `_extract_citations` is (`src/generation/guardrail.py`'s docstring has
// the full rationale, including the concrete real-data counterexample: a
// shape pattern like `\d+_[A-Z]+_c\d+` would fail to match the real
// `1932_2S_c62` chunk_id, since `1932_2S`'s segment after the first
// underscore starts with a digit). The two extractors have to agree on
// what counts as a citation candidate, which is why this one is written to
// match, not independently designed.

interface HastNode {
  type: string
  value?: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
  [key: string]: unknown
}

const CITATION_BRACKET_PATTERN = /\[([^[\]]+)\]/g
const TOKEN_SPLIT_PATTERN = /([,;]\s*)/

export function rehypeLinkCitations(unknownCitations: readonly string[], hrefFor: (chunkId: string) => string) {
  const unknown = new Set(unknownCitations)
  return function transformer(tree: HastNode) {
    walk(tree, unknown, hrefFor)
  }
}

function walk(node: HastNode, unknown: Set<string>, hrefFor: (chunkId: string) => string) {
  if (!node.children) return
  const nextChildren: HastNode[] = []
  for (const child of node.children) {
    if (child.type === 'text' && typeof child.value === 'string') {
      nextChildren.push(...linkifyTextNode(child.value, unknown, hrefFor))
    } else {
      walk(child, unknown, hrefFor)
      nextChildren.push(child)
    }
  }
  node.children = nextChildren
}

function textNode(value: string): HastNode {
  return { type: 'text', value }
}

function linkifyTextNode(
  value: string,
  unknown: Set<string>,
  hrefFor: (chunkId: string) => string,
): HastNode[] {
  const nodes: HastNode[] = []
  let cursor = 0
  CITATION_BRACKET_PATTERN.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = CITATION_BRACKET_PATTERN.exec(value))) {
    if (match.index > cursor) nodes.push(textNode(value.slice(cursor, match.index)))
    nodes.push(textNode('['))
    nodes.push(...linkifyBracketContent(match[1], unknown, hrefFor))
    nodes.push(textNode(']'))
    cursor = match.index + match[0].length
  }
  if (nodes.length === 0) return [textNode(value)]
  if (cursor < value.length) nodes.push(textNode(value.slice(cursor)))
  return nodes
}

function linkifyBracketContent(
  inner: string,
  unknown: Set<string>,
  hrefFor: (chunkId: string) => string,
): HastNode[] {
  const nodes: HastNode[] = []
  for (const part of inner.split(TOKEN_SPLIT_PATTERN)) {
    if (part === '') continue
    if (/^[,;]\s*$/.test(part)) {
      nodes.push(textNode(part))
      continue
    }
    const trimmed = part.trim()
    if (!trimmed || unknown.has(trimmed)) {
      nodes.push(textNode(part))
      continue
    }
    const leadEnd = part.indexOf(trimmed)
    const lead = part.slice(0, leadEnd)
    const trail = part.slice(leadEnd + trimmed.length)
    if (lead) nodes.push(textNode(lead))
    nodes.push({
      type: 'element',
      tagName: 'a',
      properties: { href: hrefFor(trimmed) },
      children: [textNode(trimmed)],
    })
    if (trail) nodes.push(textNode(trail))
  }
  return nodes
}
