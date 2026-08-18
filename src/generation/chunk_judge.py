"""`judge_chunk` — on-demand, per-chunk LLM relevance judgment (docs/ROADMAP.md,
Sprint 6 — the `chunk_judgments` interface contract; implemented on this
branch, feat/judge-chunks).

Singular, not batched: `judge_chunk(query, chunk)` judges exactly one chunk
per call. This replaces the plural `judge_chunks(query, chunks)` signature
named in docs/ROADMAP.md's API-decomposition section — that batched design
was never built (no prior branch, no migration needed). One chunk in context
per call also makes cross-chunk contamination (the judge's read of chunk B
being colored by having seen chunk A in the same prompt) structurally
impossible, rather than a prompt-design precaution a batched version would
have had to build in.

The caller (eventually the frontend, Sprint 7) is responsible for
accumulating repeated `judge_chunk` calls into the
`chunk_judgments: dict[str, ChunkJudgment]` shape `generate_from_chunks`
already accepts (`src/generation/chunk_judgment.py`, committed ahead of this
branch in Sprint 6) — this module has no dict-shaped entry point itself, and
no persistence: durable storage of judgments across sessions remains a
separate, still-deferred Sprint 7 concern (docs/ROADMAP.md), not built here.

Same default judge as `generate_evaluation`'s faithfulness check
(`DEFAULT_JUDGE_MODEL`, `src/generation/faithfulness.py` — local 7B via
Ollama by default): the Sprint 6 judge calibration found the hosted Mistral
judge rates confirmed hallucinations as faithful, so the local judge is
preferred wherever a judge-shaped decision is made in this project. No
established reason to pick a different judge for this adjacent signal.

Not a RAGAS metric: `check_faithfulness` (src/generation/faithfulness.py)
already covers claim-vs-evidence entailment via `ragas.metrics.Faithfulness`.
This is a distinct query-vs-chunk relevance judgment with its own,
project-specific discrete label set (`ChunkJudgmentLabel` — pertinent /
partiellement pertinent / non pertinent, not a numeric score, consistent
with this project's general preference for discrete tiers over
false-precision numbers on judge-adjacent signals, e.g.
`RetrievalConfidenceTier` in `src/generation/signals.py`), so a hand-written
prompt plus a direct `litellm.completion` call is used instead of forcing it
through a RAGAS metric shaped for a different question.

## JSON parsing, with one retry

The local 7B judge is the same model `src/generation/faithfulness.py`
documents as prone to producing free-text instead of well-formed JSON under
context pressure (RAGAS needed its own internal fix-the-format retry for the
same failure mode against the same model). `judge_chunk` asks for a single
JSON object in the prompt (no `response_format` forcing — not all LiteLLM
providers support it uniformly, and this project has no established need for
it elsewhere) and retries once, with a corrective follow-up message, if the
first response doesn't parse as the expected object.
"""

from __future__ import annotations

import json
import re
from typing import Any, cast

import litellm
from litellm import ModelResponse

from src.generation.chunk_judgment import ChunkJudgment, ChunkJudgmentLabel
from src.generation.faithfulness import DEFAULT_JUDGE_MODEL, JUDGE_NUM_CTX, JUDGE_TEMPERATURE
from src.generation.signals import GenerationChunk

# Mirrors src/generation/faithfulness.py's own _OLLAMA_PROVIDERS check (not
# imported — that name is private to that module) for the same reason:
# JUDGE_NUM_CTX is an Ollama-specific request param, invalid on a hosted
# provider like the Mistral API fallback.
_OLLAMA_PROVIDERS = ("ollama", "ollama_chat")

_VALID_LABELS: frozenset[str] = frozenset({"pertinent", "partiellement pertinent", "non pertinent"})

_SYSTEM_PROMPT = (
    "Tu es un assistant qui évalue la pertinence d'un extrait de texte par rapport à une "
    "question, dans le cadre d'un corpus sur la philosophie de Henri Bergson. Tu réponds "
    "strictement au format JSON demandé, sans aucun texte hors de cet objet JSON."
)

_INSTRUCTIONS = (
    "Évalue si l'extrait ci-dessous permet de répondre à la question posée. Attribue une "
    'étiquette parmi exactement ces trois valeurs : "pertinent", "partiellement pertinent", '
    '"non pertinent". Rédige une justification de 2 à 4 phrases qui s\'appuie sur le contenu '
    "concret de l'extrait (une idée, une image ou un terme qui s'y trouve réellement) — jamais "
    "une formule générique qui vaudrait pour n'importe quel extrait. Réponds uniquement avec un "
    'objet JSON de la forme {"label": "...", "justification": "..."}, sans texte avant ni après.'
)

_RETRY_INSTRUCTION = (
    "Ta réponse précédente n'était pas un objet JSON valide de la forme "
    '{"label": "...", "justification": "..."}. Réponds à nouveau, uniquement avec cet objet '
    "JSON, sans aucun texte avant ou après."
)

_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


def _build_prompt(query: str, chunk: GenerationChunk) -> str:
    return (
        f"{_INSTRUCTIONS}\n\n"
        f"QUESTION :\n{query}\n\n"
        f"EXTRAIT [{chunk.chunk_id}] ({chunk.work_id}) :\n{chunk.text}"
    )


def _parse_response(content: str) -> ChunkJudgment:
    match = _JSON_OBJECT_PATTERN.search(content)
    if match is None:
        raise ValueError(f"judge_chunk: no JSON object found in judge response: {content!r}")
    parsed = json.loads(match.group(0))
    label = parsed.get("label")
    justification = parsed.get("justification")
    if label not in _VALID_LABELS:
        raise ValueError(f"judge_chunk: unexpected label {label!r} in judge response: {content!r}")
    if not isinstance(justification, str) or not justification.strip():
        raise ValueError(f"judge_chunk: empty justification in judge response: {content!r}")
    return {"label": cast(ChunkJudgmentLabel, label), "justification": justification.strip()}


def judge_chunk(
    query: str,
    chunk: GenerationChunk,
    model: str = DEFAULT_JUDGE_MODEL,
) -> ChunkJudgment:
    """One relevance judgment for one (query, chunk) pair — see the module
    docstring for why this is singular rather than the earlier, unbuilt
    `judge_chunks(query, chunks)` design, and for the retry-on-malformed-JSON
    behavior below.
    """
    _, provider, _, _ = litellm.get_llm_provider(model)
    extra_params: dict[str, Any] = (
        {"num_ctx": JUDGE_NUM_CTX} if provider in _OLLAMA_PROVIDERS else {}
    )

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _build_prompt(query, chunk)},
    ]

    last_error: ValueError | None = None
    for _attempt in range(2):
        response = litellm.completion(
            model=model, messages=messages, temperature=JUDGE_TEMPERATURE, **extra_params
        )
        # Never called with stream=True, so litellm always returns a
        # ModelResponse here, not a CustomStreamWrapper (src/generation/generate.py
        # narrows the same union the same way).
        assert isinstance(response, ModelResponse)
        content = response.choices[0].message.content or ""
        try:
            return _parse_response(content)
        except ValueError as error:
            last_error = error
            messages = [
                *messages,
                {"role": "assistant", "content": content},
                {"role": "user", "content": _RETRY_INSTRUCTION},
            ]
    assert last_error is not None
    raise last_error
