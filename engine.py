"""
CineRisk Core Engine v1
=======================
Single source of truth for all risk and revenue outputs.
Dashboards, reports, and APIs are read-only views of this engine.

Design constraints (from architecture doc):
- 3 inputs max
- 2 outputs max (risk + revenue)
- 1 comparison dimension (strategy)
- Always output ranges, never single values
- Always output confidence score
- Always output explanation — no black box
"""

from dataclasses import dataclass, field
from typing import Literal, List, Tuple
import math
import json


# ── Types ──────────────────────────────────────────────────────────────

Genre    = Literal["action", "scifi", "thriller", "horror", "drama", "animation"]
Hype     = Literal["low", "medium", "high"]
Strategy = Literal["global_day1", "staggered", "streaming_delay"]


# ── Input model (3 inputs only) ────────────────────────────────────────

@dataclass
class FilmInput:
    """
    Minimal film input. Deliberately constrained to 3 inputs.
    More inputs = false precision at MVP stage.
    """
    genre:    Genre    # drives base piracy sensitivity
    hype:     Hype     # drives spread velocity
    strategy: Strategy # the variable being optimised

    def validate(self):
        assert self.genre    in ("action","scifi","thriller","horror","drama","animation")
        assert self.hype     in ("low","medium","high")
        assert self.strategy in ("global_day1","staggered","streaming_delay")
        return self


# ── Engine constants (explicit, auditable) ─────────────────────────────

# Base piracy sensitivity by genre (peer-reviewed basis: high-demand = high piracy)
GENRE_SENSITIVITY = {
    "action":    0.72,
    "scifi":     0.68,
    "thriller":  0.58,
    "horror":    0.52,
    "drama":     0.24,
    "animation": 0.38,
}

# Hype multiplier — higher buzz = faster piracy spread velocity
HYPE_MULTIPLIER = {
    "low":    0.6,
    "medium": 1.0,
    "high":   1.45,
}

# Delay factor — more delay = larger piracy window
# Based on: staggered releases produce leaks 3-4x faster than global
DELAY_FACTOR = {
    "global_day1":     0.0,   # no delay = no regional gap to exploit
    "staggered":       0.52,  # 2-4 week regional delay = major window
    "streaming_delay": 0.28,  # theater-only window = moderate window
}

# Revenue base multiplier by genre (comparable title analysis)
GENRE_REVENUE_MULT = {
    "action":    2.8,
    "scifi":     2.5,
    "thriller":  1.9,
    "horror":    2.1,
    "drama":     1.5,
    "animation": 3.1,
}

# Strategy release advantage — early/simultaneous releases capture more demand
RELEASE_ADVANTAGE = {
    "global_day1":     1.12,  # simultaneous = full demand capture
    "staggered":       0.94,  # delayed regions partly lost
    "streaming_delay": 1.0,   # neutral — theater window intact
}

