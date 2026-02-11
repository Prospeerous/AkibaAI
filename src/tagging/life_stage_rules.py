"""
Financial literacy life-stage classification.

Levels:
- beginner: Basic concepts, getting started, how-to guides
- intermediate: Comparison, strategy, portfolio management
- advanced: Technical analysis, regulatory compliance, macroprudential
"""


LIFE_STAGE_INDICATORS = {
    "beginner": {
        "keywords": [
            "how to", "beginner", "getting started", "basics",
            "what is", "introduction to", "first time",
            "financial literacy", "learn about", "simple guide",
            "step by step", "for beginners", "explained simply",
            "tips for", "start saving", "open an account",
            "money 101", "personal finance basics",
        ],
        "source_hints": [
            "mashauri", "centonomy", "malkia", "kwft",
            "fin_incorrect", "lynn_ngugi", "susan_wong",
            "abojani",
        ],
        "institution_hints": ["education"],
    },
    "intermediate": {
        "keywords": [
            "compare", "best", "analysis", "strategy",
            "diversification", "portfolio", "optimization",
            "financial planning", "investment strategy",
            "asset allocation", "risk management",
            "tax planning", "retirement planning",
        ],
        "source_hints": [
            "cytonn", "genghis", "faida", "dyer_blair", "sib",
        ],
        "institution_hints": ["investment", "stockbroker"],
    },
    "advanced": {
        "keywords": [
            "technical analysis", "fundamental analysis",
            "derivatives", "hedging", "structured products",
            "capital adequacy", "basel", "regulatory compliance",
            "monetary policy committee", "prudential guidelines",
            "systemic risk", "macroprudential", "yield curve",
            "quantitative easing", "open market operations",
        ],
        "source_hints": ["cbk", "cma", "treasury", "nse"],
        "institution_hints": ["regulatory"],
    },
}


def classify_life_stage(text: str, source_id: str = "",
                        institution_type: str = "") -> str:
    """
    Classify financial literacy level.

    Returns: beginner, intermediate, or advanced.
    Defaults to "intermediate".
    """
    text_lower = text.lower()
    scores = {}

    for stage, rules in LIFE_STAGE_INDICATORS.items():
        score = sum(1 for kw in rules["keywords"] if kw in text_lower)
        if source_id in rules.get("source_hints", []):
            score += 3
        if institution_type in rules.get("institution_hints", []):
            score += 2
        scores[stage] = score

    if max(scores.values()) == 0:
        return "intermediate"

    return max(scores, key=scores.get)
