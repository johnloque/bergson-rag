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
  it('replaces a known chunk_id citation with a link, brackets dropped', () => {
    const tree = textLeaf('Une affirmation [1907_EC_c5].')
    rehypeLinkCitations(['1907_EC_c5'], href)(tree)

    const children = tree.children!
    expect(children.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['Une affirmation ', '<span>'])
    // The flush period rides along with the pill (see the punctuation tests below).
    const [link, period] = children[1].children!
    expect(period).toEqual({ type: 'text', value: '.' })
    expect(link.tagName).toBe('a')
    expect(link.properties).toEqual({ href: '/c/1/turn/2/chunk/1907_EC_c5' })
    expect(link.children).toEqual([{ type: 'text', value: '1907_EC_c5' }])
  })

  it('leaves a citation outside the generation chunk set exactly as written', () => {
    const tree = textLeaf('Une affirmation [9999_XX_c1].')
    rehypeLinkCitations(['1907_EC_c5'], href)(tree)
    expect(tree.children).toEqual([{ type: 'text', value: 'Une affirmation [9999_XX_c1].' }])
  })

  it('leaves non-citation bracketed text untouched', () => {
    const tree = textLeaf('Il écrit [sic] ceci.')
    rehypeLinkCitations(['1907_EC_c5'], href)(tree)
    expect(tree.children).toEqual([{ type: 'text', value: 'Il écrit [sic] ceci.' }])
  })

  it('handles a multi-id bracket: known tokens linked, unknown ones keep their own brackets', () => {
    // Real generate_from_chunks output shape (eval/results/ragas_checkpoint.jsonl,
    // Q007 generation_only): a single bracket, comma-separated chunk_ids.
    const tree = textLeaf('[1888_EDIC_c1, 1934_PM_c23, 1934_PM_c39]')
    rehypeLinkCitations(['1888_EDIC_c1', '1934_PM_c39'], href)(tree)

    const children = tree.children!
    const linkTexts = children.filter((c) => c.tagName === 'a').map((c) => c.children![0].value)
    expect(linkTexts).toEqual(['1888_EDIC_c1', '1934_PM_c39'])
    const flat = children.map((c) => (c.tagName === 'a' ? c.children![0].value : c.value)).join('')
    expect(flat).toBe('1888_EDIC_c1 [1934_PM_c23] 1934_PM_c39')
  })

  it('recurses into non-text children, e.g. a sentence span from rehypeSegments', () => {
    const tree: HastNode = {
      type: 'root',
      children: [
        {
          type: 'element',
          tagName: 'span',
          children: [{ type: 'text', value: 'passage cité [1907_EC_c5]' }],
        },
      ],
    }
    rehypeLinkCitations(['1907_EC_c5'], href)(tree)

    const span = tree.children![0]
    const link = span.children!.find((c) => c.tagName === 'a')
    expect(link).toBeDefined()
    expect(link!.children).toEqual([{ type: 'text', value: '1907_EC_c5' }])
  })

  it('keeps punctuation flush against the citation on the same line as the pill', () => {
    // Real answer shape (conversation 65's neighbors): `([chunk_id]).`
    const tree = textLeaf('un registre ([1907_EC_c16]). En')
    rehypeLinkCitations(['1907_EC_c16'], href)(tree)

    const children = tree.children!
    expect(children.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['un registre ', '<span>', ' En'])
    const glued = children[1]
    expect(glued.properties).toEqual({ className: ['whitespace-nowrap'] })
    expect(glued.children!.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['(', '<a>', ').'])
  })

  it('glues the opening parenthesis to the first pill and the closing one to the last', () => {
    const tree = textLeaf('voir ([1888_EDIC_c1, 1934_PM_c39]), puis')
    rehypeLinkCitations(['1888_EDIC_c1', '1934_PM_c39'], href)(tree)

    const children = tree.children!
    expect(children.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['voir ', '<span>', ' ', '<span>', ' puis'])
    expect(children[1].children!.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['(', '<a>'])
    expect(children[3].children!.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['<a>', '),'])
  })

  it('does not glue across whitespace, nor into a following citation', () => {
    const tree = textLeaf('fil [1907_EC_c5][1907_EC_c6] suite')
    rehypeLinkCitations(['1907_EC_c5', '1907_EC_c6'], href)(tree)

    const children = tree.children!
    expect(children.map((c) => c.value ?? `<${c.tagName}>`)).toEqual(['fil ', '<a>', '<a>', ' suite'])
  })

  it('leaves text with no bracket citation untouched', () => {
    const tree = textLeaf('Aucune citation ici.')
    rehypeLinkCitations(['1907_EC_c5'], href)(tree)
    expect(tree.children).toEqual([{ type: 'text', value: 'Aucune citation ici.' }])
  })
})