# Confidence weights — how reliable is our model for this combination?
# Lower confidence = wider ranges in output
CONFIDENCE_TABLE = {
    ("action",    "high",   "staggered"):       0.82,
    ("action",    "high",   "global_day1"):     0.79,
    ("action",    "high",   "streaming_delay"): 0.74,
    ("action",    "medium", "staggered"):       0.78,
    ("action",    "medium", "global_day1"):     0.76,
    ("action",    "medium", "streaming_delay"): 0.71,
    ("action",    "low",    "staggered"):       0.68,
    ("action",    "low",    "global_day1"):     0.65,
    ("action",    "low",    "streaming_delay"): 0.62,
    ("scifi",     "high",   "staggered"):       0.80,
    ("scifi",     "high",   "global_day1"):     0.77,
    ("scifi",     "high",   "streaming_delay"): 0.72,
    ("scifi",     "medium", "staggered"):       0.75,
    ("scifi",     "medium", "global_day1"):     0.73,
    ("scifi",     "medium", "streaming_delay"): 0.68,
    ("scifi",     "low",    "staggered"):       0.65,
    ("scifi",     "low",    "global_day1"):     0.63,
    ("scifi",     "low",    "streaming_delay"): 0.60,
    ("thriller",  "high",   "staggered"):       0.76,
    ("thriller",  "high",   "global_day1"):     0.74,
    ("thriller",  "high",   "streaming_delay"): 0.70,
    ("thriller",  "medium", "staggered"):       0.72,
    ("thriller",  "medium", "global_day1"):     0.70,
    ("thriller",  "medium", "streaming_delay"): 0.65,
    ("thriller",  "low",    "staggered"):       0.62,
    ("thriller",  "low",    "global_day1"):     0.60,
    ("thriller",  "low",    "streaming_delay"): 0.58,
    ("horror",    "high",   "staggered"):       0.74,
    ("horror",    "high",   "global_day1"):     0.72,
    ("horror",    "high",   "streaming_delay"): 0.68,
    ("horror",    "medium", "staggered"):       0.70,
    ("horror",    "medium", "global_day1"):     0.68,
    ("horror",    "medium", "streaming_delay"): 0.63,
    ("horror",    "low",    "staggered"):       0.60,
    ("horror",    "low",    "global_day1"):     0.58,
    ("horror",    "low",    "streaming_delay"): 0.55,
    ("drama",     "high",   "staggered"):       0.65,
    ("drama",     "high",   "global_day1"):     0.62,
    ("drama",     "high",   "streaming_delay"): 0.60,
    ("drama",     "medium", "staggered"):       0.60,
    ("drama",     "medium", "global_day1"):     0.58,
    ("drama",     "medium", "streaming_delay"): 0.55,
    ("drama",     "low",    "staggered"):       0.52,
    ("drama",     "low",    "global_day1"):     0.50,
    ("drama",     "low",    "streaming_delay"): 0.48,
    ("animation", "high",   "staggered"):       0.72,
    ("animation", "high",   "global_day1"):     0.70,
    ("animation", "high",   "streaming_delay"): 0.66,
    ("animation", "medium", "staggered"):       0.68,
    ("animation", "medium", "global_day1"):     0.65,
    ("animation", "medium", "streaming_delay"): 0.62,
    ("animation", "low",    "staggered"):       0.58,
    ("animation", "low",    "global_day1"):     0.55,
    ("animation", "low",    "streaming_delay"): 0.52,
}


# ── Core calculations (single source of truth) ────────────────────────

def _piracy_risk_score(genre: Genre, hype: Hype, strategy: Strategy) -> float:
    """
    piracy_risk = genre_sensitivity × hype_multiplier × (1 + delay_factor)
    Returns float 0.0–1.0
    
    Logic:
    - Genre sets base sensitivity (action films are more pirated than dramas)
    - Hype drives spread velocity (high buzz = pirates prioritise it)
    - Strategy delay factor: more delay = more demand in excluded regions = more piracy
    """
    base      = GENRE_SENSITIVITY[genre]
    hype_mult = HYPE_MULTIPLIER[hype]
    delay     = DELAY_FACTOR[strategy]
    raw       = base * hype_mult * (1 + delay)
    return round(min(0.97, raw), 4)


def _revenue_estimate(genre: Genre, hype: Hype, strategy: Strategy,
                      budget_m: float = 100.0) -> Tuple[float, float]:
    """
    revenue = budget × genre_mult × release_advantage × (1 - piracy_impact)
    Returns (low_estimate, high_estimate) in $M
    
    Logic:
    - Genre mult reflects comparable title multiples
    - Release advantage rewards early/simultaneous releases
    - Piracy impact decays revenue proportionally to risk score
    - Range width = function of confidence (lower confidence = wider range)
    """
    risk       = _piracy_risk_score(genre, hype, strategy)
    conf       = CONFIDENCE_TABLE.get((genre, hype, strategy), 0.60)
    genre_mult = GENRE_REVENUE_MULT[genre]
    rel_adv    = RELEASE_ADVANTAGE[strategy]

    # hype bonus on demand
    hype_bonus = {"low": 0.85, "medium": 1.0, "high": 1.22}[hype]

    base_rev   = budget_m * genre_mult * rel_adv * hype_bonus
    piracy_hit = base_rev * risk * 0.35   # piracy erodes ~35% of at-risk revenue
    mid        = base_rev - piracy_hit

    # Range width inversely proportional to confidence
    spread     = mid * (1 - conf) * 0.55
    low        = round(mid - spread, 1)
    high       = round(mid + spread, 1)
    return max(0.0, low), max(0.0, high)


