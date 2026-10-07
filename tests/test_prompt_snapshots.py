"""Golden snapshots of every prompt this project sends to an LLM
(refactor/prompts-to-files, docs/prompts.md).

Each prompt is captured at the LLM boundary — the `messages` handed to
`litellm.completion` (generation, judge_chunk), the prompt text handed to
the judge LLM by RAGAS (faithfulness) — not by calling a template helper
directly, so the snapshot is exactly what the model receives. The capture
code goes only through public entry points (`generate_from_chunks`,
`judge_chunk`, `check_faithfulness`) and mocks the LLM: no Qdrant, no
network, fast.

The snapshots in `tests/fixtures/prompt_snapshots/<case>/` were rendered by
the pre-refactor implementation (prompts as Python string constants) and
committed before any prompt moved to `prompts/`: the refactor's acceptance
criterion is that the file-based prompts render them byte-for-byte.

Cases (`cases.json`): gold items Q001, Q002, Q007, Q009
(eval/gold_dataset.csv), real chunk text from `data/processed/chunks/`,
real generated answers from `eval/results/ragas_checkpoint.jsonl`
(generation_only mode). Evidence signals and chunk judgments are set by
hand so that, together, the cases cover every conditional branch of the
generation template:

- Q001: mono-work, single chunk, convergent, confident, no judgments
- Q002: multi-work, convergent, confident, no judgments
- Q007: multi-work, divergent, confident, two prior chunk judgments
- Q009: mono-work, divergent, low confidence (best rerank 0.24, the real
  Q009 retrieval-miss level), one prior chunk judgment

Snapshots change only when a prompt's wording changes — in its own branch
(docs/prompts.md). There, regenerate them with
`uv run python -m tests.test_prompt_snapshots` and review the diff.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest import mock

import litellm
import pytest
from langchain_core.outputs import Generation, LLMResult
from ragas.run_config import RunConfig

from src.generation.chunk_judge import judge_chunk
from src.generation.faithfulness import _text_for_judge, check_faithfulness
from src.generation.generate import generate_from_chunks
from src.generation.segmentation import segment_answer
from src.generation.signals import EvidenceSignals
from src.retrieval.reranking import RerankedChunk

SNAPSHOT_DIR = Path(__file__).parent / "fixtures" / "prompt_snapshots"
CASES: dict[str, dict[str, Any]] = json.loads(
    (SNAPSHOT_DIR / "cases.json").read_text(encoding="utf-8")
)

_INVALID_JUDGE_REPLY = "pas du JSON"
_VALID_JUDGE_REPLY = '{"label": "pertinent", "justification": "Justification de test."}'


def _model_response(content: str) -> litellm.ModelResponse:
    return litellm.ModelResponse(choices=[{"message": {"role": "assistant", "content": content}}])


def _chunks(case: dict[str, Any]) -> list[RerankedChunk]:
    return [RerankedChunk(**chunk) for chunk in case["chunks"]]


def _signals(case: dict[str, Any]) -> EvidenceSignals:
    signals = case["signals"]
    return EvidenceSignals(
        works=tuple(signals["works"]),
        convergence=signals["convergence"],
        is_convergent=signals["is_convergent"],
        is_confident=signals["is_confident"],
    )


def _capture_generation(case: dict[str, Any]) -> dict[str, str]:
    client = mock.Mock()
    client.retrieve.return_value = []
    completion = mock.Mock(return_value=_model_response("réponse"))
    with (
        mock.patch("src.generation.generate.compute_signals", return_value=_signals(case)),
        mock.patch("litellm.completion", completion),
    ):
        generate_from_chunks(
            case["query"], _chunks(case), client, chunk_judgments=case["chunk_judgments"]
        )
    messages = completion.call_args.kwargs["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    return {"generation.system": messages[0]["content"], "generation.user": messages[1]["content"]}


def _capture_judge_chunk(case: dict[str, Any]) -> dict[str, str]:
    """First reply unparseable, so the retry instruction is captured too."""
    completion = mock.Mock(
        side_effect=[_model_response(_INVALID_JUDGE_REPLY), _model_response(_VALID_JUDGE_REPLY)]
    )
    with mock.patch("litellm.completion", completion):
        judge_chunk(case["query"], _chunks(case)[0])
    messages = completion.call_args.kwargs["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[2]["content"] == _INVALID_JUDGE_REPLY
    return {
        "judge_chunk.system": messages[0]["content"],
        "judge_chunk.user": messages[1]["content"],
        "judge_chunk.retry": messages[3]["content"],
    }


class _RecordingJudgeLLM:
    """Stands in for `LangchainLLMWrapper`: records each prompt RAGAS sends
    and answers with valid JSON. The claim-extraction reply yields a single
    claim (from segment 0), so exactly one NLI prompt is sent per case."""

    def __init__(self, claim: str) -> None:
        self.run_config = RunConfig()
        self.prompts: list[str] = []
        self._claim = claim

    async def generate(self, prompt: Any, n: int = 1, **_: Any) -> LLMResult:
        self.prompts.append(prompt.to_string())
        if len(self.prompts) == 1:
            reply = {"segments": [{"segment_id": 0, "claims": [self._claim]}]}
        else:
            reply = {"statements": [{"statement": self._claim, "reason": "r", "verdict": 1}]}
        return LLMResult(generations=[[Generation(text=json.dumps(reply, ensure_ascii=False))]])


def _capture_faithfulness(case: dict[str, Any]) -> dict[str, str]:
    claim = _text_for_judge(segment_answer(case["answer"])[0])
    llm = _RecordingJudgeLLM(claim)
    check_faithfulness(case["query"], case["answer"], _chunks(case), judge_llm=llm)  # type: ignore[arg-type]
    assert len(llm.prompts) == 2
    return {
        "faithfulness.segment_claims": llm.prompts[0],
        "faithfulness.nli_verifier": llm.prompts[1],
    }


def render_case(case: dict[str, Any]) -> dict[str, str]:
    return {
        **_capture_generation(case),
        **_capture_judge_chunk(case),
        **_capture_faithfulness(case),
    }


def _snapshot_path(case_id: str, name: str) -> Path:
    return SNAPSHOT_DIR / case_id / f"{name}.txt"


def _read_snapshot(path: Path) -> str:
    # newline="": no newline translation, the bytes on disk are compared as-is.
    with path.open(encoding="utf-8", newline="") as f:
        return f.read()


@pytest.mark.parametrize("case_id", sorted(CASES))
def test_prompts_render_identically_to_snapshot(case_id: str) -> None:
    rendered = render_case(CASES[case_id])
    snapshot_files = sorted(p.stem for p in (SNAPSHOT_DIR / case_id).glob("*.txt"))
    assert sorted(rendered) == snapshot_files
    for name, text in rendered.items():
        assert text == _read_snapshot(_snapshot_path(case_id, name)), f"{case_id}/{name}"


def write_snapshots() -> None:
    for case_id, case in sorted(CASES.items()):
        (SNAPSHOT_DIR / case_id).mkdir(exist_ok=True)
        for name, text in render_case(case).items():
            with _snapshot_path(case_id, name).open("w", encoding="utf-8", newline="") as f:
                f.write(text)
            print(f"wrote {_snapshot_path(case_id, name)}")


if __name__ == "__main__":
    write_snapshots()
