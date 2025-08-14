import os, asyncio, time, hashlib
from datetime import datetime
from typing import List, Set

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
)

from src.settings import settings
from src.browser_manager import get_browser_manager, BrowserManager

# ================== KONSTLAR ==================
TARGET_URL = "https://partner.tgoyemek.com/meal/245018/order/list"
DETAILS_KEYWORD = "order/list/details"
CARD_SELECTOR = ".order-card"

DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
SAVE_DIR = os.path.join(DESKTOP_DIR, "saveAl")
os.makedirs(SAVE_DIR, exist_ok=True)

# ================== DURUM =====================
browser_manager: BrowserManager = get_browser_manager()
_clicked_cards: Set[str] = set()
_processed_detail_urls: Set[str] = set()
_processed_handles: Set[str] = set()
_base_handle: str | None = None

# ================== YARDIMCI ==================
def _hash(txt: str) -> str:
    return hashlib.sha256(txt.encode("utf-8", "ignore")).hexdigest()[:16]

def _capture_dom_outer_html(driver) -> str:
    try:
        driver.execute_cdp_cmd("DOM.enable", {})
        root = driver.execute_cdp_cmd("DOM.getDocument", {"depth": 0})
        node_id = root["root"]["nodeId"]
        return driver.execute_cdp_cmd("DOM.getOuterHTML", {"nodeId": node_id}).get("outerHTML", "")
    except Exception: return driver.page_source or ""

def _save_html_snapshot(driver, prefix: str) -> str:
    html_source = _capture_dom_outer_html(driver)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    page_title = (driver.title or "page").replace(" ", "_").replace("/", "_").replace("\\", "_")
    path = os.path.join(SAVE_DIR, f"{ts}_{prefix}_{page_title}.html")
    try:
        with open(path, "w", encoding="utf-8") as f: f.write(html_source)
        print(f"💾 Kaydedildi: {path}")
    except Exception as e: print(f"Snapshot kaydedilemedi: {e}")
    return path

def _click_new_order_cards(driver) -> int:
    try:
        cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)
    except Exception:
        return 0
    clicked = 0
    for el in cards:
        try:
            txt = el.text.strip()
            if not txt:  continue
            key = _hash(f"{driver.current_url}|{txt}")
            if key in _clicked_cards:  continue
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
            _clicked_cards.add(key)
            clicked += 1
            time.sleep(0.25)
        except (StaleElementReferenceException, NoSuchElementException):
            continue
        except Exception:
            continue
    return clicked

def _process_detail_tab_content(driver) -> bool:
    url = driver.current_url or ""
    if DETAILS_KEYWORD not in url:
        return False
    if url in _processed_detail_urls:
        return False
    html = driver.page_source or ""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    text = "\n".join([ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()])
    print(f"\n===== DETAY =====\nURL: {url}\nKarakter: {len(text)}\n{text[:500]}{'...' if len(text)>500 else ''}\n=================\n")
    _processed_detail_urls.add(url)
    _save_html_snapshot(driver, prefix="detail")
    return True

def _process_new_detail_tabs(driver) -> int:
    """
    Yeni açılmış (base harici) sekmelere minimal geçiş.
    İşlenen sekme kapatılır, base sekmeye geri dönülür.
    """
    global _base_handle
    if _base_handle is None:
        _base_handle = driver.current_window_handle

    processed_count = 0
    handles = list(driver.window_handles)

    # Sadece yeni (işlenmemiş) ve base olmayan sekmeler
    new_handles = [h for h in handles if h != _base_handle and h not in _processed_handles]

    for h in new_handles:
        try:
            driver.switch_to.window(h)
            if _process_detail_tab_content(driver):
                processed_count += 1
            _processed_handles.add(h)
            # Sekmeyi kapat (detaylar alındıktan sonra)
            driver.close()
            driver.switch_to.window(_base_handle)
        except Exception:
            # Sekme kapanmış olabilir; devam et
            try:
                if _base_handle in driver.window_handles:
                    driver.switch_to.window(_base_handle)
            except Exception:
                pass
            continue

    # Eğer detay aynı sekmede (base) açıldıysa:
    try:
        if driver.current_window_handle == _base_handle and DETAILS_KEYWORD in (driver.current_url or ""):
            if _process_detail_tab_content(driver):
                processed_count += 1
                # Liste sayfasına geri dön (gerekiyorsa)
                driver.back()
                time.sleep(0.7)
    except Exception:
        pass

    return processed_count

def _loop_step(driver) -> str | None:
    """
    Tek döngü adımı: yeni kartlara tıkla, yeni detay sekmelerini işle.
    Minimal sekme geçişi.
    """
    global _base_handle
    if not driver:
        return "Driver yok"
    if _base_handle is None:
        _base_handle = driver.current_window_handle

    current_url = driver.current_url or ""

    clicks = 0
    if DETAILS_KEYWORD not in current_url:
        # Yalnızca liste sayfasındayken kartlara tıkla
        clicks = _click_new_order_cards(driver)

    processed = _process_new_detail_tabs(driver)

    msg_parts = []
    if clicks:
        msg_parts.append(f"{clicks} kart tıklandı")
    if processed:
        msg_parts.append(f"{processed} detay işlendi (Toplam: {len(_processed_detail_urls)})")

    # Periyodik liste snapshot (örn. her 30 sn)
    if int(time.time()) % 30 == 0 and DETAILS_KEYWORD not in current_url:
        _save_html_snapshot(driver, prefix="list")

    return " | ".join(msg_parts) if msg_parts else None

# ================== ASYNC ANA ==================
async def async_main():
    global _base_handle
    print("🎨 ScrapyBridge başlatılıyor...")
    print("🌐 Browser başlatılıyor...")
    if not await browser_manager.initialize_browser():
        print("❌ Browser başlatılamadı!")
        return
    print("✅ Browser başarıyla başlatıldı!")

    print(f"🔍 {TARGET_URL} sayfasına yönlendiriliyor...")
    if not await browser_manager.navigate_to_url(TARGET_URL):
        print(f"❌ {TARGET_URL} yüklenemedi!")
        return
    print("✅ Sayfa yüklendi!")

    _base_handle = getattr(browser_manager.driver, "current_window_handle", None)
    print("\n🔄 Döngü başlıyor. Çıkmak için Ctrl+C ...")

    driver = browser_manager.driver
    while True:
        try:
            status = _loop_step(driver)
            if status:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] {status}")
            await asyncio.sleep(4)
        except KeyboardInterrupt:
            print("\n🛑 Kullanıcı durdurdu.")
            break
        except WebDriverException as e:
            print(f"💥 WebDriverException: {e}")
            print("🔄 Yeniden başlatılıyor...")
            await browser_manager.close_browser()
            await asyncio.sleep(2)
            if await browser_manager.initialize_browser() and await browser_manager.navigate_to_url(TARGET_URL):
                if not browser_manager.driver:
                    print("❌ Yeniden başlatma başarısız.")
                    break
                print("✅ Yeniden başlatıldı.")
                _base_handle = browser_manager.driver.current_window_handle
            else:
                print("❌ Yeniden başlatma başarısız.")
                break
        except Exception as e:
            print(f"Genel hata: {e}")
            await asyncio.sleep(5)

    print("\n🔚 Browser kapatılıyor...")
    await browser_manager.close_browser()
    print("✅ Temizlik tamamlandı!")

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)).replace("src", ""))
    print("Çalışma dizini:", os.getcwd(), "\n")
    main()