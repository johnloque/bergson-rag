#!/usr/bin/env python3
"""Builds `eval/calibration_set.json`, the fixed answers the faithfulness
judge variants are scored on (judge mode of
`eval/scripts/run_prompt_comparison.py`; docs/prompts.md, "Calibration
set").

Every item carries an `origin` and a `label`:

- `gold` / faithful: each `eval/gold_dataset.csv` `expected_anwser`, scored
  against all the chunks of its `paragraph_ids` (resolved through
  `src.paragraph_chunk_map`; a multi item gets every listed chunk).
- `generated` / hallucinated: real answers from the RAGAS eval checkpoint
  (`eval/results/ragas_checkpoint.jsonl`), copied verbatim, each with the
  substring of its known fabricated claim. Labels and substrings come only
  from the owner, in `eval/calibration_labels.yaml`; nothing here guesses
  one. A labeled answer missing from the checkpoint stops the build with a
  "supply this" report: an answer is never reconstructed or regenerated.
  Checkpoint answers not labeled yet are listed. These are judged against
  the item's gold chunks: the checkpoint doesn't keep the chunks an
  end_to_end answer was generated from.
- `perturbed` / hallucinated: mechanical edits of gold answers (fixed seed,
  every edit stored as data): (a) swap a proper noun (a philosopher, a
  work title), (b) change a year, (c) insert one unsupported sentence from
  a fixed list, (d) negate a claim. (a) and (b) only target a name or year
  the chunks themselves contain: the judge never sees a work's title or
  date, so swapping one the chunks don't mention falsifies nothing. One
  per gold item by default, the type rotated deterministically. An edit
  whose replacement or inserted text appears in the item's chunks is
  discarded and logged. A perturbed item
  keeps its source item's chunks (paired design).

Perturbed items are cruder than real fabrications: the judge catching them
shows it catches blatant errors, not subtle ones. They are always reported
apart from generated ones.

Usage: python -m eval.scripts.calibration_set [--perturbations-per-item 1]
Needs `data/processed/chunks/` (ingestion) and, for generated items, the
local checkpoint file.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
import sys
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml

from eval.scripts.checkpoint import load_checkpoint
from src.paragraph_chunk_map import DEFAULT_CHUNKS_DIR, parse_paragraph_id, resolve_chunk_ids
from src.prompts.loader import load_prompt

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GOLD_DATASET_PATH = REPO_ROOT / "eval" / "gold_dataset.csv"
CALIBRATION_SET_PATH = REPO_ROOT / "eval" / "calibration_set.json"
LABELS_PATH = REPO_ROOT / "eval" / "calibration_labels.yaml"
CHECKPOINT_PATH = REPO_ROOT / "eval" / "results" / "ragas_checkpoint.jsonl"

DEFAULT_SEED = 1859  # fixed: the perturbations must be reproducible
DEFAULT_PERTURBATIONS_PER_ITEM = 1
PERTURBATION_TYPES = ("proper_noun", "year", "unsupported_sentence", "negation")

# (a) Swappable proper nouns. "Bergson" is deliberately absent: chunks never
# name their own author, so swapping him out makes no claim checkably false
# against them.
PHILOSOPHERS = (
    "Aristote", "Berkeley", "Descartes", "Fechner", "Hume", "Kant", "Leibniz", "Locke",
    "Plotin", "Platon", "Spencer", "Spinoza", "William James", "Zénon",
)  # fmt: skip
# Title forms as the gold answers write them; replacements start with a
# consonant so a dropped "l'" never needs re-eliding.
TITLE_FORMS = (
    "Essai sur les données immédiates de la conscience", "Matière et mémoire", "Le Rire",
    "Évolution créatrice", "Énergie spirituelle", "Les Deux Sources",
    "La Pensée et le Mouvant", "Durée et simultanéité",
)  # fmt: skip
TITLE_REPLACEMENTS = (
    "Matière et mémoire", "Le Rire", "Les Deux Sources", "La Pensée et le Mouvant",
    "Durée et simultanéité",
)  # fmt: skip
YEAR_OFFSETS = (-11, -7, -5, -3, 3, 5, 7, 11)
# (c) Fixed, deliberately unsupported sentences.
UNSUPPORTED_SENTENCES = (  # fmt: skip
    "Bergson déclare avoir emprunté cette idée à Aristote, dont il cite longuement la Métaphysique.",  # noqa: E501
    "Il ajoute que cette thèse fut confirmée expérimentalement par des psychologues allemands en 1895.",  # noqa: E501
    "Bergson précise qu'il abandonnera entièrement cette position dans ses derniers écrits.",
    "Il affirme que cette conception lui valut le soutien unanime des physiciens de son époque.",
    "Il illustre ensuite ce point par l'exemple d'une horloge arrêtée dans une maison vide.",
)  # fmt: skip
# (d) Negations: (verb pattern, negated form). The edit window around the
# verb (a few words each side) is the fabricated substring, so "n'est pas"
# alone, frequent in the corpus, doesn't discard every negation.
NEGATIONS = (("est", "n'est pas"), ("sont", "ne sont pas"), ("peut", "ne peut pas"))
NEGATION_WINDOW_WORDS = 3


class MissingText(Exception):
    """A labeled answer isn't where it should be; the owner must supply it."""


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize(text: str) -> str:
    """For substring checks: NFC, casefolded, typographic apostrophes and
    whitespace unified."""
    text = unicodedata.normalize("NFC", text).casefold().replace("’", "'")
    return re.sub(r"\s+", " ", text)


