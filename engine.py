"""
CINEOS Core Engine v2.1
=========================
Changes from v2:
- Budget sensitivity added — large films are bigger piracy targets
- Small films (<$20M) get lower base risk regardless of genre
- Large films (>$150M) get elevated risk — higher profile = higher piracy priority
- Revenue model now scales non-linearly with budget (diminishing returns at top)
- Franchise flag replaced by budget proxy (high budget implies franchise-level attention)
"""

from dataclasses import dataclass
from typing import Literal, List, Tuple
import json

Genre    = Literal["action","scifi","thriller","horror","drama","animation"]
Hype     = Literal["low","medium","high"]
Strategy = Literal["global_day1","staggered","streaming_delay"]

@dataclass
class FilmInput:
    genre:    Genre
    hype:     Hype
    strategy: Strategy
    def validate(self):
        assert self.genre    in ("action","scifi","thriller","horror","drama","animation")
        assert self.hype     in ("low","medium","high")
        assert self.strategy in ("global_day1","staggered","streaming_delay")
        return self

# ── Constants ──────────────────────────────────────────────────────────

GENRE_SENSITIVITY = {
    "action":    0.62,
    "scifi":     0.55,
    "thriller":  0.48,
    "horror":    0.42,
    "drama":     0.18,
    "animation": 0.30,
}

HYPE_MULTIPLIER = {
    "low":    0.65,
    "medium": 1.00,
    "high":   1.38,
}

DELAY_PENALTY = {
    "global_day1":     0.00,
    "staggered":       0.44,
    "streaming_delay": 0.22,
}

EXECUTION_COST = {
    "global_day1":     0.12,
    "staggered":       0.04,
    "streaming_delay": 0.07,
}

MARKET_READINESS_BONUS = {
    ("drama",     "staggered"):       0.14,
    ("drama",     "streaming_delay"): 0.10,
    ("animation", "staggered"):       0.08,
    ("animation", "streaming_delay"): 0.06,
    ("thriller",  "streaming_delay"): 0.05,
    ("horror",    "streaming_delay"): 0.07,
}

GENRE_REVENUE_MULT = {
    "action":    2.6,
    "scifi":     2.3,
    "thriller":  1.8,
    "horror":    2.0,
    "drama":     1.4,
    "animation": 2.9,
}

RELEASE_ADVANTAGE = {
    "global_day1":     1.08,
    "staggered":       0.96,
    "streaming_delay": 1.02,
}

CONFIDENCE_BASE = {
    ("action",    "high"):   0.80, ("action",    "medium"): 0.76, ("action",    "low"): 0.66,
    ("scifi",     "high"):   0.77, ("scifi",     "medium"): 0.72, ("scifi",     "low"): 0.63,
    ("thriller",  "high"):   0.74, ("thriller",  "medium"): 0.70, ("thriller",  "low"): 0.60,
    ("horror",    "high"):   0.72, ("horror",    "medium"): 0.67, ("horror",    "low"): 0.58,
    ("drama",     "high"):   0.63, ("drama",     "medium"): 0.58, ("drama",     "low"): 0.50,
    ("animation", "high"):   0.70, ("animation", "medium"): 0.65, ("animation", "low"): 0.56,
}

STRATEGY_CONF_MOD = {
    "global_day1": -0.02, "staggered": 0.02, "streaming_delay": 0.00,
}

# ── Budget sensitivity ────────────────────────────────────────────────

def _budget_risk_modifier(budget_m: float) -> float:
    """
    Budget is a proxy for profile — bigger films are bigger piracy targets.

    Logic:
    - <$10M:   indie/micro — low piracy profile, -0.18 modifier
    - $10-30M: small indie — below radar, -0.10
    - $30-80M: mid-range — standard profile, 0.00
    - $80-150M: major release — elevated attention, +0.06
    - $150-250M: tentpole — high priority piracy target, +0.12
    - >$250M:  event film — maximum piracy profile, +0.18

    Research basis: MPA data shows piracy volume correlates strongly
    with production profile/marketing spend, not just demand.
    """
    if budget_m < 10:    return -0.18
    if budget_m < 30:    return -0.10
    if budget_m < 80:    return  0.00
    if budget_m < 150:   return  0.06
    if budget_m < 250:   return  0.12
    return                        0.18


def _budget_revenue_mult(budget_m: float) -> float:
    """
    Revenue multiplier adjusts for budget scale.
    Small films can punch above weight; massive films face diminishing returns.

    - <$20M:    indie can 10x+ but median is higher multiple → 1.15
    - $20-60M:  standard indie → 1.05
    - $60-120M: mid-major → 1.00
    - $120-200M: tentpole — marketing efficient → 0.96
    - >$200M:   event film — expensive marketing eats returns → 0.90
    """
    if budget_m < 20:   return 1.15
    if budget_m < 60:   return 1.05
    if budget_m < 120:  return 1.00
    if budget_m < 200:  return 0.96
    return                      0.90


