"""
Content relevance scoring for Kenyan financial documents.

Scores content quality and relevance on a 0.0-1.0 scale based on:
- Text length and density
- Kenya-specific financial term presence
- Source authority (regulatory > bank > education > media)
- Structural quality (numbers, data richness)
"""

import re
from typing import Dict


# Kenya-specific financial terms that indicate high-value content
KENYA_TERMS = [
    "kes", "cbk", "nse", "kra", "cma", "knbs", "nssf", "nhif",
    "m-pesa", "mpesa", "sacco", "chama", "paye", "treasury bill",
    "nairobi", "kenya", "shilling", "central bank rate",
    "safaricom", "equity bank", "kcb", "cooperative",
]

# Source authority weights
AUTHORITY_MAP = {
    "regulatory": 0.15,
    "bank": 0.10,
    "investment": 0.10,
    "stockbroker": 0.10,
    "sacco": 0.05,
    "platform": 0.05,
    "education": 0.0,
    "media": -0.05,
}


def score_relevance(text: str, metadata: Dict) -> float:
    """
    Score content quality/relevance on 0.0-1.0 scale.

    Args:
        text: Document or chunk text
        metadata: Existing metadata dict

    Returns:
        Float between 0.0 and 1.0
    """
    score = 0.5  # Base score

    # Length factor
    text_len = len(text)
    if text_len < 100:
        score -= 0.2
    elif text_len > 300:
        score += 0.1

    # Kenya-specific financial terms
    text_lower = text.lower()
    term_count = sum(1 for t in KENYA_TERMS if t in text_lower)
    score += min(term_count * 0.03, 0.15)

    # Source authority
    inst_type = metadata.get("institution_type", "")
    score += AUTHORITY_MAP.get(inst_type, 0.0)

    # Structural quality (numbers indicate data-rich content)
    number_count = len(re.findall(r'\d+\.?\d*%?', text))
    if number_count > 5:
        score += 0.05

    # Penalize very short content
    word_count = len(text.split())
    if word_count < 20:
        score -= 0.15

    return max(0.0, min(1.0, round(score, 3)))