def appears_in(fragment: str, texts: Iterable[str]) -> bool:
    needle = normalize(fragment).strip()
    return any(needle in normalize(text) for text in texts)


# --- gold items -----------------------------------------------------------


@dataclass(frozen=True)
class GoldRow:
    id: str
    category: str
    query: str
    paragraph_ids: tuple[str, ...]
    expected_answer: str


def read_gold_rows(path: Path = GOLD_DATASET_PATH) -> list[GoldRow]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return [
            GoldRow(
                id=row["id"],
                category=row["category"],
                query=row["query"],
                paragraph_ids=tuple(
                    p.strip() for p in row["paragraph_ids"].split(",") if p.strip()
                ),
                expected_answer=row["expected_anwser"],
            )
            for row in csv.DictReader(f, delimiter=";")
        ]


def gold_chunk_ids(row: GoldRow, chunks_dir: Path) -> list[str]:
    """Every chunk holding one of the row's paragraphs, in paragraph order."""
    chunk_ids: list[str] = []
    for paragraph_id in row.paragraph_ids:
        work_id, _ = parse_paragraph_id(paragraph_id)
        for chunk_id in resolve_chunk_ids(work_id, paragraph_id, chunks_dir):
            if chunk_id not in chunk_ids:
                chunk_ids.append(chunk_id)
    if not chunk_ids:
        raise ValueError(f"gold item {row.id}: no chunk holds {row.paragraph_ids}")
    return chunk_ids


def load_chunk_texts(chunks_dir: Path = DEFAULT_CHUNKS_DIR) -> dict[str, str]:
    texts: dict[str, str] = {}
    for path in sorted(chunks_dir.glob("*.json")):
        for chunk in json.loads(path.read_text(encoding="utf-8")):
            texts[chunk["chunk_id"]] = chunk["text"]
    return texts


# --- perturbations --------------------------------------------------------


@dataclass(frozen=True)
class Edit:
    type: str
    original_span: str  # text replaced ("" for an insertion)
    replacement: str  # text put in its place (the inserted sentence for (c))
    start: int  # position of the edit in the source answer
    fabricated_substring: str  # what the judge must flag, as it reads in `answer`
    fabricated_start: int  # where it starts in `answer`
    answer: str  # the perturbed answer


