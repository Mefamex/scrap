import os, asyncio, time, hashlib
from datetime import datetime
from typing import List, Optional, Set

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)

from src.settings import settings
from src.browser_manager import get_browser_manager, BrowserManager

# ================== KONSTLAR ==================
TARGET_URL = "https://partner.tgoyemek.com/meal/245018/order/list"
DETAILS_KEYWORD = "order/list/details"
CARD_SELECTOR = ".order-card"  # tüm hepsine tıklanıp bilgileri alınacak
DETAIL_PANEL_SELECTOR = ".order-details-item-list"  # sağ tarafta yüklenen detay paneli

DESKTOP_DIR = os.path.join(os.path.expanduser("~"), "Desktop")
SAVE_DIR = os.path.join(DESKTOP_DIR, "saveAl")
os.makedirs(SAVE_DIR, exist_ok=True)

# ================== DURUM =====================
browser_manager: BrowserManager = get_browser_manager()
_clicked_cards: Set[str] = set()
_processed_detail_urls: Set[str] = set()

_base_handle: Optional[str] = None

# ================== YARDIMCI ==================
def _hash(txt: str) -> str: return hashlib.sha256(txt.encode("utf-8", "ignore")).hexdigest()[:16]



def _capture_dom_outer_html(driver) -> str:
    try:
        driver.execute_cdp_cmd("DOM.enable", {})
        root = driver.execute_cdp_cmd("DOM.getDocument", {"depth": 0})
        node_id = root["root"]["nodeId"]
        return driver.execute_cdp_cmd("DOM.getOuterHTML", {"nodeId": node_id}).get("outerHTML", "")
    except Exception: return driver.page_source or ""




def _save_html_snapshot(driver, prefix: str) -> str:
    """
    Driver'dan alınan HTML'i kaydeder. Kaydetmeden önce
    <script>, <noscript> ve <style> etiketlerini kaldırır.
    """
    html_source = _capture_dom_outer_html(driver)
    try:
        soup = BeautifulSoup(html_source, "html.parser")
        for tag in soup.find_all(["script", "noscript", "style"]):  tag.decompose()
        cleaned_html = str(soup)
    except Exception:  cleaned_html = html_source

    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    page_title = (getattr(driver, "title", "") or "page").replace(" ", "_").replace("/", "_").replace("\\", "_")
    path = os.path.join(SAVE_DIR, f"{ts}_{prefix}_{page_title}.html")
    try:
        with open(path, "w", encoding="utf-8") as f:  f.write(cleaned_html)
        print(f"💾 Kaydedildi: {path}")
    except Exception as e:  print(f"Snapshot kaydedilemedi: {e}")
    return path





def _parse_detail_panel_html(html: str) -> dict:
    """Detay panelindeki sipariş bilgisini ayrıştır ve dict döndür."""
    soup = BeautifulSoup(html, "html.parser")
    result = {"items": [], "note": None, "totals": {}, "customer_info": {}, "delivery_type": None, "payment_method": None}

    # Sipariş notu
    note_el = soup.select_one(".order-note__content")
    if note_el:
        result["note"] = " ".join(note_el.get_text(" ", strip=True).split())

    # Sipariş bilgileri (müşteri, adres, il/ilçe vb.)
    for item in soup.select(".order-details-info__item"):
        title_el = item.select_one(".order-details-info__item__title")
        title = title_el.get_text(" ", strip=True).rstrip(":") if title_el else None
        value = ""
        spans = item.find_all("span")
        if len(spans) >= 2:
            value = " ".join(spans[1].get_text(" ", strip=True).split())
        else:
            # fallback: tamamını alıp başlıktan arındır
            txt = item.get_text(" ", strip=True)
            if title and txt.startswith(title):
                value = txt[len(title):].strip()
            else:
                value = txt
        if title: result["customer_info"][title] = value
    # Teslimat tipi
    del_el = soup.select_one(".order-details-info__delivery-type strong")
    if del_el: result["delivery_type"] = del_el.get_text(" ", strip=True)
    # Ödeme yöntemi
    pay_el = soup.select_one(".order-payment-type span")
    if pay_el: result["payment_method"] = pay_el.get_text(" ", strip=True)
    # Ürünler
    item_blocks = soup.select(".order-item-list .order-item")
    for blk in item_blocks:
        name_el = blk.select_one(".order-item--product__name span, .order-item--product__name")
        qty_el = blk.select_one(".order-item__count")
        price_el = blk.select_one(".order-item__total-price, .order-item__total-price--sub, .order-item__total-price--sub")
        name = name_el.get_text(" ", strip=True) if name_el else ""
        qty = qty_el.get_text(" ", strip=True) if qty_el else ""
        price = price_el.get_text(" ", strip=True) if price_el else ""
        # ignore empty product rows
        if not name and not price: continue
        result["items"].append({"name": name, "qty": qty, "price": price})

    # Totaller (ör: Sipariş Tutarı, Toplam vb.)
    for row in soup.select(".order-details-price tr"):
        tds = row.find_all("td")
        if len(tds) >= 2:
            label = tds[0].get_text(" ", strip=True)
            value = tds[1].get_text(" ", strip=True)
            result["totals"][label] = value
    return result