def _budget_confidence_mod(budget_m: float) -> float:
    """
    Larger films have more historical comparables → higher confidence.
    Very small films are harder to predict → lower confidence.
    """
    if budget_m < 10:   return -0.08
    if budget_m < 30:   return -0.04
    if budget_m < 80:   return  0.00
    if budget_m < 200:  return  0.03
    return                       0.05


# ── Core calculations ──────────────────────────────────────────────────

def _piracy_risk(genre: Genre, hype: Hype, strategy: Strategy,
                 budget_m: float) -> float:
    """
    risk = (genre_sensitivity × hype_multiplier × (1 + delay_penalty))
           + budget_risk_modifier

    Budget modifier is additive — it shifts the whole curve up or down
    based on the film's profile, independent of genre/hype/strategy.
    """
    base    = GENRE_SENSITIVITY[genre]
    hype_m  = HYPE_MULTIPLIER[hype]
    delay   = DELAY_PENALTY[strategy]
    bmod    = _budget_risk_modifier(budget_m)
    raw     = base * hype_m * (1 + delay) + bmod
    return round(min(0.94, max(0.04, raw)), 4)


def _revenue(genre: Genre, hype: Hype, strategy: Strategy,
             budget_m: float) -> Tuple[float, float]:
    risk    = _piracy_risk(genre, hype, strategy, budget_m)
    conf    = _confidence(genre, hype, strategy, budget_m)
    gmult   = GENRE_REVENUE_MULT[genre]
    radv    = RELEASE_ADVANTAGE[strategy]
    hbonus  = {"low":0.82,"medium":1.0,"high":1.20}[hype]
    ecost   = EXECUTION_COST[strategy]
    mbonus  = MARKET_READINESS_BONUS.get((genre, strategy), 0.0)
    bmult   = _budget_revenue_mult(budget_m)

    base_rev    = budget_m * gmult * radv * hbonus * bmult
    piracy_hit  = base_rev * risk * 0.32
    exec_hit    = base_rev * ecost
    market_gain = base_rev * mbonus
    mid         = base_rev - piracy_hit - exec_hit + market_gain

    spread = mid * (1 - conf) * 0.50
    lo     = round(max(0.0, mid - spread), 1)
    hi     = round(max(0.0, mid + spread), 1)
    return lo, hi


def _confidence(genre: Genre, hype: Hype, strategy: Strategy,
                budget_m: float) -> float:
    base  = CONFIDENCE_BASE.get((genre, hype), 0.60)
    smod  = STRATEGY_CONF_MOD.get(strategy, 0.0)
    bmod  = _budget_confidence_mod(budget_m)
    return round(min(0.90, max(0.42, base + smod + bmod)), 3)


def _leak_day(genre: Genre, hype: Hype, strategy: Strategy,
              budget_m: float) -> Tuple[int, int]:
    base = {"global_day1":(12,22), "staggered":(4,10), "streaming_delay":(8,16)}[strategy]
    hadj = {"low":4,"medium":0,"high":-3}[hype]
    # Big films leak faster — more pirates targeting them
    badj = 3 if budget_m < 30 else (0 if budget_m < 150 else -2)
    lo   = max(2, base[0] + hadj + badj)
    hi   = max(lo+2, base[1] + hadj + badj)
    return lo, hi


def _net_score(genre, hype, strategy, budget_m):
    risk   = _piracy_risk(genre, hype, strategy, budget_m)
    lo, hi = _revenue(genre, hype, strategy, budget_m)
    mid    = (lo + hi) / 2
    ecost  = EXECUTION_COST[strategy]
    return mid * (1 - risk * 0.28) * (1 - ecost)


# ── Explanation ────────────────────────────────────────────────────────