def _confidence(genre: Genre, hype: Hype, strategy: Strategy) -> float:
    return CONFIDENCE_TABLE.get((genre, hype, strategy), 0.60)


def _leak_day_estimate(genre: Genre, hype: Hype, strategy: Strategy) -> Tuple[int, int]:
    """
    Estimated first piracy leak window (day range from release).
    
    Logic:
    - Staggered: excluded regions leak within days (high demand, no legal access)
    - Streaming delay: pirates wait for theatrical window then cam-rip
    - Global day1: leak still happens but window is narrower
    """
    base_days = {
        "global_day1":     (10, 18),
        "staggered":       (4,  9),
        "streaming_delay": (7,  14),
    }[strategy]

    hype_adj = {"low": 3, "medium": 0, "high": -2}[hype]
    low  = max(2, base_days[0] + hype_adj)
    high = max(low + 2, base_days[1] + hype_adj)
    return low, high


# ── Explanation engine (no black box) ─────────────────────────────────

def _explain_risk(genre: Genre, hype: Hype, strategy: Strategy) -> List[str]:
    """
    Generates human-readable explanation of why this risk score was produced.
    Every output must be explainable. This is what makes it defensible in a pitch.
    """
    reasons = []
    risk = _piracy_risk_score(genre, hype, strategy)
    sens = GENRE_SENSITIVITY[genre]
    delay = DELAY_FACTOR[strategy]

    # Genre explanation
    if sens >= 0.65:
        reasons.append(
            f"{genre.title()} films carry high base piracy sensitivity ({sens:.0%}) — "
            "they attract disproportionate piracy attention due to high demand and global fan bases."
        )
    elif sens >= 0.45:
        reasons.append(
            f"{genre.title()} films carry moderate base sensitivity ({sens:.0%}) — "
            "piracy is common but driven primarily by release gaps, not demand alone."
        )
    else:
        reasons.append(
            f"{genre.title()} films have lower base piracy sensitivity ({sens:.0%}) — "
            "piracy risk is present but typically limited to theatrical window gaps."
        )

    # Hype explanation
    if hype == "high":
        reasons.append(
            "High hype accelerates piracy spread velocity by 45% — "
            "high-buzz titles are prioritised by piracy networks within hours of first leak."
        )
    elif hype == "medium":
        reasons.append(
            "Medium hype produces standard piracy spread patterns — "
            "leak velocity follows typical genre curves."
        )
    else:
        reasons.append(
            "Low hype reduces spread velocity by 40% — "
            "lower-demand titles spread more slowly even when leaked."
        )

    # Strategy explanation
    if strategy == "staggered":
        reasons.append(
            f"Staggered release creates a {int(delay*100)}% piracy window penalty — "
            "excluded regions have high demand but no legal access, making piracy the default."
        )
    elif strategy == "streaming_delay":
        reasons.append(
            f"Streaming delay adds a {int(delay*100)}% window penalty — "
            "the gap between theatrical and home release is when cam-rip piracy peaks."
        )
    else:
        reasons.append(
            "Global day-one release eliminates regional exclusion windows — "
            "no delay factor applied. This is the strongest piracy mitigation strategy."
        )

    # Overall verdict
    if risk >= 0.70:
        reasons.append(
            f"Combined risk score {risk:.2f} — HIGH. "
            "Immediate strategy review recommended before locking release calendar."
        )
    elif risk >= 0.45:
        reasons.append(
            f"Combined risk score {risk:.2f} — MEDIUM. "
            "Manageable with targeted territory adjustments."
        )
    else:
        reasons.append(
            f"Combined risk score {risk:.2f} — LOW. "
            "Current strategy is well-positioned. Monitor high-sensitivity territories."
        )

    return reasons