def _log_processed_order(parsed: dict, title_preview: str) -> None:
    """Yeni işlendiğinde masaüstündeki 'açtığı siparişler.txt' dosyasına ekle ve konsola özet bas."""
    # Prepare lines
    lines: list[str] = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines.append(f"[{ts}] {title_preview}")
    # Customer info
    if parsed.get("customer_info"):
        lines.append("-- Müşteri Bilgileri --")
        for k, v in parsed["customer_info"].items(): lines.append(f"{k}: {v}")
    if parsed.get("delivery_type"): lines.append(f"Teslimat Tipi: {parsed.get('delivery_type')}")
    if parsed.get("payment_method"): lines.append(f"Ödeme Yöntemi: {parsed.get('payment_method')}")
    if parsed.get("note"): lines.append(f"Sipariş Notu: {parsed.get('note')}")
    if parsed.get("items"):
        lines.append("-- Ürünler --")
        for it in parsed["items"]:
            lines.append(f"- {it.get('name','')}  x{it.get('qty','')}  {it.get('price','')}")
    if parsed.get("totals"):
        lines.append("-- Toplamlar --")
        for k, v in parsed["totals"].items():
            lines.append(f"{k}: {v}")
    lines.append("\n")

    # Console summary
    print("\n--- SIPARIS KAYDI ---")
    for l in lines:
        print(l)
    print("--- SON ---\n")

    # Append to SAVE_DIR/siparisler.txt with timestamp header and long separator
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        path = os.path.join(SAVE_DIR, "siparisler.txt")
        sep = "-" * 80
        # Write timestamp header then details then separator
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {title_preview}\n")
            for l in lines[1:]:
                f.write(l + "\n")
            f.write(sep + "\n\n")
        print(f"📝 Kaydedildi: {path}")
    except Exception as e:
        print(f"Dosyaya yazılamadı: {e}")


# ...existing code...





def _wait_for_detail_panel_change(driver, previous_html: str | None, timeout: float = 6.0) -> Optional[str]:
    """Detay paneli görünür olana ve içeriği değişene kadar bekle. Yeni outerHTML döner veya None."""
    try:
        wait = WebDriverWait(driver, timeout)
        panel = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, DETAIL_PANEL_SELECTOR)))
        # Beklemede daha güvenli kontrol: önce anlamlı içeriğin gelmesini, sonra değişimi kontrol et
        start = time.time()
        last_html = previous_html or ""
        # Panel içeriğinin tamamını al -> müşteri bilgileri de panel dışında ayrı bir blok olabilir
        while time.time() - start < timeout:
            try:
                # panel referansının stale olma ihtimaline karşı yeniden bul
                panel = driver.find_element(By.CSS_SELECTOR, DETAIL_PANEL_SELECTOR)
                # panelin tamamını al (içindeki order-details-info, order-item-list vb. dahil)
                current_html = (panel.get_attribute("outerHTML") or "").strip()
            except Exception:
                current_html = ""
            # önce boş panelden anlamlı içeriğe geçiş
            if not last_html:
                if len(current_html) > 50:
                    return current_html
            else:
                if current_html and current_html != last_html:
                    return current_html
            time.sleep(0.12)
    except TimeoutException: return None
    except Exception: return None
    return None


onceki_print = ""

