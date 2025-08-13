import os, asyncio, time
from src.settings import settings
from src.scrap_page import scrap_all_pages
from src.browser_manager import browser_manager
from time import sleep
from typing import List
from datetime import datetime

from bs4 import BeautifulSoup
try: from selenium.webdriver.common.by import By
except ImportError: By = None


_clicked_cards = set()
_processed_details = set()

DETAILS_KEYWORD = "order/list/details"
CARD_SELECTOR = ".order-card"

DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")

def _save_page_snapshot(driver, prefix: str = "sayfa") -> str:
    """Aktif pencerenin <html> içeriğini Desktop'a kaydeder ve yolunu döner."""
    try:
        html_source = driver.execute_script("return document.documentElement.outerHTML;")
    except Exception:
        html_source = getattr(driver, "page_source", "") or ""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{ts}.txt"
    os.makedirs(os.path.join(DESKTOP_DIR,"saveAl"), exist_ok=True)
    path = os.path.join(DESKTOP_DIR,"saveAl", filename)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_source)
    except Exception as e:
        print(f"Snapshot kaydedilemedi: {e}")
        return ""
    print(f"💾 Sayfa kaydedildi: {path}")
    return path

def _any_details_tab(driver) -> bool:
    for h in driver.window_handles:
        driver.switch_to.window(h)
        if DETAILS_KEYWORD in (driver.current_url or ""):
            return True
    return False

def _click_order_cards(driver) -> int:
    if By is None:  return 0
    try:  cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)
    except Exception:  return 0
    count = 0
    for el in cards:
        try:
            key = f"{driver.current_url}@@{el.text.strip()[:120]}"
            if key in _clicked_cards: continue
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            el.click()
            _clicked_cards.add(key)
            count += 1
            time.sleep(0.3)
        except Exception: continue
    return count

def _extract_details(driver) -> List[str]:
    new_contents = []
    current_tab = driver.current_window_handle
    for h in driver.window_handles:
        driver.switch_to.window(h)
        try: _save_page_snapshot(driver, prefix="sayfa")
        except : pass
        url = driver.current_url or ""
        if DETAILS_KEYWORD not in url: continue
        if url in _processed_details: continue
        html = driver.page_source or ""
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "template"]):  tag.decompose()
        text = "\n".join([ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()])
        print(f"\n===== DETAY SAYFASI =====\nURL: {url}\nKarakter: {len(text)}:\n{text}\n==========================\n")
        _processed_details.add(url)
        new_contents.append(text)
    try: driver.switch_to.window(current_tab)
    except: pass
    return new_contents

def islemler():
    driver = getattr(browser_manager, "driver", None)
    if not driver: return "Driver yok"
    made_clicks = 0
    if not _any_details_tab(driver):
        for h in list(driver.window_handles):
            try:
                driver.switch_to.window(h) 
                made_clicks += _click_order_cards(driver)
            except Exception: continue
        if made_clicks: return f"{made_clicks} order-card tıklandı."
    new_details = _extract_details(driver)
    if new_details: return f"{len(new_details)} yeni details işlendi. Toplam: {len(_processed_details)}"
    return None


async def async_main():
    try:
        print("🎨 ScrapyBridge  başlatılıyor...")
        
        # Browser'ı başlat
        print("🌐 Browser başlatılıyor...")
        if await browser_manager.initialize_browser(): print("✅ Browser başarıyla başlatıldı!")
        else:
            print("❌ Browser başlatılamadı!")
            return 

        # Google.com'a git
        print("🔍 Google.com'a yönlendiriliyor...")
        if await browser_manager.navigate_to_url("https://google.com"): print("✅ Google.com başarıyla yüklendi!")
        else: 
            print("❌ Google.com yüklenemedi!")
            return 
        
        # Browser bilgilerini göster
        browser_info = await browser_manager.get_browser_info()
        print(f"📊 Aktif URL: {browser_info.get('current_url')}")
        print(f"📊 Sayfa Başlığı: {browser_info.get('title')}")
        

        # https://partner.tgoyemek.com/meal/245018/order/list sayfasına git
        print("🔍 Yemek siparişi sayfasına yönlendiriliyor...")
        if await browser_manager.navigate_to_url("https://partner.tgoyemek.com/meal/245018/order/list"): print("✅ Yemek siparişi sayfası başarıyla yüklendi!")
        else:
            print("❌ Yemek siparişi sayfası yüklenemedi!")
            return

        while True:
            try:
                status = islemler()
                if status: print(status)
                sleep(2)
            except KeyboardInterrupt:
                raise
            except Exception as e:
                print(f"İşlem hatası: {e}")

        # Browser'ı açık tut (kullanıcı kapatana kadar)
        print("🔄 Browser açık kalacak. Kapatmak için Ctrl+C basın...")
        try:
            while True:   await asyncio.sleep(1)
        except KeyboardInterrupt:  print("\n👋 Çıkış yapılıyor...")
            
    except KeyboardInterrupt:
        print("\n👋 Kullanıcı tarafından durduruldu...")
    except Exception as e:
        print(f"Hata (main.py): {e}")
    finally:
        # Browser'ı kapat
        print("🔚 Browser kapatılıyor...")
        await browser_manager.close_browser()
        print("✅ Temizlik tamamlandı!")


def main():
    asyncio.run(async_main())

if __name__ == "__main__": 
    os.chdir(os.path.dirname(os.path.abspath(__file__)).replace("src", ""))
    print("Çalışma dizini:", os.getcwd(),"\n\n\n")
    main()