def _swap_proper_noun(answer: str, rng: random.Random, chunk_texts: Sequence[str]) -> Edit | None:
    candidates: list[tuple[int, int, str, tuple[str, ...]]] = []
    for name in PHILOSOPHERS:
        if not appears_in(name, chunk_texts):
            continue
        for match in re.finditer(rf"(?<!\w){re.escape(name)}(?!\w)", answer):
            others = tuple(n for n in PHILOSOPHERS if n != name)
            candidates.append((match.start(), match.end(), name, others))
    for title in TITLE_FORMS:
        if not appears_in(title, chunk_texts):
            continue
        for match in re.finditer(re.escape(title), answer, flags=re.IGNORECASE):
            start = match.start()
            if answer[max(0, start - 2) : start].lower() in ("l'", "l’"):
                start -= 2  # "l'Évolution créatrice" -> "Matière et mémoire"
            others = tuple(t for t in TITLE_REPLACEMENTS if normalize(t) != normalize(title))
            candidates.append((start, match.end(), title, others))
    if not candidates:
        return None
    start, end, _, others = rng.choice(sorted(candidates))
    replacement = rng.choice(others)
    return Edit(
        type="proper_noun",
        original_span=answer[start:end],
        replacement=replacement,
        start=start,
        fabricated_substring=replacement,
        fabricated_start=start,
        answer=answer[:start] + replacement + answer[end:],
    )


def _change_year(answer: str, rng: random.Random, chunk_texts: Sequence[str]) -> Edit | None:
    matches = [
        m
        for m in re.finditer(r"(?<!\d)1[5-9]\d\d(?!\d)", answer)
        if appears_in(m.group(), chunk_texts)
    ]
    if not matches:
        return None
    match = rng.choice(matches)
    replacement = str(int(match.group()) + rng.choice(YEAR_OFFSETS))
    return Edit(
        type="year",
        original_span=match.group(),
        replacement=replacement,
        start=match.start(),
        fabricated_substring=replacement,
        fabricated_start=match.start(),
        answer=answer[: match.start()] + replacement + answer[match.end() :],
    )


def _insert_sentence(answer: str, rng: random.Random, _: Sequence[str]) -> Edit | None:
    # After a sentence end followed by a space; at the very end otherwise.
    boundaries = [m.end() for m in re.finditer(r"[.!?»](?=\s)", answer)] or [len(answer.rstrip())]
    position = rng.choice(boundaries)
    sentence = rng.choice(UNSUPPORTED_SENTENCES)
    return Edit(
        type="unsupported_sentence",
        original_span="",
        replacement=sentence,
        start=position,
        fabricated_substring=sentence,
        fabricated_start=position + 1,
        answer=answer[:position] + " " + sentence + answer[position:],
    )


def _negate(answer: str, rng: random.Random, _: Sequence[str]) -> Edit | None:
    candidates: list[tuple[re.Match[str], str]] = []
    for verb, negated in NEGATIONS:
        for match in re.finditer(rf"(?<![\w'’]){verb}(?!\w)", answer):
            before = answer[max(0, match.start() - 3) : match.start()].lower()
            after = answer[match.end() : match.end() + 4].lower()
            if before.endswith("ne ") or after == " pas":
                continue  # already negated
            candidates.append((match, negated))
    # "c'est" -> "ce n'est pas"
    for match in re.finditer(r"(?<!\w)([Cc])['’]est(?!\w)", answer):
        candidates.append((match, f"{match.group(1)}e n'est pas"))
    if not candidates:
        return None
    match, negated = rng.choice(sorted(candidates, key=lambda c: c[0].start()))
    words = list(re.finditer(r"\S+", answer))
    index = next(i for i, w in enumerate(words) if w.end() > match.start())
    first = words[max(0, index - NEGATION_WINDOW_WORDS)].start()
    last = words[min(len(words) - 1, index + NEGATION_WINDOW_WORDS)].end()
    window = answer[first:last]
    edited = window[: match.start() - first] + negated + window[match.end() - first :]
    return Edit(
        type="negation",
        original_span=window,
        replacement=edited,
        start=first,
        fabricated_substring=edited,
        fabricated_start=first,
        answer=answer[:first] + edited + answer[last:],
    )


_PERTURBERS = {
    "proper_noun": _swap_proper_noun,
    "year": _change_year,
    "unsupported_sentence": _insert_sentence,
    "negation": _negate,
}


