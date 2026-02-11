"""
Product type classification for Kenyan financial content.

Categories cover the full spectrum of Kenyan financial products
from mobile money to capital markets.
"""

from typing import List


PRODUCT_KEYWORDS = {
    "savings": [
        "savings account", "fixed deposit", "call deposit", "money market",
        "savings plan", "save money", "interest on savings",
        "fosa", "savings product", "saving tips",
    ],
    "loans": [
        "loan", "credit", "borrow", "overdraft",
        "personal loan", "business loan", "asset finance",
        "lpo financing", "salary advance", "check-off",
        "credit facility", "loan repayment",
    ],
    "mortgage": [
        "mortgage", "home loan", "housing finance",
        "home ownership", "kmrc", "property finance",
        "housing fund", "affordable housing",
    ],
    "insurance": [
        "insurance", "cover", "premium", "claim", "underwrite",
        "life insurance", "health insurance", "motor insurance",
        "general insurance", "nhif", "medical cover",
    ],
    "investment": [
        "investment", "portfolio", "returns", "dividend",
        "unit trust", "money market fund", "equity fund",
        "mutual fund", "wealth management", "asset management",
    ],
    "pension": [
        "pension", "retirement", "nssf", "provident fund",
        "annuity", "retirement benefit", "gratuity",
        "retirement savings", "pension scheme",
    ],
    "mobile_money": [
        "m-pesa", "mpesa", "airtel money", "t-kash",
        "mobile money", "mobile wallet", "send money",
        "paybill", "till number", "lipa na", "fuliza",
    ],
    "sacco_products": [
        "sacco", "fosa", "bosa", "share capital",
        "sacco loan", "sacco savings", "sacco dividend",
        "merry-go-round", "chama",
    ],
    "tax": [
        "tax", "paye", "vat", "income tax", "corporate tax",
        "turnover tax", "withholding tax", "capital gains",
        "tax return", "kra", "itax", "tax compliance",
    ],
    "budgeting": [
        "budget", "expense tracking", "spending", "financial plan",
        "emergency fund", "financial goal", "saving plan",
        "money management", "personal finance",
    ],
    "equities": [
        "stock", "share", "equity", "nse",
        "listed company", "ipo", "market capitalization",
        "stock exchange", "share price", "equity trading",
    ],
    "bonds": [
        "bond", "treasury bill", "t-bill", "t-bond",
        "government securities", "infrastructure bond",
        "fixed income", "coupon", "green bond",
    ],
    "forex": [
        "forex", "foreign exchange", "exchange rate",
        "currency", "dollar", "euro", "sterling",
        "fx market", "currency pair",
    ],
}


def classify_product_types(text: str, source_id: str = "",
                           institution_type: str = "") -> List[str]:
    """
    Classify text into product types.

    Returns list of matching product types (can be multiple).
    """
    text_lower = text.lower()
    matches = []

    for product, keywords in PRODUCT_KEYWORDS.items():
        match_count = sum(1 for kw in keywords if kw in text_lower)
        if match_count >= 2:
            matches.append(product)

    return matches