def _click_new_order_cards(driver) -> int:
    """Her yeni kartı tıkla, detay paneli yüklenmesini bekle, veriyi ayrıştır."""
    global onceki_print
    try: cards = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)
    except Exception: return 0
    if not cards:
        print("⏸ Kart bulunamadı.")
        return 0
    clicked = 0
    # mevcut panel html'i al (yeniden bul)
    prev_panel_html = ""
    try:
        panel = driver.find_element(By.CSS_SELECTOR, DETAIL_PANEL_SELECTOR)
        prev_panel_html = panel.get_attribute("outerHTML") or ""
    except Exception:  prev_panel_html = ""
    yaz = f"🧭 Bulunan kart sayısı: {len(cards)}  (daha önce işlenen: {len(_clicked_cards)})"
    if onceki_print != yaz:
        print(yaz)
        onceki_print = yaz
    # Her döngüde index ile yeniden locate et -> stale referans önlemi
    for idx in range(len(cards)):
        try:
            # yeniden locate edilen element
            els = driver.find_elements(By.CSS_SELECTOR, CARD_SELECTOR)
            if idx >= len(els): continue
            el = els[idx]
            txt = el.text.strip()
            if not txt: continue
            key = _hash(f"{driver.current_url}|{txt[:160]}")
            if key in _clicked_cards: continue
            # target varsa kaldır (yeni sekme açılmasını engelle)
            try: driver.execute_script("arguments[0].removeAttribute('target');", el)
            except Exception:  pass
            # karta scroll yap
            try: driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
            except Exception: pass
            clicked_ok = False  # normal click dene; işe yaramazsa JS click
            try:
                el.click()
                clicked_ok = True
            except Exception:
                try:
                    driver.execute_script("arguments[0].click();", el)
                    clicked_ok = True
                except Exception as e:
                    print(f"⚠️ Kart tıklama hatası (idx={idx}): {e}")
                    clicked_ok = False
            if not clicked_ok:
                time.sleep(0.2)  # tık başarısızsa bir sonraki karta geç
                continue
            # detay panelin yüklenmesini bekle
            new_html = _wait_for_detail_panel_change(driver, prev_panel_html, timeout=8.0)
            if not new_html:
                # fallback: kısa bekleme sonrası panelin outerHTML'ini al
                time.sleep(0.6)
                try:
                    panel = driver.find_element(By.CSS_SELECTOR, DETAIL_PANEL_SELECTOR)
                    new_html = panel.get_attribute("outerHTML") or ""
                except Exception:  new_html = ""
            print(f"🔎 Önceki panel uzunluğu: {len(prev_panel_html or '')}, yeni uzunluğu: {len(new_html or '')}")
            if new_html and len(new_html.strip()) > 50:
                # Bazı sayfalarda müşteri bilgileri ayrı bir blokta (.order-details-info) olabilir.
                try:
                    info_el = driver.find_element(By.CSS_SELECTOR, ".order-details-info")
                    info_html = info_el.get_attribute("outerHTML") or ""
                except Exception:
                    info_html = ""
                combined_html = (info_html or "") + new_html
                parsed = _parse_detail_panel_html(combined_html)
                # çıktı ver
                print("\n===== DETAY (panel) =====")
                title_preview = (txt[:120] + "...") if len(txt) > 120 else txt
                print("Kart başlığı:", title_preview)
                # Yeni: Sipariş bilgileri (müşteri / adres / sipariş no vb.)
                if parsed.get("customer_info"):
                    print("Sipariş Bilgileri:")
                    for k, v in parsed["customer_info"].items():  print(f"  {k}: {v}")
                if parsed.get("delivery_type"):
                    print("Teslimat Tipi:", parsed["delivery_type"])
                if parsed.get("payment_method"): print("Ödeme Yöntemi:", parsed["payment_method"])

                if parsed.get("note"):  print("Sipariş Notu:", parsed["note"])
                for it in parsed["items"]:  print(f"- {it['name']}  x{it['qty']}  {it['price']}")
                if parsed["totals"]:
                    print("Toplamlar:")
                    for k, v in parsed["totals"].items(): print(f"  {k}: {v}")
                print("=========================\n")
                # log to file and save snapshot
                try:
                    _log_processed_order(parsed, title_preview)
                except Exception as e:
                    print(f"Logging hata: {e}")
                _save_html_snapshot(driver, prefix="detail")
                # İşlendikten sonra hash anahtarı ile işaretle
                _clicked_cards.add(key)
                prev_panel_html, clicked = new_html, clicked+1
            else:
                print("⚠️ Detay paneli yüklenemedi veya anlamlı içerik yok.")
                time.sleep(0.4)  # kısa bekleme
            time.sleep(0.35)
        except (StaleElementReferenceException, NoSuchElementException):  continue
        except Exception as e:
            print(f"click_new_order_cards genel hata: {e}")
            continue
    return clicked




def _loop_step(driver) -> str | None:
    """  Tek döngü adımı: yeni kartlara tıkla, detay panelini işle. """
    if not driver: return "Driver yok"
    current_url = driver.current_url or ""
    clicks = 0
    if DETAILS_KEYWORD in current_url:  clicks = _click_new_order_cards(driver)
    msg_parts = []
    if clicks: msg_parts.append(f"{clicks} kart işlendi (Toplam tıklanan: {len(_clicked_cards)})")
    # Periyodik liste snapshot (örn. her 30 sn)
    if int(time.time()) % 30 == 0 and DETAILS_KEYWORD not in current_url: _save_html_snapshot(driver, prefix="list")
    return " | ".join(msg_parts) if msg_parts else None






# ================== ASYNC ANA ==================
async def async_main():
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

    print("\n🔄 Döngü başlıyor. Çıkmak için Ctrl+C ...")
    driver = browser_manager.driver
    while True:
        try:
            status = _loop_step(driver)
            if status:  print(f"[{datetime.now().strftime('%H:%M:%S')}] {status}")
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
                print("✅ Yeniden başlatıldı.")
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