def perturb(answer: str, kind: str, rng: random.Random, chunk_texts: Sequence[str]) -> Edit | None:
    """One `kind` edit of `answer`, or None if `answer` offers no target.

    A proper noun or a year is only swapped where it also appears in
    `chunk_texts`: the judge sees chunk text only, never a work's title or
    date, so changing one the chunks don't mention would make nothing
    checkably false (the original was just as unsupported)."""
    return _PERTURBERS[kind](answer, rng, chunk_texts)


def perturb_item(
    item_id: str,
    item_index: int,
    answer: str,
    chunk_texts: Sequence[str],
    seed: int,
    per_item: int,
    log: list[dict[str, Any]],
) -> list[Edit]:
    """Up to `per_item` edits of different types. Perturbation `j` of item
    `item_index` starts at type `(item_index * per_item + j) % 4` and moves
    to the next type when that one has no target in the answer, or when its
    replacement appears in the chunks (discarded). Every skip and discard is
    appended to `log`. Seeded per (item, perturbation), so adding items
    doesn't change existing ones."""
    edits: list[Edit] = []
    used: set[str] = set()
    for j in range(per_item):
        start = (item_index * per_item + j) % len(PERTURBATION_TYPES)
        for step in range(len(PERTURBATION_TYPES)):
            kind = PERTURBATION_TYPES[(start + step) % len(PERTURBATION_TYPES)]
            if kind in used:
                continue
            rng = random.Random(f"{seed}:{item_id}:{j}:{kind}")
            edit = perturb(answer, kind, rng, chunk_texts)
            if edit is None:
                log.append({"item": item_id, "type": kind, "status": "not applicable"})
                continue
            used.add(kind)
            if appears_in(edit.replacement, chunk_texts):
                log.append(
                    {
                        "item": item_id,
                        "type": kind,
                        "status": "discarded",
                        "reason": f"replacement {edit.replacement!r} appears in the item's chunks",
                    }
                )
                continue
            edits.append(edit)
            break
        else:
            log.append({"item": item_id, "perturbation": j + 1, "status": "no usable edit"})
    return edits


# --- generated items ------------------------------------------------------


def read_labels(path: Path = LABELS_PATH) -> list[dict[str, str]]:
    """Owner-supplied labels for checkpoint answers: `checkpoint_key`,
    `label` (hallucinated), `fabricated_substring`, `note`."""
    if not path.is_file():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("generated") or []
    required = {"checkpoint_key", "label", "fabricated_substring", "note"}
    for number, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict) or set(entry) != required:
            raise ValueError(f"{path.name}, entry {number}: expected exactly {sorted(required)}")
        if entry["label"] != "hallucinated":
            raise ValueError(f"{path.name}, entry {number}: label must be 'hallucinated'")
        if not str(entry["fabricated_substring"]).strip():
            raise ValueError(f"{path.name}, entry {number}: empty fabricated_substring")
    return entries


def unlabeled_checkpoint_keys(checkpoint: Mapping[str, dict], labels: Sequence[dict]) -> list[str]:
    labeled = {entry["checkpoint_key"] for entry in labels}
    return sorted(key for key in checkpoint if not key.startswith("rerun:") and key not in labeled)


# --- assembly -------------------------------------------------------------


def _chunk_refs(chunk_ids: Sequence[str], chunk_texts: Mapping[str, str]) -> list[dict[str, str]]:
    return [{"chunk_id": cid, "sha256": text_hash(chunk_texts[cid])} for cid in chunk_ids]


