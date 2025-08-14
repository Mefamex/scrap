"""
scrap paket başlangıcı.
BrowserManager tekil (singleton) erişimi sağlar.
"""

from __future__ import annotations
import threading
import logging
from typing import Optional, Any, Dict, Callable
from src.settings import settings

# Basit logging ayarı (uygulama tarafında tekrar yapılandırılabilir)
logger = logging.getLogger("scrap")
if not logger.handlers: logging.basicConfig( level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s" )

_lock = threading.RLock()
_browser_manager: Optional["BrowserManager"] = None

class BrowserManager:
    """
    Tarayıcı yaşam döngüsünü yöneten basit iskelet sınıf.
    Gerçek webdriver / playwright nesnelerini entegre etmek için genişlet.
    """
    def __init__(self, **options: Any) -> None:
        self._options = options
        self._started = False
        self._driver = None  # Gerçek sürücü (ör: selenium webdriver / playwright browser)
        logger.debug("BrowserManager oluşturuldu: %r", options)

    def start(self) -> None:
        if self._started:
            logger.debug("BrowserManager zaten başlatılmış.")
            return
        # Burada gerçek başlatma kodu (örn. Selenium driver init) yer alacak.
        # self._driver = webdriver.Chrome(...)
        self._started = True
        logger.info("BrowserManager başlatıldı.")

    def get_driver(self) -> Any:
        if not self._started:  self.start()
        return self._driver

    def execute(self, func: Callable[[Any], Any]) -> Any:
        """
        Sürücü ile kapalı fonksiyon çalıştır.
        """
        driver = self.get_driver()
        if driver is None: raise RuntimeError("Driver henüz yapılandırılmadı.")
        return func(driver)

    def shutdown(self) -> None:
        if not self._started:
            return
        try:
            # Örnek: self._driver.quit()
            pass
        finally:
            self._driver = None
            self._started = False
            logger.info("BrowserManager kapatıldı.")

def init_browser_manager(force: bool = False, **options: Any) -> BrowserManager:
    """
    BrowserManager örneğini oluşturur veya mevcut olanı döner.
    force=True ise mevcut örnek kapatılıp yeniden yaratılır.
    """
    global _browser_manager
    with _lock:
        if _browser_manager and not force:
            return _browser_manager
        if _browser_manager and force:
            try:
                _browser_manager.shutdown()
            except Exception as exc:
                logger.warning("Eski BrowserManager kapatma hatası: %s", exc)
        _browser_manager = BrowserManager(**options)
        return _browser_manager

def get_browser_manager() -> BrowserManager:
    """
    Hazır (veya lazy init ile) BrowserManager döner.
    """
    bm = _browser_manager
    if bm is None: bm = init_browser_manager()
    return bm

def shutdown_browser_manager() -> None:
    with _lock:
        if _browser_manager:
            _browser_manager.shutdown()

__all__ = [
    "BrowserManager",
    "init_browser_manager",
    "get_browser_manager",
    "shutdown_browser_manager",
]