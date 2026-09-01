import type { ClaimVerdictOut } from '../api/types'
import { findHighlightRanges } from './highlightMatching'

// A minimal HAST (react-markdown's parsed tree) node shape — just enough to
// walk it and splice text nodes, without pulling in `@types/hast` as a
// dependency for a handful of fields.
interface HastNode {
  type: string
  value?: string
  children?: HastNode[]
  [key: string]: unknown
}

// rehype plugin (react-markdown `rehypePlugins`): after markdown is parsed
// into its element tree (lists, bold, etc. already structured), walks every
// text leaf and wraps any faithfulness-flagged verbatim quote it contains in
// a `<mark>` element — same matching rule as the plain-text highlighter
// (lib/highlightMatching.ts), just applied per text node instead of over
// one flat string. This is what keeps markdown structure and the highlight
// composing correctly: a quote entirely inside a bold run or a list item is
// still just text at that leaf, split like any other text node, so
// `<strong>`/`<li>` etc. are untouched and the `<mark>` nests inside them
// rather than being stripped or misplaced by the parser.
export function rehypeHighlightClaims(claims: ClaimVerdictOut[]) {
  return function transformer(tree: HastNode) {
    walk(tree, claims)
  }
}

function walk(node: HastNode, claims: ClaimVerdictOut[]) {
  if (!node.children) return
  const nextChildren: HastNode[] = []
  for (const child of node.children) {
    if (child.type === 'text' && typeof child.value === 'string') {
      nextChildren.push(...splitTextNode(child.value, claims))
    } else {
      walk(child, claims)
      nextChildren.push(child)
    }
  }
  node.children = nextChildren
}

function splitTextNode(value: string, claims: ClaimVerdictOut[]): HastNode[] {
  const ranges = findHighlightRanges(value, claims)
  if (ranges.length === 0) return [{ type: 'text', value }]

  const nodes: HastNode[] = []
  let cursor = 0
  for (const range of ranges) {
    if (range.start > cursor) nodes.push({ type: 'text', value: value.slice(cursor, range.start) })
    nodes.push({
      type: 'element',
      tagName: 'mark',
      properties: {},
      children: [{ type: 'text', value: value.slice(range.start, range.end) }],
    })
    cursor = range.end
  }
  if (cursor < value.length) nodes.push({ type: 'text', value: value.slice(cursor) })
  return nodes
}
