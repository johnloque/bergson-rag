"""Repair of the faithfulness judge's raw replies (src/generation/judge_output.py)
and its wiring into the judge LLM (`build_judge_llm`). The malformed replies
below are the local judge's own, from
eval/results/raw_judge_replies_default_20261009.json (shortened)."""

from __future__ import annotations

import json
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from ragas.prompt.pydantic_prompt import fix_output_format_prompt

from src.generation.faithfulness import _RepairingJudgeLLM, check_faithfulness
from src.generation.judge_output import repair_json_reply, wrap_fix_reply

# Q001-p1: two claims of one segment, no comma between them.
MISSING_CLAIM_COMMA = """ {
  "segments": [
    {
      "segment_id": 0,
      "claims": [
        "Henri Bergson déclare avoir emprunté cette idée à Aristote."
        "Il cite longuement la Métaphysique d'Aristote."
      ]
    }
  ]
}"""

# Q002-gen, variant prompt: no comma after the "statement" field.
MISSING_FIELD_COMMA = """ {
    "statements": [
        {
            "statement": "L'œuvre de Henri Bergson s'intitule \\"De l'évolution de la vie.\\""
            "reason": "Le contexte cite \\"De l'évolution créatrice\\".",
            "verdict": 0
        }
    ]
}"""

# Q002-gen, default prompt: a quoted title closed by `\'`.
ESCAPED_APOSTROPHE = """ {
    "statements": [
        {
            "statement": "L'œuvre de Henri Bergson s'intitule \\"De l'évolution de la vie.\\'",
            "reason": "Le contexte cite \\"De l'évolution créatrice\\".",
            "verdict": 1
        }
    ]
}"""


def test_repairs_a_missing_comma_between_claims():
    claims = json.loads(repair_json_reply(MISSING_CLAIM_COMMA))["segments"][0]["claims"]
    assert claims == [
        "Henri Bergson déclare avoir emprunté cette idée à Aristote.",
        "Il cite longuement la Métaphysique d'Aristote.",
    ]


def test_repairs_a_missing_comma_between_fields():
    answer = json.loads(repair_json_reply(MISSING_FIELD_COMMA))["statements"][0]
    assert answer["statement"].endswith('"De l\'évolution de la vie."')
    assert answer["verdict"] == 0


def test_repairs_an_escaped_apostrophe():
    answer = json.loads(repair_json_reply(ESCAPED_APOSTROPHE))["statements"][0]
    assert answer["statement"].endswith("\"De l'évolution de la vie.'")


def test_valid_or_unrepairable_replies_are_untouched():
    valid = ' {"claims": ["a",\n "b"], "x": "l\\\\\'"}'  # `\\'` is a valid escape run
    assert repair_json_reply(valid) == valid
    prose = "Je ne peux pas répondre en JSON."
    assert repair_json_reply(prose) == prose
    broken = '{"a": "b" "c": }'
    assert repair_json_reply(broken) == broken


def test_wrap_fix_reply_restores_the_envelope_ragas_expects():
    wrapped = json.loads(wrap_fix_reply(' {"statements": []}'))
    assert wrapped == {"text": '{"statements": []}'}
    already = '{"text": "{}"}'
    assert wrap_fix_reply(already) == already
    assert wrap_fix_reply("pas du JSON") == "pas du JSON"


class _ScriptedChat(BaseChatModel):
    """Answers each prompt with `reply(prompt_text)`."""

    reply: Callable[[str], str]

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages: list[BaseMessage], *_: Any, **__: Any) -> ChatResult:
        text = self.reply(str(messages[-1].content))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])


def _is_fix(prompt: str) -> bool:
    return prompt.startswith(fix_output_format_prompt.instruction)


def _judge(segment_reply: str, nli_reply: str, fix_reply: str) -> Any:
    def reply(prompt: str) -> str:
        if _is_fix(prompt):
            return fix_reply
        return nli_reply if '"statements"' in prompt.rsplit("input:", 1)[-1] else segment_reply

    return _RepairingJudgeLLM(_ScriptedChat(reply=reply))


def _check(llm: Any) -> Any:
    answer = "Bergson déclare avoir emprunté cette idée à Aristote, dont il cite la Métaphysique."
    chunks = [SimpleNamespace(text="Un passage sans Aristote.")]
    return check_faithfulness("Q ?", answer, chunks, judge_llm=llm)  # type: ignore[arg-type]


def test_check_faithfulness_judges_replies_it_used_to_drop():
    """The baseline's failures: claims extraction (missing comma) and NLI
    (escaped apostrophe) now parse, so every claim gets a verdict."""
    llm = _judge(MISSING_CLAIM_COMMA, ESCAPED_APOSTROPHE, fix_reply="inutilisé")
    result = _check(llm)
    assert [c.supported for c in result.claims] == [True, True]


def test_bare_fix_reply_rescues_an_unrepairable_nli_reply():
    fixed = json.dumps({"statements": [{"statement": "s", "reason": "r", "verdict": 0}]})
    llm = _judge(MISSING_CLAIM_COMMA, "Verdict : 0, faute de contexte.", fix_reply=fixed)
    assert [c.supported for c in _check(llm).claims] == [False, False]


def test_fix_reply_still_unparseable_leaves_the_claim_unevaluated():
    """RAGAS raises langchain's OutputParserException (not its own) when the
    retry's wrapped text doesn't parse: the claim is not evaluated, the
    check doesn't fail."""
    llm = _judge(MISSING_CLAIM_COMMA, "Verdict : 0.", fix_reply='{"text": "toujours pas"}')
    result = _check(llm)
    assert [c.supported for c in result.claims] == [None, None]
