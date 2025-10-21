from __future__ import annotations

from collections import Counter
from typing import Dict, List


def compute_metrics(reference: str, hypothesis: str) -> Dict[str, object]:
    ref_tokens = tokenize(reference)
    hyp_tokens = tokenize(hypothesis)

    word_error_rate = levenshtein_distance(ref_tokens, hyp_tokens) / max(len(ref_tokens), 1)
    character_error_rate = levenshtein_distance(list(reference), list(hypothesis)) / max(len(reference), 1)

    ref_counter = Counter(ref_tokens)
    hyp_counter = Counter(hyp_tokens)

    missing: List[str] = []
    matched: List[str] = []
    for token, count in ref_counter.items():
        hyp_count = hyp_counter.get(token, 0)
        matched.extend([token] * min(count, hyp_count))
        if count > hyp_count:
            missing.extend([token] * (count - hyp_count))

    extra: List[str] = []
    for token, count in hyp_counter.items():
        ref_count = ref_counter.get(token, 0)
        if count > ref_count:
            extra.extend([token] * (count - ref_count))

    return {
        "word_error_rate": float(word_error_rate),
        "character_error_rate": float(character_error_rate),
        "missing": missing,
        "extra": extra,
        "matched": matched,
    }


def tokenize(text: str) -> List[str]:
    return [token for token in text.lower().split() if token]


def levenshtein_distance(source: List[str], target: List[str]) -> int:
    if not source:
        return len(target)
    if not target:
        return len(source)

    previous_row = list(range(len(target) + 1))
    for i, source_token in enumerate(source, start=1):
        current_row = [i]
        for j, target_token in enumerate(target, start=1):
            substitution_cost = 0 if source_token == target_token else 1
            insertions = current_row[j - 1] + 1
            deletions = previous_row[j] + 1
            substitutions = previous_row[j - 1] + substitution_cost
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    return previous_row[-1]


__all__ = ["compute_metrics", "tokenize", "levenshtein_distance"]
