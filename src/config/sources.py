"""
Source definitions for all Kenyan financial data providers.

Each source is a SourceConfig dataclass that tells the scraper:
  - where to look (seed URLs)
  - what to look for (URL patterns, file types)
  - how to behave (rate limits, depth)
  - how to classify the output (domain, institution type)
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SourceConfig:
    """Configuration for a single data source."""
    source_id: str                              # Unique key, e.g. "cbk"
    name: str                                   # Human name
    base_url: str                               # Root domain
    seed_urls: List[str]                        # Pages to start crawling from
    institution_type: str                       # regulatory | bank | investment | sacco | platform
                                                # | stockbroker | media | education
    financial_domain: List[str]                 # e.g. ["monetary_policy", "banking"]
    pdf_enabled: bool = True                    # Download PDFs
    html_enabled: bool = True                   # Extract HTML article content
    max_depth: int = 2                          # Crawl depth from seed URLs
    max_documents: int = 100                    # Hard cap per source
    request_delay: float = 2.0                  # Seconds between requests
    url_patterns: List[str] = field(default_factory=list)  # Regex include patterns
    url_exclude: List[str] = field(default_factory=list)   # Regex exclude patterns
    requires_javascript: bool = False           # Needs browser rendering
    notes: str = ""


# ═══════════════════════════════════════════════════════════════════════════
#  OFFICIAL REGULATORY INSTITUTIONS
# ═══════════════════════════════════════════════════════════════════════════

CBK = SourceConfig(
    source_id="cbk",
    name="Central Bank of Kenya",
    base_url="https://www.centralbank.go.ke",
    seed_urls=[
        "https://www.centralbank.go.ke/publications/",
        "https://www.centralbank.go.ke/monetary-policy/",
        "https://www.centralbank.go.ke/statistics/",
        "https://www.centralbank.go.ke/financial-stability/",
        "https://www.centralbank.go.ke/policy-procedures/",
        "https://www.centralbank.go.ke/national-payments-system/",
        "https://www.centralbank.go.ke/bank-supervision/",
        "https://www.centralbank.go.ke/rates/",
    ],
    institution_type="regulatory",
    financial_domain=["monetary_policy", "banking_supervision", "payment_systems",
                      "financial_stability", "exchange_rates", "interest_rates"],
    url_patterns=[r"\.pdf$", r"/publications/", r"/reports/", r"/statistics/"],
    url_exclude=[r"/career", r"/tender", r"/vacancies"],
)

NSE = SourceConfig(
    source_id="nse",
    name="Nairobi Securities Exchange",
    base_url="https://www.nse.co.ke",
    seed_urls=[
        "https://www.nse.co.ke/listed-companies/list.html",
        "https://www.nse.co.ke/market-statistics/",
        "https://www.nse.co.ke/regulatory-framework/",
        "https://www.nse.co.ke/products-services/",
        "https://www.nse.co.ke/inverstor-education/",
        "https://www.nse.co.ke/media-center/publications.html",
    ],
    institution_type="regulatory",
    financial_domain=["capital_markets", "equities", "bonds", "derivatives",
                      "market_data", "investor_education"],
    url_patterns=[r"\.pdf$", r"/publications/", r"/market-statistics/"],
    url_exclude=[r"/career", r"/tender"],
    requires_javascript=True,
    notes="NSE uses dynamic content; some pages need JS rendering.",
)

KRA = SourceConfig(
    source_id="kra",
    name="Kenya Revenue Authority",
    base_url="https://www.kra.go.ke",
    seed_urls=[
        "https://www.kra.go.ke/helping-tax-payers/new-to-tax/individual",
        "https://www.kra.go.ke/helping-tax-payers/new-to-tax/companies",
        "https://www.kra.go.ke/tax-policy",
        "https://www.kra.go.ke/news-center/public-notices",
        "https://www.kra.go.ke/helping-tax-payers/faqs",
        "https://kra.go.ke/individual/calculate-tax/calculating-tax/paye",
        "https://kra.go.ke/individual/calculate-tax/calculating-tax/turnover-tax",
        "https://kra.go.ke/en/business/companies-partnerships/compliance-requirements",
    ],
    institution_type="regulatory",
    financial_domain=["taxation", "income_tax", "vat", "customs", "excise",
                      "tax_compliance", "tax_policy"],
    url_patterns=[r"\.pdf$", r"/helping-tax-payers/", r"/tax-policy/", r"/downloads/"],
    url_exclude=[r"/career", r"/tender", r"/itax"],
    request_delay=3.0,
    notes="KRA has heavy JS. Prioritize static PDF guides and FAQ content.",
)

CMA = SourceConfig(
    source_id="cma",
    name="Capital Markets Authority",
    base_url="https://www.cma.or.ke",
    seed_urls=[
        "https://www.cma.or.ke/index.php/regulatory-framework",
        "https://www.cma.or.ke/index.php/investor-education",
        "https://www.cma.or.ke/index.php/research-publications",
        "https://www.cma.or.ke/index.php/quarterly-statistical-bulletin",
        "https://www.cma.or.ke/index.php/licensing",
    ],
    institution_type="regulatory",
    financial_domain=["capital_markets", "securities_regulation", "investor_protection",
                      "market_development"],
    url_patterns=[r"\.pdf$", r"/publications/", r"/regulatory-framework/"],
    url_exclude=[r"/career", r"/tender"],
)

KNBS = SourceConfig(
    source_id="knbs",
    name="Kenya National Bureau of Statistics",
    base_url="https://www.knbs.or.ke",
    seed_urls=[
        "https://www.knbs.or.ke/publications/",
        "https://www.knbs.or.ke/download/",
        "https://www.knbs.or.ke/visualizations/",
        "https://www.knbs.or.ke/category/economic-survey/",
        "https://www.knbs.or.ke/category/consumer-price-indices/",
        "https://www.knbs.or.ke/category/gross-domestic-product/",
    ],
    institution_type="regulatory",
    financial_domain=["economic_statistics", "gdp", "inflation", "cpi",
                      "population", "trade_statistics", "employment"],
    url_patterns=[r"\.pdf$", r"\.xlsx?$", r"/download/", r"/publications/"],
    url_exclude=[r"/career", r"/tender"],
    notes="KNBS publishes Excel datasets alongside PDFs. Both are valuable.",
)

SASRA = SourceConfig(
    source_id="sasra",
    name="SACCO Societies Regulatory Authority",
    base_url="https://www.sasra.go.ke",
    seed_urls=[
        "https://www.sasra.go.ke/publications/",
        "https://www.sasra.go.ke/download/",
        "https://www.sasra.go.ke/licensed-saccos/",
        "https://www.sasra.go.ke/regulations/",
        "https://www.sasra.go.ke/supervision-reports/",
    ],
    institution_type="regulatory",
    financial_domain=["sacco_regulation", "cooperative_banking", "sacco_supervision"],
    url_patterns=[r"\.pdf$", r"/publications/", r"/download/"],
    url_exclude=[r"/career", r"/tender"],
)

TREASURY = SourceConfig(
    source_id="treasury",
    name="National Treasury of Kenya",
    base_url="https://www.treasury.go.ke",
    seed_urls=[
        "https://www.treasury.go.ke/publications/",
        "https://www.treasury.go.ke/media-centre/",
        "https://www.treasury.go.ke/budget/",
        "https://www.treasury.go.ke/economy/",
        "https://www.treasury.go.ke/public-debt/",
        "https://www.treasury.go.ke/tax-policy/",
    ],
    institution_type="regulatory",
    financial_domain=["fiscal_policy", "budget", "public_debt", "economic_policy",
                      "public_finance"],
    url_patterns=[r"\.pdf$", r"/publications/", r"/budget/"],
    url_exclude=[r"/career", r"/tender", r"/procurement"],
)


# ═══════════════════════════════════════════════════════════════════════════
#  FINANCIAL PLATFORMS
# ═══════════════════════════════════════════════════════════════════════════

MPESA = SourceConfig(
    source_id="mpesa",
    name="M-Pesa / Safaricom Developer",
    base_url="https://developer.safaricom.co.ke",
    seed_urls=[
        "https://developer.safaricom.co.ke/APIs",
        "https://developer.safaricom.co.ke/Documentation",
        "https://www.safaricom.co.ke/personal/m-pesa",
        "https://www.safaricom.co.ke/business/sme/m-pesa-payment-solutions",
    ],
    institution_type="platform",
    financial_domain=["mobile_money", "digital_payments", "fintech", "api_documentation"],
    url_patterns=[r"\.pdf$", r"/APIs/", r"/Documentation/", r"/m-pesa/"],
    url_exclude=[r"/career", r"/shop"],
    html_enabled=True,
    pdf_enabled=True,
    notes="Developer docs are mostly HTML. Consumer M-Pesa pages are HTML + PDF brochures.",
)


# ── Commercial Banks ──────────────────────────────────────────────────────

def _bank_config(source_id: str, name: str, base_url: str,
                 seed_urls: List[str], **kwargs) -> SourceConfig:
    """Factory for bank source configs with shared defaults."""
    return SourceConfig(
        source_id=source_id,
        name=name,
        base_url=base_url,
        seed_urls=seed_urls,
        institution_type="bank",
        financial_domain=["retail_banking", "corporate_banking", "loans",
                          "savings", "insurance", "investment"],
        url_patterns=[r"\.pdf$", r"/products/", r"/personal/", r"/business/"],
        url_exclude=[r"/career", r"/tender", r"/login", r"/register", r"/apply"],
        max_depth=2,
        **kwargs,
    )


EQUITY = _bank_config(
    "equity", "Equity Bank", "https://equitygroupholdings.com",
    [
        "https://equitygroupholdings.com/ke/personal-banking",
        "https://equitygroupholdings.com/ke/business-banking",
        "https://equitygroupholdings.com/ke/borrow",
        "https://equitygroupholdings.com/ke/save",
        "https://equitygroupholdings.com/ke/invest",
        "https://equitygroupholdings.com/ke/investor-relations/",
    ],
)

KCB = _bank_config(
    "kcb", "KCB Bank", "https://ke.kcbgroup.com",
    [
        "https://ke.kcbgroup.com/personal-banking",
        "https://ke.kcbgroup.com/business-banking",
        "https://ke.kcbgroup.com/corporate-banking",
        "https://ke.kcbgroup.com/investor-relations/",
    ],
)

COOP = _bank_config(
    "coop", "Co-operative Bank", "https://www.co-opbank.co.ke",
    [
        "https://www.co-opbank.co.ke/personal",
        "https://www.co-opbank.co.ke/business",
        "https://www.co-opbank.co.ke/corporate",
        "https://www.co-opbank.co.ke/investor-relations/",
    ],
)

ABSA = _bank_config(
    "absa", "Absa Bank Kenya", "https://www.absabank.co.ke",
    [
        "https://www.absabank.co.ke/personal/",
        "https://www.absabank.co.ke/business/",
        "https://www.absabank.co.ke/corporate/",
        "https://www.absabank.co.ke/investor-relations/",
    ],
)

NCBA = _bank_config(
    "ncba", "NCBA Bank", "https://ke.ncbagroup.com",
    [
        "https://ke.ncbagroup.com/personal/",
        "https://ke.ncbagroup.com/business/",
        "https://ke.ncbagroup.com/corporate-banking/",
        "https://ke.ncbagroup.com/investor-relations/",
    ],
)

STANBIC = _bank_config(
    "stanbic", "Stanbic Bank Kenya", "https://www.stanbicbank.co.ke",
    [
        "https://www.stanbicbank.co.ke/kenya/personal/",
        "https://www.stanbicbank.co.ke/kenya/business/",
        "https://www.stanbicbank.co.ke/kenya/corporate-and-investment/",
    ],
)

IM_BANK = _bank_config(
    "im", "I&M Bank", "https://www.imbank.com",
    [
        "https://www.imbank.com/personal-banking/",
        "https://www.imbank.com/business-banking/",
        "https://www.imbank.com/corporate-banking/",
        "https://www.imbank.com/investor-relations/",
    ],
)

FAMILY = _bank_config(
    "family", "Family Bank", "https://familybank.co.ke",
    [
        "https://familybank.co.ke/personal/",
        "https://familybank.co.ke/business/",
        "https://familybank.co.ke/corporate/",
        "https://familybank.co.ke/investor-relations/",
    ],
)


# ── Investment Firms ──────────────────────────────────────────────────────

def _investment_config(source_id: str, name: str, base_url: str,
                       seed_urls: List[str], **kwargs) -> SourceConfig:
    return SourceConfig(
        source_id=source_id,
        name=name,
        base_url=base_url,
        seed_urls=seed_urls,
        institution_type="investment",
        financial_domain=["asset_management", "unit_trusts", "wealth_management",
                          "insurance", "pensions", "real_estate_investment"],
        url_patterns=[r"\.pdf$", r"/products/", r"/funds/", r"/invest/"],
        url_exclude=[r"/career", r"/login", r"/apply", r"/portal"],
        max_depth=2,
        **kwargs,
    )


CYTONN = _investment_config(
    "cytonn", "Cytonn Investments", "https://www.cytonn.com",
    [
        "https://www.cytonn.com/investments",
        "https://www.cytonn.com/research",
        "https://www.cytonn.com/topicals",
        "https://www.cytonn.com/downloads",
    ],
)

BRITAM = _investment_config(
    "britam", "Britam Holdings", "https://www.britam.com",
    [
        "https://www.britam.com/investor-relations/",
        "https://www.britam.com/insurance/",
        "https://www.britam.com/asset-management/",
    ],
)

CIC = _investment_config(
    "cic", "CIC Insurance Group", "https://www.cic.co.ke",
    [
        "https://www.cic.co.ke/insurance/",
        "https://www.cic.co.ke/investments/",
        "https://www.cic.co.ke/investor-relations/",
    ],
)

ICEA_LION = _investment_config(
    "icea_lion", "ICEA LION Group", "https://www.icealion.com",
    [
        "https://www.icealion.com/insurance/",
        "https://www.icealion.com/asset-management/",
        "https://www.icealion.com/investor-relations/",
    ],
)

OLD_MUTUAL = _investment_config(
    "old_mutual", "Old Mutual Kenya", "https://www.oldmutual.co.ke",
    [
        "https://www.oldmutual.co.ke/personal/",
        "https://www.oldmutual.co.ke/corporate/",
        "https://www.oldmutual.co.ke/investor-relations/",
    ],
)

MADISON = _investment_config(
    "madison", "Madison Group", "https://www.madison.co.ke",
    [
        "https://www.madison.co.ke/insurance/",
        "https://www.madison.co.ke/investments/",
    ],
)


# ── SACCO Publications ───────────────────────────────────────────────────

SACCOS = SourceConfig(
    source_id="saccos",
    name="SACCO Publications (Aggregated)",
    base_url="https://www.sasra.go.ke",
    seed_urls=[
        "https://www.sasra.go.ke/publications/",
        "https://www.sasra.go.ke/licensed-saccos/",
        # Major DT-SACCOs with public product pages
        "https://www.stima-sacco.co.ke/products/",
        "https://www.kikiyu.coop/products/",
        "https://www.unaitas.com/products/",
        "https://www.mwalimu-national.coop/products/",
    ],
    institution_type="sacco",
    financial_domain=["sacco_products", "savings", "loans", "cooperative_banking"],
    url_patterns=[r"\.pdf$", r"/products/", r"/publications/"],
    url_exclude=[r"/career", r"/login", r"/portal"],
    max_depth=1,
    notes="SACCOs have varying web quality. Focus on SASRA aggregate data + top DT-SACCOs.",
)


# ═══════════════════════════════════════════════════════════════════════════
#  ADDITIONAL MOBILE MONEY PLATFORMS (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

AIRTEL_MONEY = SourceConfig(
    source_id="airtel_money",
    name="Airtel Money Kenya",
    base_url="https://www.airtel.co.ke",
    seed_urls=[
        "https://www.airtel.co.ke/airtel-money",
        "https://www.airtel.co.ke/airtel-money/send-money",
        "https://www.airtel.co.ke/airtel-money/pay-bills",
        "https://www.airtel.co.ke/airtel-money/buy-goods",
        "https://www.airtel.co.ke/airtel-money/save-borrow",
    ],
    institution_type="platform",
    financial_domain=["mobile_money", "digital_payments", "savings", "loans"],
    url_patterns=[r"\.pdf$", r"/airtel-money/"],
    url_exclude=[r"/career", r"/shop", r"/airtime"],
    max_depth=2,
    request_delay=3.0,
    notes="Airtel Money product pages, mostly HTML.",
)

TKASH = SourceConfig(
    source_id="tkash",
    name="Telkom T-Kash",
    base_url="https://www.telkom.co.ke",
    seed_urls=[
        "https://www.telkom.co.ke/t-kash",
        "https://www.telkom.co.ke/t-kash/send-money",
        "https://www.telkom.co.ke/t-kash/pay-bills",
    ],
    institution_type="platform",
    financial_domain=["mobile_money", "digital_payments"],
    url_patterns=[r"\.pdf$", r"/t-kash/"],
    url_exclude=[r"/career", r"/shop"],
    max_depth=2,
    request_delay=3.0,
    notes="Telkom T-Kash. Smaller product range than M-Pesa/Airtel.",
)


# ═══════════════════════════════════════════════════════════════════════════
#  ADDITIONAL BANKS (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

DTB = _bank_config(
    "dtb", "Diamond Trust Bank", "https://www.dtbafrica.com",
    [
        "https://www.dtbafrica.com/kenya/personal-banking/",
        "https://www.dtbafrica.com/kenya/business-banking/",
        "https://www.dtbafrica.com/kenya/corporate-banking/",
        "https://www.dtbafrica.com/investor-relations/",
    ],
)

PRIME = _bank_config(
    "prime", "Prime Bank Kenya", "https://www.primebank.co.ke",
    [
        "https://www.primebank.co.ke/personal-banking/",
        "https://www.primebank.co.ke/business-banking/",
        "https://www.primebank.co.ke/corporate-banking/",
        "https://www.primebank.co.ke/investor-relations/",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
#  ADDITIONAL INVESTMENT / INSURANCE (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

SANLAM = _investment_config(
    "sanlam", "Sanlam Kenya", "https://www.sanlam.co.ke",
    [
        "https://www.sanlam.co.ke/personal/",
        "https://www.sanlam.co.ke/investments/",
        "https://www.sanlam.co.ke/insurance/",
        "https://www.sanlam.co.ke/corporate/",
    ],
)

GENGHIS = _investment_config(
    "genghis", "Genghis Capital", "https://www.genghis-capital.com",
    [
        "https://www.genghis-capital.com/research/",
        "https://www.genghis-capital.com/services/",
        "https://www.genghis-capital.com/resources/",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
#  STOCKBROKERS / INVESTMENT BANKS (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

def _stockbroker_config(source_id: str, name: str, base_url: str,
                        seed_urls: List[str], **kwargs) -> SourceConfig:
    """Factory for stockbroker/investment bank source configs."""
    return SourceConfig(
        source_id=source_id,
        name=name,
        base_url=base_url,
        seed_urls=seed_urls,
        institution_type="stockbroker",
        financial_domain=["equities", "fixed_income", "research",
                          "portfolio_management", "capital_markets"],
        url_patterns=[r"\.pdf$", r"/research/", r"/services/", r"/resources/"],
        url_exclude=[r"/career", r"/login", r"/portal"],
        max_depth=2,
        **kwargs,
    )


FAIDA = _stockbroker_config(
    "faida", "Faida Investment Bank", "https://www.faidainvestment.com",
    [
        "https://www.faidainvestment.com/research/",
        "https://www.faidainvestment.com/services/",
        "https://www.faidainvestment.com/resources/",
    ],
)

DYER_BLAIR = _stockbroker_config(
    "dyer_blair", "Dyer & Blair Investment Bank", "https://www.dyerandblair.com",
    [
        "https://www.dyerandblair.com/research/",
        "https://www.dyerandblair.com/services/",
        "https://www.dyerandblair.com/investor-education/",
    ],
)

SIB = _stockbroker_config(
    "sib", "Standard Investment Bank", "https://www.sib.co.ke",
    [
        "https://www.sib.co.ke/research/",
        "https://www.sib.co.ke/services/",
        "https://www.sib.co.ke/publications/",
        "https://www.sib.co.ke/weekly-brief/",
    ],
    notes="SIB publishes weekly market briefs and research reports.",
)


# ═══════════════════════════════════════════════════════════════════════════
#  INDIVIDUAL SACCOs (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

def _sacco_config(source_id: str, name: str, base_url: str,
                  seed_urls: List[str], **kwargs) -> SourceConfig:
    """Factory for individual SACCO source configs."""
    return SourceConfig(
        source_id=source_id,
        name=name,
        base_url=base_url,
        seed_urls=seed_urls,
        institution_type="sacco",
        financial_domain=["sacco_products", "savings", "loans",
                          "cooperative_banking"],
        url_patterns=[r"\.pdf$", r"/products/", r"/services/", r"/loans/",
                      r"/savings/"],
        url_exclude=[r"/career", r"/login", r"/portal", r"/member"],
        max_depth=1,
        **kwargs,
    )


MWALIMU_SACCO = _sacco_config(
    "mwalimu_sacco", "Mwalimu National SACCO",
    "https://www.mwalimu-national.coop",
    [
        "https://www.mwalimu-national.coop/products/",
        "https://www.mwalimu-national.coop/services/",
        "https://www.mwalimu-national.coop/loans/",
        "https://www.mwalimu-national.coop/savings/",
    ],
)

STIMA_SACCO = _sacco_config(
    "stima_sacco", "Stima DT SACCO",
    "https://www.stima-sacco.co.ke",
    [
        "https://www.stima-sacco.co.ke/products/",
        "https://www.stima-sacco.co.ke/loans/",
        "https://www.stima-sacco.co.ke/savings/",
    ],
)

SAFARICOM_SACCO = _sacco_config(
    "safaricom_sacco", "Safaricom Investment SACCO",
    "https://www.safaboreftsacco.co.ke",
    [
        "https://www.safaboreftsacco.co.ke/products/",
        "https://www.safaboreftsacco.co.ke/services/",
    ],
    notes="Safaricom staff SACCO. Limited public info.",
)

HARAMBEE_SACCO = _sacco_config(
    "harambee_sacco", "Harambee SACCO",
    "https://www.harambeesacco.com",
    [
        "https://www.harambeesacco.com/products/",
        "https://www.harambeesacco.com/services/",
    ],
)

UNAITAS_SACCO = _sacco_config(
    "unaitas_sacco", "Unaitas SACCO",
    "https://www.unaitas.com",
    [
        "https://www.unaitas.com/products/",
        "https://www.unaitas.com/savings/",
        "https://www.unaitas.com/loans/",
    ],
)

POLICE_SACCO = _sacco_config(
    "police_sacco", "Kenya Police SACCO",
    "https://www.kenyapolicesacco.com",
    [
        "https://www.kenyapolicesacco.com/products/",
        "https://www.kenyapolicesacco.com/services/",
    ],
)

AFYA_SACCO = _sacco_config(
    "afya_sacco", "Afya SACCO",
    "https://www.afyasacco.com",
    [
        "https://www.afyasacco.com/products/",
        "https://www.afyasacco.com/services/",
    ],
)

UN_SACCO = _sacco_config(
    "un_sacco", "United Nations SACCO",
    "https://www.unsacco.org",
    [
        "https://www.unsacco.org/products/",
        "https://www.unsacco.org/services/",
    ],
)


# ═══════════════════════════════════════════════════════════════════════════
#  NEWS / MEDIA (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

def _news_config(source_id: str, name: str, base_url: str,
                 seed_urls: List[str], **kwargs) -> SourceConfig:
    """Factory for financial news source configs."""
    return SourceConfig(
        source_id=source_id,
        name=name,
        base_url=base_url,
        seed_urls=seed_urls,
        institution_type="media",
        financial_domain=["financial_news", "market_analysis",
                          "economic_commentary"],
        url_patterns=[r"/\d{4}/\d{2}/", r"/business/", r"/money/", r"/markets/"],
        url_exclude=[r"/sport", r"/entertainment", r"/lifestyle",
                     r"/login", r"/subscribe", r"/premium"],
        html_enabled=True,
        pdf_enabled=False,
        max_depth=2,
        max_documents=200,
        request_delay=3.0,
        requires_javascript=True,
        **kwargs,
    )


BUSINESS_DAILY = _news_config(
    "business_daily", "Business Daily",
    "https://www.businessdailyafrica.com",
    [
        "https://www.businessdailyafrica.com/bd/markets",
        "https://www.businessdailyafrica.com/bd/economy",
        "https://www.businessdailyafrica.com/bd/corporate",
        "https://www.businessdailyafrica.com/bd/opinion",
    ],
    notes="Nation Media Group. Premium content behind paywall; scrape free articles.",
)

NATION_BUSINESS = _news_config(
    "nation_business", "Nation Business",
    "https://nation.africa",
    [
        "https://nation.africa/kenya/business",
        "https://nation.africa/kenya/business/economic-growth",
        "https://nation.africa/kenya/business/corporate",
    ],
    notes="Nation Africa business section. Some content gated.",
)

STANDARD_BUSINESS = _news_config(
    "standard_business", "The Standard Business",
    "https://www.standardmedia.co.ke",
    [
        "https://www.standardmedia.co.ke/business",
        "https://www.standardmedia.co.ke/business/money",
        "https://www.standardmedia.co.ke/business/markets",
    ],
    notes="Standard Group. Less paywall friction than BD/Nation.",
)


# ═══════════════════════════════════════════════════════════════════════════
#  FINANCIAL EDUCATION (Phase 3)
# ═══════════════════════════════════════════════════════════════════════════

def _education_config(source_id: str, name: str, base_url: str,
                      seed_urls: List[str], **kwargs) -> SourceConfig:
    """Factory for financial education source configs."""
    return SourceConfig(
        source_id=source_id,
        name=name,
        base_url=base_url,
        seed_urls=seed_urls,
        institution_type="education",
        financial_domain=["financial_literacy", "personal_finance",
                          "investing_education", "budgeting"],
        url_patterns=[r"/blog/", r"/articles/", r"/resources/", r"/\d{4}/"],
        url_exclude=[r"/career", r"/login", r"/shop", r"/cart"],
        html_enabled=True,
        pdf_enabled=True,
        max_depth=2,
        max_documents=150,
        request_delay=3.0,
        **kwargs,
    )


MASHAURI = _education_config(
    "mashauri", "Mashauri",
    "https://mashauri.com",
    [
        "https://mashauri.com/blog/",
        "https://mashauri.com/resources/",
    ],
    notes="Kenyan personal finance blog. Beginner-focused content.",
)

CENTONOMY = _education_config(
    "centonomy", "Centonomy",
    "https://www.centonomy.com",
    [
        "https://www.centonomy.com/blog/",
        "https://www.centonomy.com/resources/",
        "https://www.centonomy.com/programs/",
    ],
    notes="Financial training company. Founded by Waceke Nduati.",
)

MALKIA = _education_config(
    "malkia", "Malkia Investments",
    "https://www.malkiainvestments.com",
    [
        "https://www.malkiainvestments.com/blog/",
    ],
    notes="Women-focused financial education. SME and personal finance.",
)

FIN_INCORRECT = SourceConfig(
    source_id="fin_incorrect",
    name="Financially Incorrect Podcast",
    base_url="https://www.youtube.com",
    seed_urls=[
        "https://www.youtube.com/@FinanciallyIncorrectKE",
    ],
    institution_type="education",
    financial_domain=["financial_literacy", "investing_education",
                      "personal_finance", "kenyan_markets"],
    html_enabled=False,
    pdf_enabled=False,
    max_documents=50,
    request_delay=5.0,
    notes="YouTube podcast. Extract via youtube-transcript-api.",
)

LYNN_NGUGI = SourceConfig(
    source_id="lynn_ngugi",
    name="Lynn Ngugi Talks",
    base_url="https://www.youtube.com",
    seed_urls=[
        "https://www.youtube.com/@LynnNgugiTalks",
    ],
    institution_type="education",
    financial_domain=["financial_literacy", "personal_finance",
                      "entrepreneurship"],
    html_enabled=False,
    pdf_enabled=False,
    max_documents=50,
    request_delay=5.0,
    notes="YouTube channel. Money and success stories. Extract transcripts.",
)

SUSAN_WONG = _education_config(
    "susan_wong", "Susan Wong Finance",
    "https://www.susanwong.co.ke",
    [
        "https://www.susanwong.co.ke/blog/",
    ],
    notes="Personal finance blogger/educator focused on Kenyan market.",
)

KIFAM = _education_config(
    "kifam", "KIFAM",
    "https://www.kifam.co.ke",
    [
        "https://www.kifam.co.ke/resources/",
        "https://www.kifam.co.ke/publications/",
    ],
    notes="Kenya Institute of Financial Analysis & Management.",
)

ABOJANI = _education_config(
    "abojani", "Abojani Investments",
    "https://www.abojaniinvestments.com",
    [
        "https://www.abojaniinvestments.com/blog/",
        "https://www.abojaniinvestments.com/resources/",
    ],
    notes="Kenyan investment education and advisory.",
)

KWFT = _education_config(
    "kwft", "Kenya Women Finance Trust (KWFT)",
    "https://www.kwftbank.com",
    [
        "https://www.kwftbank.com/personal-banking/",
        "https://www.kwftbank.com/sme-banking/",
        "https://www.kwftbank.com/financial-education/",
    ],
    notes="Microfinance institution. Women-focused financial products.",
)


# ═══════════════════════════════════════════════════════════════════════════
#  REGISTRY
# ═══════════════════════════════════════════════════════════════════════════

SOURCES: dict[str, SourceConfig] = {
    # ── Regulatory ──────────────────────────────────────────────────────
    "cbk": CBK,
    "nse": NSE,
    "kra": KRA,
    "cma": CMA,
    "knbs": KNBS,
    "sasra": SASRA,
    "treasury": TREASURY,
    # ── Platforms (Mobile Money) ────────────────────────────────────────
    "mpesa": MPESA,
    "airtel_money": AIRTEL_MONEY,
    "tkash": TKASH,
    # ── Banks ───────────────────────────────────────────────────────────
    "equity": EQUITY,
    "kcb": KCB,
    "coop": COOP,
    "absa": ABSA,
    "ncba": NCBA,
    "stanbic": STANBIC,
    "im": IM_BANK,
    "family": FAMILY,
    "dtb": DTB,
    "prime": PRIME,
    # ── Investment / Insurance ──────────────────────────────────────────
    "cytonn": CYTONN,
    "britam": BRITAM,
    "cic": CIC,
    "icea_lion": ICEA_LION,
    "old_mutual": OLD_MUTUAL,
    "madison": MADISON,
    "sanlam": SANLAM,
    "genghis": GENGHIS,
    # ── Stockbrokers ────────────────────────────────────────────────────
    "faida": FAIDA,
    "dyer_blair": DYER_BLAIR,
    "sib": SIB,
    # ── SACCOs ──────────────────────────────────────────────────────────
    "saccos": SACCOS,
    "mwalimu_sacco": MWALIMU_SACCO,
    "stima_sacco": STIMA_SACCO,
    "safaricom_sacco": SAFARICOM_SACCO,
    "harambee_sacco": HARAMBEE_SACCO,
    "unaitas_sacco": UNAITAS_SACCO,
    "police_sacco": POLICE_SACCO,
    "afya_sacco": AFYA_SACCO,
    "un_sacco": UN_SACCO,
    # ── News / Media ────────────────────────────────────────────────────
    "business_daily": BUSINESS_DAILY,
    "nation_business": NATION_BUSINESS,
    "standard_business": STANDARD_BUSINESS,
    # ── Financial Education ─────────────────────────────────────────────
    "mashauri": MASHAURI,
    "centonomy": CENTONOMY,
    "malkia": MALKIA,
    "fin_incorrect": FIN_INCORRECT,
    "lynn_ngugi": LYNN_NGUGI,
    "susan_wong": SUSAN_WONG,
    "kifam": KIFAM,
    "abojani": ABOJANI,
    "kwft": KWFT,
}

# Convenience groupings
REGULATORY_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "regulatory"}
BANK_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "bank"}
INVESTMENT_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "investment"}
PLATFORM_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "platform"}
SACCO_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "sacco"}
STOCKBROKER_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "stockbroker"}
MEDIA_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "media"}
EDUCATION_SOURCES = {k: v for k, v in SOURCES.items() if v.institution_type == "education"}