def _explain(genre: Genre, hype: Hype, strategy: Strategy,
             budget_m: float) -> List[str]:
    reasons = []
    risk    = _piracy_risk(genre, hype, strategy, budget_m)
    sens    = GENRE_SENSITIVITY[genre]
    delay   = DELAY_PENALTY[strategy]
    ecost   = EXECUTION_COST[strategy]
    mbon    = MARKET_READINESS_BONUS.get((genre, strategy), 0.0)
    bmod    = _budget_risk_modifier(budget_m)

    # Genre
    if sens >= 0.55:
        reasons.append(f"{genre.title()} films carry high base piracy sensitivity ({sens:.0%}) — disproportionate piracy attention due to high global demand.")
    elif sens >= 0.35:
        reasons.append(f"{genre.title()} films have moderate sensitivity ({sens:.0%}) — risk driven primarily by release gaps, not demand alone.")
    else:
        reasons.append(f"{genre.title()} films have low base sensitivity ({sens:.0%}) — audience is more niche, piracy spread is slower.")

    # Budget
    if bmod <= -0.10:
        reasons.append(f"${budget_m:.0f}M budget places this in the low-profile tier — smaller films attract less organised piracy attention. Risk reduced by {abs(bmod):.0%}.")
    elif bmod >= 0.12:
        reasons.append(f"${budget_m:.0f}M budget makes this a high-profile piracy target — event films are prioritised by piracy networks globally. Risk elevated by {bmod:.0%}.")
    elif bmod > 0:
        reasons.append(f"${budget_m:.0f}M budget is tentpole scale — elevated piracy profile vs mid-range releases. Risk elevated by {bmod:.0%}.")
    else:
        reasons.append(f"${budget_m:.0f}M budget sits in the standard piracy profile range — no significant budget modifier applied.")

    # Hype
    if hype == "high":
        reasons.append("High hype increases piracy spread velocity by 38% — prioritised by piracy networks within hours of first availability.")
    elif hype == "medium":
        reasons.append("Medium hype produces standard piracy spread — leak velocity follows typical genre curves.")
    else:
        reasons.append("Low hype reduces spread velocity by 35% — piracy spreads more slowly even if a leak occurs.")

    # Strategy
    if strategy == "staggered":
        reasons.append(f"Staggered release adds a {delay:.0%} piracy window penalty — excluded regions have high demand with no legal access.")
    elif strategy == "streaming_delay":
        reasons.append(f"Streaming delay adds a {delay:.0%} window penalty — the gap between theatrical and home release is when cam-rip piracy peaks.")
    else:
        reasons.append(f"Global day-one eliminates regional exclusion windows. Execution cost ({ecost:.0%}) reflects higher coordination spend for simultaneous worldwide launch.")

    if mbon > 0:
        reasons.append(f"{genre.title()} films benefit from a {mbon:.0%} market readiness bonus under {strategy.replace('_',' ')} — careful rollout builds word-of-mouth.")

    # Verdict
    if risk >= 0.75:
        reasons.append(f"Combined risk score {risk:.2f} — HIGH. Immediate strategy review recommended.")
    elif risk >= 0.45:
        reasons.append(f"Combined risk score {risk:.2f} — MEDIUM. Manageable with targeted territory adjustments.")
    else:
        reasons.append(f"Combined risk score {risk:.2f} — LOW. Current strategy is well-positioned.")

    return reasons


def _recommendation_text(recommended, scores, revenues, current) -> str:
    labels = {"global_day1":"Global Day-One","staggered":"Staggered Release","streaming_delay":"Streaming Delay"}
    worst  = max(scores, key=scores.get)
    lo, hi = revenues[recommended]
    mid    = (lo + hi) / 2
    cur_lo, cur_hi = revenues[current]
    cur_mid = (cur_lo + cur_hi) / 2
    delta  = round(mid - cur_mid, 1)
    if recommended == current:
        return (f"{labels[recommended]} is already your strongest option — risk score {scores[recommended]:.2f} with estimated net revenue ${lo}M–${hi}M. Focus on execution quality rather than strategy change.")
    return (f"{labels[recommended]} is the recommended strategy — risk {scores[recommended]:.2f} vs {scores[worst]:.2f} for the weakest option, net revenue ${lo}M–${hi}M ({'+'if delta>=0 else ''}{delta}M vs current). {'Switch immediately — the gap is material.' if abs(delta)>15 else 'Consistent advantage across scenarios.'}")


# ── Output types ───────────────────────────────────────────────────────

@dataclass
class StrategyResult:
    strategy:     Strategy
    risk_score:   float
    risk_label:   str
    revenue_low:  float
    revenue_high: float
    revenue_mid:  float
    confidence:   float
    leak_day_low:  int
    leak_day_high: int
    net_score:    float
    explanation:  List[str]