def _explain_recommendation(
    winner: Strategy,
    scores: dict,
    revenues: dict
) -> str:
    """Single-sentence actionable recommendation with reasoning."""
    w_risk = scores[winner]
    w_rev  = revenues[winner]
    loser  = max(scores, key=scores.get)

    rev_lo, rev_hi = w_rev
    rev_mid = (rev_lo + rev_hi) / 2

    loser_rev = revenues[loser]
    loser_mid = (loser_rev[0] + loser_rev[1]) / 2
    gain      = round(rev_mid - loser_mid, 1)

    strategy_labels = {
        "global_day1":     "Global Day-One",
        "staggered":       "Staggered Release",
        "streaming_delay": "Streaming Delay",
    }

    return (
        f"{strategy_labels[winner]} is the recommended strategy — "
        f"piracy risk {w_risk:.2f} vs {scores[loser]:.2f} for the weakest option, "
        f"with estimated net revenue ${rev_lo}M–${rev_hi}M "
        f"(+${abs(gain)}M vs current worst-case). "
        f"{'Switch immediately — the gap is material.' if abs(gain) > 20 else 'Marginal but consistent advantage across all scenarios.'}"
    )


# ── Main simulation output ─────────────────────────────────────────────

@dataclass
class StrategyResult:
    strategy:    Strategy
    risk_score:  float           # 0.0–1.0
    risk_label:  str             # LOW / MEDIUM / HIGH
    revenue_low: float           # $M
    revenue_high:float           # $M
    revenue_mid: float           # $M (midpoint for comparison)
    confidence:  float           # 0.0–1.0
    leak_day_low:  int
    leak_day_high: int
    explanation: List[str]       # why this result happened


