import type { SegmentOut } from '../api/types'
import type { SegmentStatus } from './segmentVerdicts'

// rehype plugin (react-markdown `rehypePlugins`): wraps every answer
// sentence the faithfulness judge drew claims from in a
// `<span data-segment-id data-segment-status>`, which AnswerCard renders as
// a colored, clickable passage (components/AnswerCard.tsx).
//
// Segments come from the backend (src/generation/segmentation.py) as
// character offsets into the raw markdown answer, while this runs on the
// rendered tree, where markdown syntax is gone (`**`, list markers, a list
// item's continuation indent). The bridge is each text node's own
// `position` — its offsets in that same markdown source, kept by
// react-markdown's parser — so a text leaf is mapped back to source offsets
// character by character, never by searching for the sentence's text.
//
// A sentence spanning several text leaves (part bold, part plain, or a
// citation link the next plugin carves out) becomes several spans with the
// same `data-segment-id`, each nested inside its own `<strong>`/`<li>` etc.
// so markdown structure is untouched. Only the first one gets
// `data-segment-first`, so a sentence is a single keyboard stop.
// `rehypeLinkCitations` runs after this plugin and recurses into these
// spans, so a citation inside a sentence still becomes a link.

interface HastNode {
  type: string
  value?: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
  position?: { start?: { offset?: number }; end?: { offset?: number } }
  [key: string]: unknown
}

export function rehypeSegments(
  source: string,
  segments: readonly SegmentOut[],
  statusById: ReadonlyMap<number, SegmentStatus>,
) {
  const colored = segments.filter((segment) => statusById.has(segment.id))
  return function transformer(tree: HastNode) {
    if (colored.length === 0) return
    walk(tree, { source, colored, statusById, seen: new Set() })
  }
}

interface WalkState {
  source: string
  colored: readonly SegmentOut[]
  statusById: ReadonlyMap<number, SegmentStatus>
  seen: Set<number>
}

function walk(node: HastNode, state: WalkState) {
  if (!node.children) return
  const nextChildren: HastNode[] = []
  for (const child of node.children) {
    if (child.type === 'text' && typeof child.value === 'string') {
      nextChildren.push(...splitTextNode(child, state))
    } else {
      walk(child, state)
      nextChildren.push(child)
    }
  }
  node.children = nextChildren
}

function splitTextNode(node: HastNode, state: WalkState): HastNode[] {
  const value = node.value as string
  const start = node.position?.start?.offset
  const end = node.position?.end?.offset
  if (start === undefined || end === undefined || value === '') return [node]

  const offsets = sourceOffsets(value, state.source, start, end)
  const segmentAt = (i: number) =>
    state.colored.find((s) => offsets[i] >= s.start && offsets[i] < s.end)?.id ?? null

  const nodes: HastNode[] = []
  let runStart = 0
  let runSegment = segmentAt(0)
  for (let i = 1; i <= value.length; i++) {
    const segment = i < value.length ? segmentAt(i) : undefined
    if (segment === runSegment) continue
    nodes.push(runNode(value.slice(runStart, i), runSegment, state))
    runStart = i
    runSegment = segment ?? null
  }
  return nodes
}

function runNode(text: string, segmentId: number | null, state: WalkState): HastNode {
  const textNode: HastNode = { type: 'text', value: text }
  if (segmentId === null) return textNode
  const first = !state.seen.has(segmentId)
  state.seen.add(segmentId)
  return {
    type: 'element',
    tagName: 'span',
    properties: {
      dataSegmentId: String(segmentId),
      dataSegmentStatus: state.statusById.get(segmentId),
      ...(first ? { dataSegmentFirst: 'true' } : {}),
    },
    children: [textNode],
  }
}

// The source offset of each character of a rendered text leaf. A plain leaf
// is a verbatim slice of the source; otherwise (a backslash escape, a list
// item's continuation indent stripped by the parser), characters are
// matched greedily, in order, skipping source characters that didn't make
// it into the rendered text.
export function sourceOffsets(value: string, source: string, start: number, end: number): number[] {
  if (source.slice(start, end) === value) return Array.from(value, (_, i) => start + i)
  const offsets: number[] = []
  let j = start
  // Indexed per UTF-16 unit, like `value.slice` in splitTextNode — not
  // per code point.
  for (let i = 0; i < value.length; i++) {
    let k = j
    while (k < end && source[k] !== value[i]) k++
    if (k < end) j = k
    offsets.push(Math.min(j, end - 1))
    j = Math.min(j + 1, end)
  }
  return offsets
}