def build_calibration_set(
    gold_rows: Sequence[GoldRow],
    gold_chunks: Mapping[str, Sequence[str]],
    chunk_texts: Mapping[str, str],
    labels: Sequence[dict[str, str]],
    checkpoint: Mapping[str, dict],
    seed: int = DEFAULT_SEED,
    per_item: int = DEFAULT_PERTURBATIONS_PER_ITEM,
) -> dict[str, Any]:
    """The calibration set as JSON-ready data. Raises `MissingText` naming
    every labeled answer that isn't in `checkpoint` (nothing is built)."""
    missing = [e["checkpoint_key"] for e in labels if e["checkpoint_key"] not in checkpoint]
    if missing:
        raise MissingText(", ".join(missing))

    by_id = {row.id: row for row in gold_rows}
    items: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []

    def base(row: GoldRow, item_id: str, origin: str, label: str, answer: str) -> dict[str, Any]:
        return {
            "id": item_id,
            "origin": origin,
            "label": label,
            "source_item": row.id,
            "category": row.category,
            "query": row.query,
            "answer": answer,
            "paragraph_ids": list(row.paragraph_ids),
            "chunks": _chunk_refs(gold_chunks[row.id], chunk_texts),
            "fabricated_substring": None,
            "fabricated_start": None,
            "perturbation": None,
            "generated": None,
        }

    for row in gold_rows:
        items.append(base(row, row.id, "gold", "faithful", row.expected_answer))

    for entry in labels:
        row_data = checkpoint[entry["checkpoint_key"]]
        answer = row_data["answer"]
        substring = entry["fabricated_substring"]
        if substring not in answer:
            raise ValueError(
                f"{entry['checkpoint_key']}: fabricated_substring {substring!r} is not in the "
                "checkpoint answer (it must be copied verbatim)"
            )
        row = by_id[row_data["item_id"]]
        item = base(row, f"{row.id}-gen-{row_data['mode']}", "generated", "hallucinated", answer)
        item["fabricated_substring"] = substring
        item["fabricated_start"] = answer.index(substring)
        item["generated"] = {
            "checkpoint_key": entry["checkpoint_key"],
            "mode": row_data["mode"],
            "answer_sha256": text_hash(answer),
            "checkpoint_faithfulness": row_data.get("faithfulness"),
            "note": entry["note"],
            "chunks": "gold chunks of the item (the checkpoint doesn't keep the evidence it was "
            "generated from)",
        }
        items.append(item)

    for index, row in enumerate(gold_rows):
        texts = [chunk_texts[cid] for cid in gold_chunks[row.id]]
        edits = perturb_item(row.id, index, row.expected_answer, texts, seed, per_item, log)
        for number, edit in enumerate(edits, start=1):
            item = base(
                row, f"{row.id}-p{number}-{edit.type}", "perturbed", "hallucinated", edit.answer
            )
            item["fabricated_substring"] = edit.fabricated_substring
            item["fabricated_start"] = edit.fabricated_start
            item["perturbation"] = {"source_item": row.id, **asdict(edit)}
            for key in ("answer", "fabricated_substring", "fabricated_start"):
                del item["perturbation"][key]
            items.append(item)

    return {
        "description": (
            "Faithfulness-judge calibration set (eval/scripts/calibration_set.py, "
            "docs/prompts.md). Generated by script; edit eval/calibration_labels.yaml, not this."
        ),
        "seed": seed,
        "perturbations_per_item": per_item,
        "items": items,
        "perturbation_log": log,
        "unlabeled_checkpoint_items": unlabeled_checkpoint_keys(checkpoint, labels),
    }


def calibration_set_hash(calibration: Mapping[str, Any]) -> str:
    """Identifies the items (ids, texts, chunks): two runs on the same set
    have the same hash."""
    return text_hash(json.dumps(calibration["items"], ensure_ascii=False, sort_keys=True))


def load_calibration_set(path: Path = CALIBRATION_SET_PATH) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found: build it with `python -m eval.scripts.calibration_set`"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_chunk_texts(item: Mapping[str, Any], chunk_texts: Mapping[str, str]) -> list[str]:
    """The item's chunk texts, checked against the hashes stored at build
    time: re-chunking changes chunk ids and boundaries, and the set must
    then be rebuilt, not silently scored against other text."""
    texts = []
    for ref in item["chunks"]:
        text = chunk_texts.get(ref["chunk_id"])
        if text is None or text_hash(text) != ref["sha256"]:
            raise ValueError(
                f"calibration item {item['id']}: chunk {ref['chunk_id']} is missing or changed "
                "since the set was built (re-chunked?): rebuild eval/calibration_set.json"
            )
        texts.append(text)
    return texts


# --- held-out check -------------------------------------------------------

HELD_OUT_SHINGLE_WORDS = 8