@dataclass
class SimulationOutput:
    film_genre:          Genre
    film_hype:           Hype
    budget_m:            float
    results:             List[StrategyResult]
    recommended:         Strategy
    recommendation_text: str
    current_strategy:    Strategy

    def to_dict(self):
        return {
            "input": {"genre":self.film_genre,"hype":self.film_hype,"budget_m":self.budget_m,"current_strategy":self.current_strategy},
            "recommended": self.recommended,
            "recommendation": self.recommendation_text,
            "strategies": [{
                "strategy":r.strategy,"risk_score":r.risk_score,"risk_label":r.risk_label,
                "revenue_low":r.revenue_low,"revenue_high":r.revenue_high,"revenue_mid":r.revenue_mid,
                "confidence":r.confidence,"leak_day_low":r.leak_day_low,"leak_day_high":r.leak_day_high,
                "net_score":r.net_score,"explanation":r.explanation,
            } for r in self.results],
        }

    def to_json(self): return json.dumps(self.to_dict(), indent=2)

    def print_summary(self):
        print(f"\n{'═'*64}")
        print(f"  ENGINE v2.1 — {self.film_genre.upper()} / {self.film_hype.upper()} / ${self.budget_m}M")
        print(f"{'═'*64}")
        for r in self.results:
            m = " ◀ REC" if r.strategy==self.recommended else ""
            c = " (current)" if r.strategy==self.current_strategy else ""
            print(f"\n  {r.strategy.upper()}{c}{m}")
            print(f"  Risk: {r.risk_score:.2f} [{r.risk_label}]  conf={r.confidence:.0%}  net={r.net_score:.1f}")
            print(f"  Rev:  ${r.revenue_low}M–${r.revenue_high}M  Leak: Day {r.leak_day_low}–{r.leak_day_high}")
        print(f"\n  {self.recommendation_text}")
        print(f"{'═'*64}\n")


# ── Public API ─────────────────────────────────────────────────────────

def simulate(genre: Genre, hype: Hype, strategy: Strategy,
             budget_m: float = 100.0) -> SimulationOutput:
    film = FilmInput(genre=genre, hype=hype, strategy=strategy).validate()
    all_strats: List[Strategy] = ["global_day1","staggered","streaming_delay"]
    results, scores, revenues = [], {}, {}

    for s in all_strats:
        risk    = _piracy_risk(film.genre, film.hype, s, budget_m)
        lo, hi  = _revenue(film.genre, film.hype, s, budget_m)
        conf    = _confidence(film.genre, film.hype, s, budget_m)
        llo,lhi = _leak_day(film.genre, film.hype, s, budget_m)
        expl    = _explain(film.genre, film.hype, s, budget_m)
        label   = "HIGH" if risk>=0.70 else ("MEDIUM" if risk>=0.45 else "LOW")
        net     = _net_score(film.genre, film.hype, s, budget_m)
        results.append(StrategyResult(
            strategy=s,risk_score=risk,risk_label=label,
            revenue_low=lo,revenue_high=hi,revenue_mid=round((lo+hi)/2,1),
            confidence=conf,leak_day_low=llo,leak_day_high=lhi,
            net_score=round(net,1),explanation=expl,
        ))
        scores[s]=risk; revenues[s]=(lo,hi)

    recommended = max(all_strats, key=lambda s: _net_score(film.genre, film.hype, s, budget_m))
    return SimulationOutput(
        film_genre=film.genre,film_hype=film.hype,budget_m=budget_m,
        results=results,recommended=recommended,
        recommendation_text=_recommendation_text(recommended,scores,revenues,film.strategy),
        current_strategy=film.strategy,
    )


# ── Validation ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("\nENGINE v2.1 — BUDGET SENSITIVITY VALIDATION\n")

    print("Budget sensitivity — action/high/staggered:")
    print(f"  {'Budget':>8}  {'Risk':>6}  {'Revenue Range':>22}  {'Leak Day':>10}  {'Rec'}")
    print(f"  {'-'*70}")
    for b in [5, 15, 40, 80, 150, 220, 350]:
        out = simulate('action','high','staggered', b)
        cur = next(r for r in out.results if r.strategy=='staggered')
        print(f"  ${b:>6}M  {cur.risk_score:>6.2f}  ${cur.revenue_low}M–${cur.revenue_high}M  Day {cur.leak_day_low}–{cur.leak_day_high}  {out.recommended}")

    print("\nRecommendation variety check:")
    rec_counts = {"global_day1":0,"staggered":0,"streaming_delay":0}
    for genre in ("action","scifi","thriller","horror","drama","animation"):
        for hype in ("low","medium","high"):
            for budget in (10, 50, 150, 300):
                out = simulate(genre, hype, 'staggered', budget)
                rec_counts[out.recommended] += 1
    total = sum(rec_counts.values())
    for s,c in rec_counts.items():
        print(f"  {s:20} {c:3} / {total}  ({c/total*100:.0f}%)")

    print("\nSample scenarios:")
    simulate('action','high','staggered',220).print_summary()
    simulate('drama','low','global_day1',8).print_summary()
    simulate('animation','high','streaming_delay',95).print_summary()
    print("✓ Engine v2.1 ready.\n")
