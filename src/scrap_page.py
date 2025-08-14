import logging
from typing import Optional
import requests
from bs4 import BeautifulSoup

from src.settings import settings
from src.browser_manager import browser_manager  # DÜZELTİLDİ (eskiden: from src import get_browser_manager)

logger = logging.getLogger("scrap.scrap_page")

def _get_or_create_driver():
    """
    Mevcut Selenium driver'ı döner.
    (sync fonksiyon içinde await edemeyeceğimiz için burada initialize etmiyoruz;
    main zaten initialize_browser çağırıyor. Hazır değilse None döner.)
    """
    if not getattr(browser_manager, "is_initialized", False):
        logger.debug("Browser manager henüz initialize edilmemiş; requests fallback kullanılacak.")
        return None
    return getattr(browser_manager, "driver", None)

def _fetch_with_browser(driver, url: str, timeout: int, headers: dict) -> Optional[str]:
    try:
        if not driver:
            return None
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        return getattr(driver, "page_source", "")
    except Exception as e:
        logger.warning("Selenium fetch hatası, fallback requests: %s", e)
        return None

def ensure_browser(use_browser: bool = True):
    """
    Browser kullanımı isteniyorsa hazır (initialize edilmiş) Selenium driver döner.
    Sync bağlamda async initialize_browser çağrılamaz; hazır değilse None.
    """
    if not use_browser:  return None
    if not getattr(browser_manager, "is_initialized", False):
        logger.debug("Browser henüz initialize edilmemiş; driver None dönecek.")
        return None
    drv = getattr(browser_manager, "driver", None)
    if drv is None: logger.debug("Browser manager var fakat driver nesnesi yok.")
    return drv

def open_page(url: str, *, timeout: int, headers: dict) -> Optional[str]:
    """
    Mevcut driver ile sayfayı açıp HTML döner; driver yoksa None.
    """
    driver = ensure_browser(use_browser=True)
    if not driver:
        return None
    return _fetch_with_browser(driver, url, timeout, headers)


def scrap_all_pages( url: str, *, timeout: int = 20, encoding: Optional[str] = None, use_browser: bool = True ) -> str:
    """
    Sayfadaki görünür metni çıkarır.
    use_browser=True ve aktif Selenium driver varsa önce onu dener, aksi halde requests.
    """
    ua = settings.browser_config.user_agent or "Mozilla/5.0"
    headers = {"User-Agent": ua}

    html = None
    if use_browser:
        # ensure_browser + open_page ile dene
        html = open_page(url, timeout=timeout, headers=headers)

    if html is None:
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        if encoding:  resp.encoding = encoding
        html = resp.text

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]): tag.decompose()

    text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln and not all(ch in "-_=*" for ch in ln)]

    cleaned = []
    for ln in lines:
        collapsed = " ".join(ln.split())
        if collapsed:
            cleaned.append(collapsed)

    return "\n".join(cleaned)

def fetch_raw_html(url: str, *, timeout: int = 20, encoding: Optional[str] = None, use_browser: bool = True) -> str:
    """Ham HTML döner (temizleme yapmaz)."""
    ua = settings.browser_config.user_agent or "Mozilla/5.0"
    headers = {"User-Agent": ua}
    html = None
    if use_browser:
        html = open_page(url, timeout=timeout, headers=headers)
    if html is None:
        resp = requests.get(url, timeout=timeout, headers=headers)
        resp.raise_for_status()
        if encoding: resp.encoding = encoding
        html = resp.text
    return html

def scrape_info_items(
    url: str,
    *,
    selector: str = ".info-content-column__item",
    timeout: int = 20,
    encoding: Optional[str] = None,
    use_browser: bool = True,
    include_html: bool = False,
) -> list[dict]:
    """
    Belirtilen CSS seçiciye göre öğeleri kazır.

    Dönen liste eleman formatı:
        {"index": int, "text": str, "html": str (opsiyonel) }
    """
    try:
        html = fetch_raw_html(url, timeout=timeout, encoding=encoding, use_browser=use_browser)
    except Exception as e:
        logger.error("HTML alınamadı: %s", e)
        return []

    soup = BeautifulSoup(html, "html.parser")
    elements = soup.select(selector)
    results = []
    for i, el in enumerate(elements):
        text = " ".join(el.get_text(separator=" ").split())
        item = {"index": i, "text": text}
        if include_html:
            item["html"] = str(el)
        results.append(item)
    return results

__all__ = [
    # mevcut dışa aktarılabilir fonksiyonlar
    "scrap_all_pages",
    "fetch_raw_html",
    "scrape_info_items",
]