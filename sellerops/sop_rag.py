"""TF-IDF retrieval over the four marketplace SOP documents.

Citations are ``<file> §<section>``. When nothing scores above the
threshold, return an explicit not-found — never fabricate an answer.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

THRESHOLD = 0.08


@dataclass
class Chunk:
    doc: str
    section: str
    text: str


@dataclass
class Hit:
    chunk: Chunk
    score: float

    def citation(self) -> str:
        return f"{self.chunk.doc} §{self.chunk.section}"


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z]{3,}", text.lower())


def load_chunks(sop_dir: str | Path) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path in sorted(Path(sop_dir).glob("*.md")):
        section, buf = None, []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.startswith("## "):
                if section and any(b.strip() for b in buf):
                    chunks.append(Chunk(path.name, section, "\n".join(buf)))
                section, buf = line[3:].strip(), []
            elif line.startswith("# "):
                continue  # skip the H1 title — title-only chunks cause false positives
            else:
                buf.append(line)
        if section and any(b.strip() for b in buf):
            chunks.append(Chunk(path.name, section, "\n".join(buf)))
    return chunks


class SopIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        df: dict[str, int] = {}
        self._tf: list[dict[str, int]] = []
        for c in chunks:
            counts: dict[str, int] = {}
            for t in _tokens(c.text):
                counts[t] = counts.get(t, 0) + 1
            self._tf.append(counts)
            for t in counts:
                df[t] = df.get(t, 0) + 1
        n = max(len(chunks), 1)
        self._idf = {t: math.log(n / d) for t, d in df.items()}

    def _vec(self, counts: dict[str, int]) -> dict[str, float]:
        return {t: c * self._idf.get(t, 0.0) for t, c in counts.items()}

    def search(self, query: str, k: int = 3) -> list[Hit]:
        qv = self._vec({t: query.lower().count(t) for t in set(_tokens(query))})
        qn = math.sqrt(sum(v * v for v in qv.values()))
        hits: list[Hit] = []
        for chunk, tf in zip(self.chunks, self._tf):
            dv = self._vec(tf)
            dot = sum(qv.get(t, 0.0) * v for t, v in dv.items())
            dn = math.sqrt(sum(v * v for v in dv.values()))
            score = dot / (qn * dn) if qn and dn else 0.0
            if score >= THRESHOLD:
                hits.append(Hit(chunk, round(score, 4)))
        return sorted(hits, key=lambda h: -h.score)[:k]


def answer(index: SopIndex, query: str) -> dict:
    hits = index.search(query)
    if not hits:
        return {"found": False, "answer": None, "citations": [],
                "note": "no SOP section matched; escalate to policy team"}
    best = hits[0]
    return {"found": True,
            "answer": best.chunk.text.strip()[:600],
            "citations": [h.citation() for h in hits]}
