"""
Risk level classification for Kenyan financial content.

Levels:
- low: Government securities, savings accounts, pensions, insurance
- medium: Unit trusts, SACCOs, balanced funds, corporate bonds
- high: Equities, real estate, IPOs, venture capital
- very_high: Forex trading, crypto, derivatives, leveraged instruments
"""


RISK_INDICATORS = {
    "very_high": [
        "high risk", "speculative", "forex trading", "crypto",
        "leveraged", "derivatives", "options trading",
        "margin trading", "day trading", "pyramid scheme",
        "ponzi", "cryptocurrency", "binary options",
    ],
    "high": [
        "equities", "stock market", "shares", "ipo",
        "venture capital", "private equity", "startup",
        "real estate investment", "land banking",
        "nse trading", "capital appreciation",
    ],
    "medium": [
        "unit trust", "money market fund", "balanced fund",
        "corporate bond", "infrastructure bond",
        "sacco investment", "mutual fund", "diversified",
        "moderate risk", "income fund",
    ],
    "low": [
        "savings account", "fixed deposit", "treasury bill",
        "government bond", "nssf", "pension",
        "insurance", "money market", "call deposit",
        "guaranteed", "capital protection", "risk-free",
    ],
}


def classify_risk_level(text: str, source_id: str = "",
                        institution_type: str = "") -> str:
    """
    Classify text risk level.

    Returns single risk level: low, medium, high, very_high.
    Defaults to "medium" if no clear signal.
    """
    text_lower = text.lower()
    scores = {}

    for level, keywords in RISK_INDICATORS.items():
        scores[level] = sum(1 for kw in keywords if kw in text_lower)

    if max(scores.values()) == 0:
        return "medium"

    return max(scores, key=scores.get)