def _shingles(text: str, size: int = HELD_OUT_SHINGLE_WORDS) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", normalize(text))
    return {tuple(words[i : i + size]) for i in range(len(words) - size + 1)}


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def held_out_overlaps(
    calibration_texts: Mapping[str, str], examples_paths: Sequence[Path]
) -> list[dict[str, str]]:
    """Calibration texts (answers, chunks) sharing an 8-word run with a
    judge prompt's few-shot examples. Any hit means the judge may have seen
    the answer to a calibration item in its own prompt."""
    overlaps = []
    for path in examples_paths:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        example_shingles = set().union(*(_shingles(s) for s in _strings(data)))
        for name, text in calibration_texts.items():
            shared = _shingles(text) & example_shingles
            if shared:
                overlaps.append(
                    {
                        "examples_file": path.name,
                        "calibration_text": name,
                        "shared": " ".join(min(shared)),
                    }
                )
    return overlaps


def calibration_texts(
    calibration: Mapping[str, Any], chunk_texts: Mapping[str, str]
) -> dict[str, str]:
    texts: dict[str, str] = {}
    for item in calibration["items"]:
        texts[f"answer {item['id']}"] = item["answer"]
        for ref in item["chunks"]:
            if ref["chunk_id"] in chunk_texts:
                texts[f"chunk {ref['chunk_id']}"] = chunk_texts[ref["chunk_id"]]
    return texts


# --- CLI ------------------------------------------------------------------


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--perturbations-per-item",
        type=int,
        default=DEFAULT_PERTURBATIONS_PER_ITEM,
        help="Perturbed copies per gold item (default 1, max 4, one per type). Each one is a "
        "full local-judge run per --repeat in judge mode: cost grows linearly.",
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--labels", type=Path, default=LABELS_PATH)
    parser.add_argument("--checkpoint", type=Path, default=CHECKPOINT_PATH)
    parser.add_argument("--chunks-dir", type=Path, default=DEFAULT_CHUNKS_DIR)
    parser.add_argument("--gold", type=Path, default=GOLD_DATASET_PATH)
    parser.add_argument("--output", type=Path, default=CALIBRATION_SET_PATH)
    args = parser.parse_args(argv)
    if not 1 <= args.perturbations_per_item <= len(PERTURBATION_TYPES):
        parser.error(f"--perturbations-per-item must be 1..{len(PERTURBATION_TYPES)}")

    gold_rows = read_gold_rows(args.gold)
    chunk_texts = load_chunk_texts(args.chunks_dir)
    gold_chunks = {row.id: gold_chunk_ids(row, args.chunks_dir) for row in gold_rows}
    labels = read_labels(args.labels)
    checkpoint = load_checkpoint(args.checkpoint)
    try:
        calibration = build_calibration_set(
            gold_rows,
            gold_chunks,
            chunk_texts,
            labels,
            checkpoint,
            args.seed,
            args.perturbations_per_item,
        )
    except MissingText as missing:
        print(
            f"SUPPLY THIS: labeled answer(s) not found in {args.checkpoint}: {missing}.\n"
            "Generated answers are copied verbatim from the checkpoint, never reconstructed or "
            "regenerated: restore the checkpoint row(s), or remove the label(s). Nothing written.",
            file=sys.stderr,
        )
        return 1

    args.output.write_text(
        json.dumps(calibration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    counts: dict[str, int] = {}
    for item in calibration["items"]:
        counts[item["origin"]] = counts.get(item["origin"], 0) + 1
    print(f"Wrote {args.output}: {counts}")
    for entry in calibration["perturbation_log"]:
        print(f"  perturbation log: {entry}")
    if calibration["unlabeled_checkpoint_items"]:
        unlabeled = ", ".join(calibration["unlabeled_checkpoint_items"])
        print(
            "Checkpoint answers not labeled yet (add to eval/calibration_labels.yaml with an "
            f"owner-supplied substring if fabricated): {unlabeled}"
        )
    examples = [
        path
        for prompt_id in ("faithfulness.segment_claims", "faithfulness.nli_verifier")
        for path in load_prompt(prompt_id).examples_paths
    ]
    overlaps = held_out_overlaps(calibration_texts(calibration, chunk_texts), examples)
    print(f"Held-out check against the committed judge examples: {overlaps or 'no overlap'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
