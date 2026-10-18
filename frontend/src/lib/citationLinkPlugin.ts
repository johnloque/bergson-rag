// rehype plugin (react-markdown `rehypePlugins`, alongside
// lib/segmentPlugin.ts): turns each `[chunk_id]` citation the generated
// answer contains into a link to Screen 4's chunk detail view
// (routes/ChunkDetail.tsx), focused on that chunk — but only when the
// chunk_id is one of the chunks passed to the generation that produced the
// answer (`knownChunkIds`, the generation's own `chunk_ids`).
//
// That is the same set Layer 1 checks citations against
// (`src/generation/guardrail.py`'s `check_structure`, fed
// `generation.chunk_ids` by `/evaluate`), so a token linked here is exactly
// a token Layer 1 will not list in `unknown_citations`. Checking against the
// generation's chunk ids directly, rather than waiting for
// `unknown_citations`, makes citations clickable as soon as the answer is
// generated — evaluation is manual and may never run
// (`feat/citations-clickable-at-generation`).
//
// Display: the brackets are dropped once a bracket links at least one
// token — the pill itself marks the citation, so `[`/`]` and the
// comma/semicolon separators were only visual noise. The link's text is
// still the bare chunk_id, exactly as the model wrote it
// (`src/generation/prompt.py`'s `CITATION_INSTRUCTION`, e.g. `1907_EC_c5`),
// never reformatted to `lib/citation.ts:formatCitation`'s work+year+
// paragraph format — chunk_id strings have a roughly constant length, which
// keeps inline paragraph flow stable. A token that isn't in the set keeps
// its own brackets as plain text (`[9999_XX_c1]`), so it still reads as the
// citation `CitationFlag` names. A bracket with no known token at all is
// left exactly as written — it may not be a citation at all (`[sic]`).
// Punctuation flush against a replaced bracket (`(`, `).`) is wrapped with
// its neighboring pill in a `whitespace-nowrap` span, so the two never land
// on separate lines.
//
// Same split-per-text-leaf approach as lib/segmentPlugin.ts: markdown
// structure is already parsed into the HAST tree by the time this runs, so
// a citation bracket inside a bold run or list item is still just text at
// that leaf — `<strong>`/`<li>` stay intact and the `<a>` nests inside them.
// `walk` below recurses into every non-text child regardless of tag name,
// including the sentence spans `rehypeSegments` produces when it runs first
// (components/AnswerCard.tsx), so a citation inside a checked sentence still
// becomes a link nested inside it.
//
// A single bracket may cite more than one chunk_id, comma/semicolon-
// separated (confirmed against real `generate_from_chunks` output, e.g.
// `[1888_EDIC_c1, 1934_PM_c23, 1934_PM_c39]`) — mirrors
// `src/generation/guardrail.py`'s `_extract_citations`, which splits on the
// same `[,;]\s*` pattern and checks each token independently.
//
// `CITATION_BRACKET_PATTERN` below is shape-agnostic on purpose — any
// bracketed text, not a chunk_id-shaped pattern — for the same reasons
// `_extract_citations` is (its docstring has the full rationale, including
// the real counterexample: `\d+_[A-Z]+_c\d+` would miss `1932_2S_c62`).

interface HastNode {
  type: string
  value?: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
  [key: string]: unknown
}

const CITATION_BRACKET_PATTERN = /\[([^[\]]+)\]/g
const TOKEN_SPLIT_PATTERN = /[,;]\s*/

export function rehypeLinkCitations(knownChunkIds: readonly string[], hrefFor: (chunkId: string) => string) {
  const known = new Set(knownChunkIds)
  return function transformer(tree: HastNode) {
    walk(tree, known, hrefFor)
  }
}

function walk(node: HastNode, known: Set<string>, hrefFor: (chunkId: string) => string) {
  if (!node.children) return
  const nextChildren: HastNode[] = []
  for (const child of node.children) {
    if (child.type === 'text' && typeof child.value === 'string') {
      nextChildren.push(...linkifyTextNode(child.value, known, hrefFor))
    } else {
      walk(child, known, hrefFor)
      nextChildren.push(child)
    }
  }
  node.children = nextChildren
}

function textNode(value: string): HastNode {
  return { type: 'text', value }
}

function linkifyTextNode(value: string, known: Set<string>, hrefFor: (chunkId: string) => string): HastNode[] {
  const nodes: HastNode[] = []
  let cursor = 0
  CITATION_BRACKET_PATTERN.lastIndex = 0
  let match: RegExpExecArray | null
  while ((match = CITATION_BRACKET_PATTERN.exec(value))) {
    const tokens = match[1]
      .split(TOKEN_SPLIT_PATTERN)
      .map((t) => t.trim())
      .filter(Boolean)
    if (!tokens.some((t) => known.has(t))) continue
    // Punctuation written flush against the bracket — `(` before, `).` or
    // `),` after, as in the model's frequent `([1907_EC_c16]).` — is kept on
    // the same line as the pill it touches (`gluedBefore`/`gluedAfter`), so
    // a line never ends on a lone `(` or starts on a lone `)`. Stops at
    // whitespace, and at `[` so a following citation is left to the next
    // iteration.
    const before = value.slice(cursor, match.index)
    const gluedBefore = /\S*$/.exec(before)![0]
    const end = match.index + match[0].length
    const gluedAfter = /^[^\s[]*/.exec(value.slice(end))![0]
    const plain = before.slice(0, before.length - gluedBefore.length)
    if (plain) nodes.push(textNode(plain))
    const pills = tokens.map((token) =>
      known.has(token)
        ? { type: 'element', tagName: 'a', properties: { href: hrefFor(token) }, children: [textNode(token)] }
        : textNode(`[${token}]`),
    )
    pills.forEach((pill, i) => {
      // A plain space between tokens, so a multi-id citation can still wrap
      // between its pills.
      if (i > 0) nodes.push(textNode(' '))
      const lead = i === 0 ? gluedBefore : ''
      const trail = i === pills.length - 1 ? gluedAfter : ''
      nodes.push(
        lead || trail
          ? {
              type: 'element',
              tagName: 'span',
              properties: { className: ['whitespace-nowrap'] },
              children: [...(lead ? [textNode(lead)] : []), pill, ...(trail ? [textNode(trail)] : [])],
            }
          : pill,
      )
    })
    cursor = end + gluedAfter.length
    CITATION_BRACKET_PATTERN.lastIndex = cursor
  }
  if (nodes.length === 0) return [textNode(value)]
  if (cursor < value.length) nodes.push(textNode(value.slice(cursor)))
  return nodes
}
