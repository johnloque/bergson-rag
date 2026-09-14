import { describe, expect, it } from 'vitest'
import { rehypeLinkCitations } from './citationLinkPlugin'

// Pure HAST-transform tests, decoupled from React/react-markdown rendering
// (that composition is covered end-to-end in AnswerCard.test.tsx) — same
// split-of-concerns as lib/highlightMatching.test.ts vs.
// components/AnswerCard.test.tsx's own highlight-composition tests.

interface HastNode {
  type: string
  value?: string
  tagName?: string
  properties?: Record<string, unknown>
  children?: HastNode[]
  [key: string]: unknown
}

function textLeaf(value: string): HastNode {
  return { type: 'root', children: [{ type: 'text', value }] }
}

function href(chunkId: string) {
  return `/c/1/turn/2/chunk/${chunkId}`
}

describe('rehypeLinkCitations', () => {
  it('wraps a single known chunk_id citation in a link, text unchanged', () => {
    const tree = textLeaf('Une affirmation [1907_EC_c5].')
    rehypeLinkCitations([], href)(tree)

    const children = tree.children!
    expect(children.map((c) => c.value ?? `<${c.tagName}>`)).toEqual([
      'Une affirmation ',
      '[',
      '<a>',
      ']',
      '.',
    ])
    const link = children[2]
    expect(link.tagName).toBe('a')
    expect(link.properties).toEqual({ href: '/c/1/turn/2/chunk/1907_EC_c5' })
    expect(link.children).toEqual([{ type: 'text', value: '1907_EC_c5' }])
  })

  it('leaves a citation Layer 1 flagged as unknown as plain text, no link', () => {
    const tree = textLeaf('Une affirmation [9999_XX_c1].')
    rehypeLinkCitations(['9999_XX_c1'], href)(tree)

    const children = tree.children!
    // Split into surrounding text/bracket nodes, same as the linked case
    // (no `<a>` among them though) — reconstructing them must still
    // reproduce the original text exactly.
    expect(children.some((c) => c.tagName === 'a')).toBe(false)
    expect(children.map((c) => c.value ?? '').join('')).toBe('Une affirmation [9999_XX_c1].')
  })

  it('handles a multi-id bracket, linking only the known tokens', () => {
    // Real generate_from_chunks output shape (eval/results/ragas_checkpoint.jsonl,
    // Q007 generation_only): a single bracket, comma-separated chunk_ids.
    const tree = textLeaf('[1888_EDIC_c1, 1934_PM_c23, 1934_PM_c39]')
    rehypeLinkCitations(['1934_PM_c23'], href)(tree)

    const children = tree.children!
    const linkTexts = children.filter((c) => c.tagName === 'a').map((c) => c.children![0].value)
    expect(linkTexts).toEqual(['1888_EDIC_c1', '1934_PM_c39'])
    // The unknown token and every separator/bracket stay as plain text —
    // reconstructing every node's value/text back together must reproduce
    // the original string exactly.
    const flat = children
      .map((c) => (c.tagName === 'a' ? c.children![0].value : c.value))
      .join('')
    expect(flat).toBe('[1888_EDIC_c1, 1934_PM_c23, 1934_PM_c39]')
  })

  it('recurses into non-text children, e.g. a <mark> from a prior highlight pass', () => {
    const tree: HastNode = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'mark',
          children: [{ type: 'text', value: 'passage cité [1907_EC_c5]' }],
        },
      ],
    }
    rehypeLinkCitations([], href)(tree)

    const mark = tree.children![0]
    const link = mark.children!.find((c) => c.tagName === 'a')
    expect(link).toBeDefined()
    expect(link!.children).toEqual([{ type: 'text', value: '1907_EC_c5' }])
  })

  it('leaves text with no bracket citation untouched', () => {
    const tree = textLeaf('Aucune citation ici.')
    rehypeLinkCitations([], href)(tree)
    expect(tree.children).toEqual([{ type: 'text', value: 'Aucune citation ici.' }])
  })
})
