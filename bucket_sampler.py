"""
bucket_sampler.py

Loads the JSON bucket files (languages/*.json, roles/*.json, behavioral.json)
and does weighted-random sampling without replacement — the "social media
algorithm" pattern: high sampling_weight = picked more often, low weight =
picked less often, but NEVER zero probability.

This module owns ALL topic selection. Gemini never sees the full bucket
file — only the handful of topic names this function hands back. That's
what keeps token cost low and keeps coverage auditable (you can log exactly
which topics/questions got picked for any session).

Usage from gemini.py:
    from bucket_sampler import BucketSampler

    sampler = BucketSampler()  # loads all JSON files once at startup

    # For known language/role combos (dropdown path):
    fundamentals = sampler.sample_fundamentals("python", k=2)
    extended     = sampler.sample_extended("backend", k=2)
    design       = sampler.sample_system_design("backend", difficulty="Intermediate", k=1)
    behavioral   = sampler.sample_behavioral(k=1)

    # For "Other" (free-text) — no bucket exists, caller falls back to
    # letting Gemini generate topics live from its own knowledge, exactly
    # like the current system already does. sampler.has_language(name) /
    # sampler.has_role(name) tell the caller which path to take.
"""

import json
import random
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"


class BucketSampler:
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = data_dir
        self.languages = {}   # e.g. "python" -> loaded dict
        self.roles = {}       # e.g. "backend" -> loaded dict
        self.behavioral = None
        self._load_all()

    # ---------- loading ----------

    def _load_all(self):
        lang_dir = self.data_dir / "languages"
        if lang_dir.exists():
            for f in lang_dir.glob("*.json"):
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                key = data.get("language", f.stem).strip().lower()
                self.languages[key] = data

        role_dir = self.data_dir / "roles"
        if role_dir.exists():
            for f in role_dir.glob("*.json"):
                with open(f, encoding="utf-8") as fh:
                    data = json.load(fh)
                key = data.get("role_shape", f.stem).strip().lower()
                self.roles[key] = data

        behavioral_path = self.data_dir / "behavioral.json"
        if behavioral_path.exists():
            with open(behavioral_path, encoding="utf-8") as fh:
                self.behavioral = json.load(fh)

        print(
            f"📚 BucketSampler loaded: "
            f"{len(self.languages)} language(s) {list(self.languages)}, "
            f"{len(self.roles)} role(s) {list(self.roles)}, "
            f"behavioral={'yes' if self.behavioral else 'no'}"
        )

    # ---------- lookup helpers (used to decide dropdown vs "Other" path) ----------

    def has_language(self, language: str) -> bool:
        return (language or "").strip().lower() in self.languages

    def has_role(self, role: str) -> bool:
        return (role or "").strip().lower() in self.roles

    # ---------- core weighted sampling, no repeats within one call ----------

    @staticmethod
    def _weighted_sample_no_repeat(pool: list, k: int) -> list:
        """
        Weighted random sampling WITHOUT replacement.
        - Higher sampling_weight => picked more often across many sessions.
        - Every item has sampling_weight > 0 => never truly impossible.
        - No repeats WITHIN a single call (no duplicate topic in one interview).
        """
        if not pool:
            return []
        k = min(k, len(pool))
        remaining = pool.copy()
        selected = []
        for _ in range(k):
            weights = [item.get("sampling_weight", 1.0) for item in remaining]
            pick = random.choices(remaining, weights=weights, k=1)[0]
            selected.append(pick)
            remaining.remove(pick)
        return selected

    # ---------- Phase 2: Fundamentals (per language, topic-only) ----------

    def sample_fundamentals(self, language: str, k: int = 2) -> list[str]:
        lang_key = (language or "").strip().lower()
        data = self.languages.get(lang_key)
        if not data:
            return []
        picks = self._weighted_sample_no_repeat(data.get("fundamentals", []), k)
        return [p["topic"] for p in picks]

    # ---------- Phase 4: Extended Technical Topics (per role, topic-only) ----------

    def sample_extended(self, role: str, k: int = 2) -> list[str]:
        role_key = (role or "").strip().lower()
        data = self.roles.get(role_key)
        if not data:
            return []
        topics = data.get("extended_technical_topics", {}).get("topics", [])
        picks = self._weighted_sample_no_repeat(topics, k)
        return [p["topic"] for p in picks]

    # ---------- Phase 5: System Design (per role, filtered by difficulty, k=1) ----------

    def sample_system_design(self, role: str, difficulty: str = "Intermediate", k: int = 1) -> list[dict]:
        """
        Returns list of {"name": ..., "seed_prompt": ...} dicts (not just names —
        Gemini needs the seed_prompt text to know what scenario to open with).
        Filters to the candidate's chosen difficulty tier before weighting.
        """
        role_key = (role or "").strip().lower()
        data = self.roles.get(role_key)
        if not data:
            return []
        scenarios = data.get("system_design_scenarios", {}).get("scenarios", [])
        diff_key = (difficulty or "").strip().lower()
        tier = [s for s in scenarios if s.get("difficulty", "").lower() == diff_key]
        if not tier:
            # fall back to full pool if nothing matches the requested tier
            tier = scenarios
        picks = self._weighted_sample_no_repeat(tier, k)
        return [{"name": p["name"], "seed_prompt": p["seed_prompt"]} for p in picks]

    # ---------- Phase 6: Behavioral (question-text based, uniform random, role/language-agnostic) ----------

    def sample_behavioral(self, k: int = 1) -> list[str]:
        """
        Uniform random (no weighting — every category/question is equally
        valid, there's no real-world 'frequency' signal to encode here,
        as discussed). Picks k categories, one question per category,
        no repeat categories within a call.
        """
        if not self.behavioral:
            return []
        categories = self.behavioral.get("categories", [])
        if not categories:
            return []
        k = min(k, len(categories))
        chosen_categories = random.sample(categories, k)
        questions = []
        for cat in chosen_categories:
            pool = cat.get("questions", [])
            if pool:
                questions.append(random.choice(pool))
        return questions


if __name__ == "__main__":
    # Quick smoke test
    sampler = BucketSampler()
    print("\nFundamentals (python, k=2):", sampler.sample_fundamentals("python", k=2))
    print("Extended (backend, k=2):", sampler.sample_extended("backend", k=2))
    print("System design (backend, Beginner, k=1):", sampler.sample_system_design("backend", "Beginner", k=1))
    print("Behavioral (k=1):", sampler.sample_behavioral(k=1))
    print("\nhas_language('rust'):", sampler.has_language("rust"), "(expected False -> falls back to free-text/Other path)")
    print("has_language('python'):", sampler.has_language("python"), "(expected True)")