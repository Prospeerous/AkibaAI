"""
Persona classification for Kenyan financial content.

Personas:
- student: University/college students, HELB borrowers, campus finance
- sme: Small and medium enterprise owners, biashara operators
- farmer: Agricultural finance, farming, agribusiness
- salaried: Employed individuals, PAYE payers, pension contributors
- gig_worker: Freelancers, digital workers, platform economy
- informal_sector: Jua kali, market traders, bodaboda, mama mboga
- diaspora: Kenyans abroad, remittances, cross-border finance
- general: Content applicable to everyone
"""

from typing import List


# Strong keywords: 1 match = high confidence
# Weak keywords: need 2+ matches to count
PERSONA_KEYWORDS = {
    "student": {
        "strong": [
            "student loan", "helb", "university fee", "campus",
            "scholarship", "student account", "tuition",
            "higher education loan", "helb repayment", "college fees",
            "bursary", "education fund", "school fees loan",
        ],
        "weak": [
            "student", "university", "college", "young", "graduate",
            "youth", "internship", "first job", "attachment",
        ],
        "source_hints": [],
    },
    "sme": {
        "strong": [
            "sme loan", "business loan", "msme", "small business",
            "business account", "trade finance", "invoice discounting",
            "lpo financing", "asset finance", "business growth",
            "entrepreneurship", "business plan", "startup capital",
            "biashara", "working capital", "merchant account",
            "business overdraft", "sme banking",
        ],
        "weak": [
            "business", "enterprise", "company", "sme", "entrepreneur",
            "merchant", "supplier", "vendor", "turnover tax",
        ],
        "source_hints": [],
    },
    "farmer": {
        "strong": [
            "agricultural finance", "farm loan", "crop insurance",
            "agricultural insurance", "farming", "agribusiness",
            "dairy loan", "livestock", "horticulture",
            "farm input", "agricultural value chain",
            "kilimo", "shamba", "cooperative society",
            "tea bonus", "coffee cooperative",
        ],
        "weak": [
            "agriculture", "farm", "crop", "harvest", "rural",
            "cooperative", "agrochemical",
        ],
        "source_hints": [],
    },
    "salaried": {
        "strong": [
            "paye", "salary advance", "payroll", "check-off",
            "salary account", "pension", "nssf contribution",
            "nhif", "gratuity", "staff loan", "employment benefits",
            "retirement planning", "provident fund",
            "pay as you earn", "employer deduction",
        ],
        "weak": [
            "salary", "employed", "employee", "employer", "payslip",
            "monthly income", "deductions", "net pay",
        ],
        "source_hints": [],
    },
    "gig_worker": {
        "strong": [
            "freelance", "gig economy", "digital worker",
            "online income", "platform worker", "content creator",
            "ride hailing", "delivery driver", "remote work income",
            "freelance tax", "digital nomad",
        ],
        "weak": [
            "freelancer", "contractor", "self-employed", "side hustle",
            "part-time", "casual worker", "gig",
        ],
        "source_hints": [],
    },
    "informal_sector": {
        "strong": [
            "jua kali", "market trader", "bodaboda", "mama mboga",
            "chama", "merry-go-round", "table banking",
            "informal sector", "micro enterprise",
            "mkokoteni", "kiosk", "hawker", "mama fua",
            "boda boda", "mitumba",
        ],
        "weak": [
            "informal", "trader", "market", "small trader",
            "daily income", "cash business",
        ],
        "source_hints": [],
    },
    "diaspora": {
        "strong": [
            "diaspora", "remittance", "send money kenya",
            "diaspora account", "foreign income", "offshore",
            "kenya abroad", "expatriate", "diaspora bond",
            "diaspora banking", "international money transfer",
        ],
        "weak": [
            "diaspora", "abroad", "remittance", "forex",
            "international transfer", "foreign exchange",
        ],
        "source_hints": [],
    },
}


def classify_persona(text: str, source_id: str = "",
                     institution_type: str = "") -> List[str]:
    """
    Classify text into one or more personas.

    Returns list of matching personas, or ["general"] if no specific match.
    """
    text_lower = text.lower()
    matches = []

    for persona, rules in PERSONA_KEYWORDS.items():
        score = 0

        # Strong keywords: 1 match = confident
        for kw in rules["strong"]:
            if kw in text_lower:
                score += 3
                break

        # Weak keywords: count matches
        weak_count = sum(1 for kw in rules["weak"] if kw in text_lower)
        score += weak_count

        # Source hints
        if source_id in rules.get("source_hints", []):
            score += 2

        if score >= 3:
            matches.append(persona)

    return matches if matches else ["general"]