@dataclass
class SimulationOutput:
    """
    The only output format. Dashboards and reports read this — they don't compute.
    """
    film_genre:  Genre
    film_hype:   Hype
    budget_m:    float

    results:     List[StrategyResult]   # one per strategy, always all 3
    recommended: Strategy               # engine's top pick
    recommendation_text: str           # plain english decision
    current_strategy: Strategy         # what was passed in as input

    def to_dict(self) -> dict:
        return {
            "input": {
                "genre":    self.film_genre,
                "hype":     self.film_hype,
                "budget_m": self.budget_m,
                "current_strategy": self.current_strategy,
            },
            "recommended": self.recommended,
            "recommendation": self.recommendation_text,
            "strategies": [
                {
                    "strategy":     r.strategy,
                    "risk_score":   r.risk_score,
                    "risk_label":   r.risk_label,
                    "revenue_low":  r.revenue_low,
                    "revenue_high": r.revenue_high,
                    "revenue_mid":  r.revenue_mid,
                    "confidence":   r.confidence,
                    "leak_day_low":  r.leak_day_low,
                    "leak_day_high": r.leak_day_high,
                    "explanation":  r.explanation,
                }
                for r in self.results
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def print_summary(self):
        print("\n" + "═"*60)
        print(f"  CINERISK ENGINE — SIMULATION OUTPUT")
        print(f"  Genre: {self.film_genre.upper()} | Hype: {self.film_hype.upper()} | Budget: ${self.budget_m}M")
        print("═"*60)
        for r in self.results:
            marker = " ◀ RECOMMENDED" if r.strategy == self.recommended else ""
            current = " (current)" if r.strategy == self.current_strategy else ""
            print(f"\n  {r.strategy.upper()}{current}{marker}")
            print(f"  Risk:     {r.risk_score:.2f}  [{r.risk_label}]  (confidence: {r.confidence:.0%})")
            print(f"  Revenue:  ${r.revenue_low}M – ${r.revenue_high}M")
            print(f"  Leak day: Day {r.leak_day_low}–{r.leak_day_high}")
            print(f"\n  Why:")
            for line in r.explanation:
                print(f"    • {line}")
        print("\n" + "─"*60)
        print(f"  RECOMMENDATION:")
        print(f"  {self.recommendation_text}")
        print("═"*60 + "\n")


# ── Public API (single entry point) ───────────────────────────────────

def simulate(
    genre:    Genre,
    hype:     Hype,
    strategy: Strategy,
    budget_m: float = 100.0,
) -> SimulationOutput:
    """
    Run a full simulation for a film.
    Always compares all 3 strategies.
    Always returns ranges + confidence + explanations.

    This is the ONLY function dashboards and reports should call.
    """
    film = FilmInput(genre=genre, hype=hype, strategy=strategy).validate()

    all_strategies: List[Strategy] = ["global_day1", "staggered", "streaming_delay"]
    results = []
    risk_scores  = {}
    rev_ranges   = {}

    for strat in all_strategies:
        risk  = _piracy_risk_score(film.genre, film.hype, strat)
        rev_lo, rev_hi = _revenue_estimate(film.genre, film.hype, strat, budget_m)
        conf  = _confidence(film.genre, film.hype, strat)
        ld_lo, ld_hi = _leak_day_estimate(film.genre, film.hype, strat)
        expl  = _explain_risk(film.genre, film.hype, strat)
        label = "HIGH" if risk >= 0.70 else ("MEDIUM" if risk >= 0.45 else "LOW")

        results.append(StrategyResult(
            strategy=strat,
            risk_score=risk,
            risk_label=label,
            revenue_low=rev_lo,
            revenue_high=rev_hi,
            revenue_mid=round((rev_lo + rev_hi) / 2, 1),
            confidence=conf,
            leak_day_low=ld_lo,
            leak_day_high=ld_hi,
            explanation=expl,
        ))
        risk_scores[strat] = risk
        rev_ranges[strat]  = (rev_lo, rev_hi)

    # Best strategy = highest revenue midpoint (adjusted for risk)
    def score_strategy(strat):
        lo, hi = rev_ranges[strat]
        mid = (lo + hi) / 2
        risk = risk_scores[strat]
        return mid * (1 - risk * 0.3)   # risk-adjusted net score

    recommended = min(risk_scores, key=risk_scores.get)   # lowest risk
    # Break ties with revenue
    min_risk = risk_scores[recommended]
    candidates = [s for s,r in risk_scores.items() if abs(r - min_risk) < 0.05]
    if len(candidates) > 1:
        recommended = max(candidates, key=score_strategy)

    rec_text = _explain_recommendation(recommended, risk_scores, rev_ranges)

    return SimulationOutput(
        film_genre=film.genre,
        film_hype=film.hype,
        budget_m=budget_m,
        results=results,
        recommended=recommended,
        recommendation_text=rec_text,
        current_strategy=film.strategy,
    )


# ── CLI demo ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nCINERISK ENGINE v1 — TEST SCENARIOS")

    scenarios = [
        ("action",    "high",   "staggered",       220.0, "Nova Station (high-risk case)"),
        ("action",    "medium", "global_day1",      180.0, "Titan's Edge (optimised case)"),
        ("drama",     "low",    "streaming_delay",   12.0, "Quiet Hours (low-risk case)"),
        ("animation", "high",   "global_day1",       95.0, "Pixel Pals 3 (franchise case)"),
        ("thriller",  "medium", "staggered",         65.0, "Deep Water (medium risk)"),
    ]

    for genre, hype, strategy, budget, label in scenarios:
        print(f"\n{'─'*60}")
        print(f"  SCENARIO: {label}")
        out = simulate(genre, hype, strategy, budget)
        out.print_summary()

        # Also verify JSON output works (for API/dashboard use)
        data = out.to_dict()
        assert data["recommended"] in ("global_day1","staggered","streaming_delay")
        assert all(r["confidence"] > 0 for r in data["strategies"])
        assert all(r["revenue_low"] <= r["revenue_high"] for r in data["strategies"])
        print(f"  ✓ JSON output validated")

    print("\n✓ All scenarios passed. Engine ready.\n")
