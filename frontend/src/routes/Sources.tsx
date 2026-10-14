import { IconBook2 } from '@tabler/icons-react'
import { Disclosure } from '../components/Disclosure'
import { ANTHOLOGY_WORK_IDS, TEXTS, WORKS } from '../lib/works'
import {
  type TextCitationRange,
  ANTHOLOGY_TEXT_RANGES,
  KNOWN_SOURCE_DESC_MISMATCHES,
  PUBLISHERS,
  WORK_CODES,
  formatChunkRange,
} from '../lib/sourceMetadata'

const ZENODO_URL = 'https://zenodo.org/records/5075704#.YORkTjo6-Uk'

// Explicit, loud report rather than a silently-wrong value: 1888_EDIC's
// sourceDesc still describes the wrong work as of the last extraction
// (docs/xml_audit_report.md Sec. 5, scripts/extract_source_metadata.py).
// The publisher values below are unaffected — sourced from
// publicationStmt, not sourceDesc — but the mismatch itself is real and
// open, and must not be silently swallowed here.
if (KNOWN_SOURCE_DESC_MISMATCHES.length > 0) {
  console.warn(
    `Sources: known sourceDesc/title mismatch still open for ${KNOWN_SOURCE_DESC_MISMATCHES.join(
      ', ',
    )} (docs/xml_audit_report.md Sec. 5) — verify against data/raw/corpus/raw/src before ` +
      'trusting that field; the publisher values shown here come from publicationStmt instead.',
  )
}

const LEGEND_EXAMPLE_WORK = WORKS.find((w) => w.id === '1907_EC')!

// A citation code, `--ink-3` monospace — shared by work rows and text ranges.
function Code({ children }: { children: string }) {
  return (
    <span className="font-mono text-[11px]" style={{ color: 'var(--ink-3)' }}>
      {children}
    </span>
  )
}

// One individual text of an anthology: "L'effort intellectuel (1902) ·
// 1919_ES_c153 à 1919_ES_c203". Year from lib/works.ts:TEXTS; a text excluded from
// TEXTS has neither year nor range and renders as its bare title.
function TextLine({ workId, title, chunkRange }: { workId: string } & TextCitationRange) {
  const year = TEXTS[workId]?.find((t) => t.title === title)?.year
  return (
    <li>
      {title}
      {year !== undefined && ` (${year})`}
      {chunkRange && (
        <>
          <span style={{ color: 'var(--ink-3)' }}> · </span>
          <Code>{formatChunkRange(chunkRange)}</Code>
        </>
      )}
    </li>
  )
}

function SourceRow({ workId, isFirst }: { workId: string; isFirst: boolean }) {
  const work = WORKS.find((w) => w.id === workId)!
  const publisher = PUBLISHERS[workId]
  const texts = ANTHOLOGY_TEXT_RANGES[workId]
  const isAnthology = ANTHOLOGY_WORK_IDS.includes(workId)

  const titleAndYear = (
    <span>
      <span className="text-[13px] font-medium" style={{ color: 'var(--ink)' }}>
        {work.title}
      </span>{' '}
      <span className="text-[12px]" style={{ color: 'var(--ink-3)' }}>
        ({work.year})
      </span>
      <span className="text-[12px]" style={{ color: 'var(--ink-3)' }}>
        {' · '}
      </span>
      <Code>{workId}</Code>
    </span>
  )

  return (
    <div
      className="flex items-start justify-between gap-4 py-3"
      style={!isFirst ? { borderTop: '0.5px solid var(--hairline)' } : undefined}
    >
      <div className="min-w-0 flex-1">
        {isAnthology && texts ? (
          <Disclosure
            trigger={titleAndYear}
            expandLabel={`les textes de ${work.title}`}
            chevronPosition="leading"
            chevronSize={13}
            rowClassName="flex items-center gap-1.5"
          >
            <ul
              className="mt-1.5 pl-[19px] text-[11.5px]"
              style={{ color: 'var(--ink-2)', lineHeight: 1.9 }}
            >
              {texts.map((text) => (
                <TextLine key={text.title} workId={workId} {...text} />
              ))}
            </ul>
          </Disclosure>
        ) : (
          <div className="flex items-center gap-1.5">{titleAndYear}</div>
        )}
      </div>
      <span className="shrink-0 pt-0.5 text-[11px]" style={{ color: 'var(--ink-3)' }}>
        {publisher}
      </span>
    </div>
  )
}

// Full content and layout for the sidebar's "Sources" sub-page
// (docs/frontend.md) — supersedes the earlier short-paragraph placeholder
// from `feat/sidebar-restructure`.
export function Sources() {
  return (
    <div className="mx-auto max-w-3xl px-10 py-10">
      <div className="mb-8 flex flex-col items-center gap-2 text-center">
        <p
          className="font-wordmark text-[13px] uppercase"
          style={{ color: 'var(--ink-3)', letterSpacing: '2px' }}
        >
          Sources
        </p>
        <p className="font-wordmark text-[22px] font-medium" style={{ color: 'var(--ink)' }}>
          Les huit ouvrages majeurs d'Henri Bergson
        </p>
      </div>

      <p
        className="mx-auto mb-8 max-w-[480px] text-center text-[13px]"
        style={{ color: 'var(--ink-2)' }}
      >
        Le corpus interrogé par Bergson-RAG couvre l'intégralité des grandes œuvres publiées par
        Bergson de son vivant.
      </p>

      <p
        className="mx-auto mb-8 max-w-[560px] text-center text-[12px]"
        style={{ color: 'var(--ink-3)', lineHeight: 1.6 }}
        data-testid="citation-legend"
      >
        Dans les réponses, une référence comme <Code>{`${LEGEND_EXAMPLE_WORK.id}_c5`}</Code>{' '}
        désigne l'ouvrage (<Code>{LEGEND_EXAMPLE_WORK.id}</Code> = {LEGEND_EXAMPLE_WORK.title}) puis
        le numéro du passage dans cet ouvrage. Pour les deux recueils, la plage indiquée sous chaque
        texte permet de retrouver de quel texte vient un passage.
      </p>

      <div className="mx-auto mb-8 max-w-[560px]">
        {WORK_CODES.map((workId, i) => (
          <SourceRow key={workId} workId={workId} isFirst={i === 0} />
        ))}
      </div>

      <div
        className="mx-auto flex max-w-[560px] gap-3 rounded-[10px] py-5 px-6"
        style={{ background: 'var(--paper-2)' }}
      >
        <IconBook2 size={20} className="mt-0.5 shrink-0" style={{ color: 'var(--ink-3)' }} />
        <p className="text-[12.5px]" style={{ color: 'var(--ink-2)', lineHeight: 1.6 }}>
          Les textes ont été collectés sur le site de l'UQAC (Université du Québec à Chicoutimi),
          puis encodés en XML pour préserver la structure des ouvrages, dans le cadre d'un mémoire
          de recherche en humanités numériques —{' '}
          <a
            href={ZENODO_URL}
            target="_blank"
            rel="noopener"
            style={{ color: 'var(--red)' }}
          >
            lien vers la référence Zenodo
          </a>
          .
        </p>
      </div>
    </div>
  )
}
