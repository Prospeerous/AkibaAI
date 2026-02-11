"""
Scraper registry — maps source_id to scraper class.

Lazy-imports to avoid loading all scrapers when only one is needed.
"""

from typing import Dict, Optional

from src.config.sources import SOURCES
from src.config.settings import Settings
from src.utils.http_client import RateLimitedClient


def _import_scraper(source_id: str):
    """Lazy-import the correct scraper class for a source_id."""
    if source_id == "cbk":
        from src.scrapers.cbk import CBKScraper
        return CBKScraper
    elif source_id == "nse":
        from src.scrapers.nse import NSEScraper
        return NSEScraper
    elif source_id == "kra":
        from src.scrapers.kra import KRAScraper
        return KRAScraper
    elif source_id == "cma":
        from src.scrapers.cma import CMAScraper
        return CMAScraper
    elif source_id == "knbs":
        from src.scrapers.knbs import KNBSScraper
        return KNBSScraper
    elif source_id == "sasra":
        from src.scrapers.sasra import SASRAScraper
        return SASRAScraper
    elif source_id == "treasury":
        from src.scrapers.treasury import TreasuryScraper
        return TreasuryScraper
    elif source_id == "mpesa":
        from src.scrapers.mpesa import MPesaScraper
        return MPesaScraper
    elif source_id in ("equity", "kcb", "coop", "absa", "ncba",
                       "stanbic", "im", "family", "dtb", "prime"):
        from src.scrapers.banks import BankScraper
        return BankScraper
    elif source_id in ("cytonn", "britam", "cic", "icea_lion",
                       "old_mutual", "madison", "sanlam", "genghis"):
        from src.scrapers.investment import InvestmentScraper
        return InvestmentScraper
    elif source_id in ("faida", "dyer_blair", "sib"):
        from src.scrapers.stockbroker import StockbrokerScraper
        return StockbrokerScraper
    elif source_id in ("saccos", "mwalimu_sacco", "stima_sacco",
                       "safaricom_sacco", "harambee_sacco", "unaitas_sacco",
                       "police_sacco", "afya_sacco", "un_sacco"):
        from src.scrapers.saccos import SACCOScraper
        return SACCOScraper
    elif source_id in ("airtel_money", "tkash"):
        from src.scrapers.airtel_money import AirtelMoneyScraper
        return AirtelMoneyScraper
    elif source_id in ("business_daily", "nation_business", "standard_business"):
        from src.scrapers.news_scraper import NewsScraper
        return NewsScraper
    elif source_id in ("mashauri", "centonomy", "malkia", "susan_wong",
                       "kifam", "abojani", "kwft"):
        from src.scrapers.education_scraper import EducationScraper
        return EducationScraper
    elif source_id in ("fin_incorrect", "lynn_ngugi"):
        from src.scrapers.podcast_scraper import PodcastScraper
        return PodcastScraper
    else:
        raise ValueError(f"Unknown source_id: {source_id}")


def get_scraper(source_id: str,
                settings: Optional[Settings] = None,
                http_client: Optional[RateLimitedClient] = None):
    """
    Factory: instantiate the correct scraper for a given source_id.

    Args:
        source_id: Key from SOURCES registry (e.g. "cbk", "equity")
        settings: Override default settings
        http_client: Share an HTTP client across scrapers

    Returns:
        Initialized scraper instance
    """
    if source_id not in SOURCES:
        raise ValueError(
            f"Unknown source '{source_id}'. "
            f"Available: {', '.join(sorted(SOURCES.keys()))}"
        )

    config = SOURCES[source_id]
    scraper_cls = _import_scraper(source_id)
    return scraper_cls(
        source_config=config,
        settings=settings,
        http_client=http_client,
    )


def get_scraper_registry() -> Dict[str, str]:
    """Build a mapping of source_id → scraper class name."""
    registry = {}
    for sid in SOURCES:
        try:
            registry[sid] = _import_scraper(sid).__name__
        except Exception:
            registry[sid] = "Unknown"
    return registry


SCRAPER_REGISTRY = get_scraper_registry
