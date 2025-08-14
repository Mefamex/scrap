# -*- coding: utf-8 -*-
"""
===========================================================
        SCRAPY BRIDGE - BROWSER MANAGER
===========================================================

Description:
    Selenium WebDriver yöneticisi. Tarayıcıyı açık tutar ve 
    scraping işlemlerini yönetir.

Author:
    mefamex (info@mefamex.com)

===========================================================
"""

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager
import asyncio, logging, time, os, base64, platform, subprocess, psutil
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

from src.settings import settings, _get_chrome_driver_path

# Logger initialization
logger = logging.getLogger(__name__)



def _terminate_chrome_tasks():
    """Sistemden açık Chrome görevlerini sonlandırır."""
    try:
        chrome_processes = [p for p in psutil.process_iter(['name']) if p.info['name'] == 'chrome.exe']
        if not chrome_processes: return
        for proc in chrome_processes: proc.terminate()
        logger.info("Açık Chrome görevleri sonlandırıldı.")
    except Exception as e: logger.error(f"Chrome görevlerini sonlandırırken hata oluştu: {e}")

class BrowserManager:
    """Singleton class to manage the Selenium browser instance."""
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(BrowserManager, cls).__new__(cls)
            # __init__ metodunun sadece ilk oluşturmada çalışmasını sağla
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Tarayıcı yöneticisi sınıfı"""
        if self._initialized: return
        self.driver: Optional[WebDriver] = None
        self.is_initialized = False
        self.config = settings.browser_config
        self.start_time = time.time()
        self.session_count = 0
        self._initialized = True
        
    async def initialize_browser(self) -> bool:
        """Tarayıcıyı başlat ve açık tut"""
        if self.is_initialized:
            logger.info("Browser already initialized.")
            return True
        try:
            # --- 1) Çevre değişkenleri ile native log seviyesini düşür ---
            os.environ.setdefault("ABSL_CPP_MIN_LOG_LEVEL", "3")
            os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
            
            chromedriver_path = _get_chrome_driver_path()
            _terminate_chrome_tasks()

            chrome_options = Options()

            user_data_dir = os.path.join(settings.app_base_dir, "chrome_profiles", "BOTum_ben")
            os.makedirs(user_data_dir, exist_ok=True)
            logger.info(f"Chrome user data dir: {user_data_dir}")
            chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
            chrome_options.add_argument("--profile-directory=Default")
            chrome_options.add_argument("--start-maximized")
            # Log seviyesini düşür
            chrome_options.add_argument("--log-level=3")
            # Sesli girişi devre dışı bırak
            chrome_options.add_argument("--disable-voice-input")
            # Temel güvenilir / performans flag'leri
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")

            # chrome_options.add_argument("--disable-gpu")

            # Remote debugging FLAG EKLEME (DevTools listening mesajı normal ve zararsız)

            # Bot / otomasyon gizleme
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")

            # UA
            if self.config.user_agent: chrome_options.add_argument(f"--user-agent={self.config.user_agent}")

            # Ek kullanıcı tanımlı seçenekler
            for option in self.config.chrome_options: chrome_options.add_argument(option)

            if self.config.proxy: chrome_options.add_argument(f"--proxy-server={self.config.proxy}")

            # --- Manuel chromedriver başlat: stdout/stderr'i DEVNULL yaparak Chrome'un absl/TF loglarını bastır ---
            # Uygulama Windows olduğundan CREATE_NO_WINDOW kullan (gerekiyorsa)
            try:
                # boş bir port isteği için socket kullanarak kullanılabilir port elde et
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.bind(('127.0.0.1', 0))
                port = s.getsockname()[1]
                s.close()
            except Exception: port = 0

            chromedriver_cmd = [str(chromedriver_path), f"--port={port}"] if port else [str(chromedriver_path)]
            creationflags = 0
            if platform.system().lower() == "windows":
                creationflags = subprocess.CREATE_NO_WINDOW

            # Başlat ve çıktıyı sustur
            self._chromedriver_proc = subprocess.Popen( chromedriver_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags, )

            # Wait for chromedriver to accept connections (kısa bekleme döngüsü)
            import time, socket
            start = time.time()
            timeout = 5.0
            connected = False
            port_to_try = port if port else 9515
            while time.time() - start < timeout:
                try:
                    with socket.create_connection(("127.0.0.1", port_to_try), timeout=0.5):
                        connected = True
                        break
                except Exception:
                    time.sleep(0.1)
                    continue

            if not connected:
                # chromedriver açılamadıysa proc'u öldür ve hata ver
                try:
                    if self._chromedriver_proc:
                        self._chromedriver_proc.kill()
                        self._chromedriver_proc = None
                except Exception:  pass
                raise RuntimeError("Chromedriver process başlatılamadı veya bağlantı kurulamadı.")

            # ChromeOptions ile remote driver'a bağlan
            from selenium.webdriver.remote.webdriver import WebDriver
            from selenium.webdriver.remote.remote_connection import RemoteConnection

            executor_url = f"http://127.0.0.1:{port_to_try}"
            loop = asyncio.get_event_loop()
            # webdriver.Remote kullanarak chromedriver'a bağlan
            self.driver = await loop.run_in_executor(
                None,
                lambda: webdriver.Remote(command_executor=executor_url, options=chrome_options)
            )

            if not self.driver:
                logger.error("Failed to initialize the browser driver.")
                return False
            
            
            await loop.run_in_executor(None, self._setup_stealth)

            self.driver.set_page_load_timeout(settings.browser_timeout)
            self.driver.implicitly_wait(10)

            self.is_initialized = True
            self.session_count += 1
            logger.info("Browser initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Browser initialization failed: {e}")
            self.is_initialized = False
            return False
        # Eğer manuel başlattıysak chromedriver sürecini sonlandır

    
    
    
    
    async def _delayed_api_load(self):
        """API hazır olduktan sonra ana sayfayı aç"""
        if self.driver is None or not self.is_initialized:
            logger.error("Browser is not initialized.")
            return
        api_url = f"http://{settings.host}:{settings.port}"
        max_attempts = 30
        
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(1)
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    try:
                        async with session.get(f"{api_url}/health", timeout=aiohttp.ClientTimeout(total=5)) as response:
                            if response.status == 200:
                                loop = asyncio.get_event_loop()
                                await loop.run_in_executor(None, self.driver.get, api_url)
                                logger.info(f"Browser loaded API homepage: {api_url}")
                                return
                    except: pass
            except Exception as e: logger.debug(f"API load attempt {attempt + 1} failed: {e}")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.driver.get, "about:blank")
            logger.info("Opened about:blank as fallback")
        except Exception as e: logger.warning(f"Could not load any page: {e}")
    
    def _setup_stealth(self):
        """Bot detection bypass"""
        if not self.driver:
            logger.error("Browser is not initialized.")
            return
        try:
            # WebDriver property'sini gizle
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            # Chrome Detection bypass
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', { "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36' })
            # Permissions override
            self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                "source": """
                    Object.defineProperty(navigator, 'permissions', {
                        get: () => ({
                            query: () => Promise.resolve({ state: 'granted' })
                        })
                    });
                """
            })
        except Exception as e: logger.warning(f"Stealth setup failed: {e}")
    
    
    
    
    
    
    
    async def navigate_to_url(self, url: str, timeout: Optional[int] = None) -> bool:
        """URL'ye git"""
        if not self.is_initialized or not self.driver:
            logger.error("Browser is not initialized.")
            return False
        try:
            if not self.is_initialized: await self.initialize_browser()
            timeout = timeout or settings.browser_timeout
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.driver.get, url)
            # Sayfa yüklenene kadar bekle
            await loop.run_in_executor(None, lambda: WebDriverWait(self.driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete")) # type: ignore
            logger.info(f"Successfully navigated to: {url}")
            return True
        except TimeoutException:
            logger.error(f"Navigation timeout for URL: {url}")
            return False
        except Exception as e:
            logger.error(f"Navigation failed for URL {url}: {e}")
            return False
    
    
    
    
    
    
    
    
    
    async def wait_for_element(self, selector: str, timeout: int = 30, by: str = "css") -> bool:
        """Element yüklenene kadar bekle"""
        if not self.is_initialized or not self.driver:
            logger.error("Browser is not initialized.")
            return False
        try:
            loop = asyncio.get_event_loop()
            wait = WebDriverWait(self.driver, timeout)
            
            by_mapping = {
                "css": By.CSS_SELECTOR,
                "xpath": By.XPATH,
                "id": By.ID,
                "name": By.NAME,
                "tag": By.TAG_NAME,
                "class": By.CLASS_NAME
                }
            
            by_method = by_mapping.get(by, By.CSS_SELECTOR)
            
            await loop.run_in_executor(
                None,
                wait.until,
                EC.presence_of_element_located((by_method, selector))
            )
            return True
            
        except TimeoutException:
            logger.error(f"Element wait timeout: {selector}")
            return False
        except Exception as e:
            logger.error(f"Element wait failed: {e}")
            return False






    async def click_element(self, element: WebElement) -> bool:
        """Element'e tıkla"""
        try:
            if not element:
                return False
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, element.click)
            return True
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False
    
    async def scroll_page(self, direction: str = "down", count: int = 1) -> bool:
        """Sayfa scroll"""
        if not self.is_initialized or not self.driver:
            logger.error("Browser is not initialized.")
            return False
        try:
            loop = asyncio.get_event_loop()
            for _ in range(count):
                if direction == "down":
                    await loop.run_in_executor(None, self.driver.execute_script, "window.scrollTo(0, document.body.scrollHeight);")
                elif direction == "up": await loop.run_in_executor(None, self.driver.execute_script, "window.scrollTo(0, 0);")
                await asyncio.sleep(1)
            return True
        except Exception as e:
            logger.error(f"Scrolling failed: {e}")
            return False
    
    
    
    
    
    
    
    
    
    async def take_screenshot(self, file_path: str, full_page: bool = False) -> bool:
        """Screenshot al"""
        if not self.is_initialized or not self.driver:
            logger.error("Browser is not initialized.")
            return False
        try:
            loop = asyncio.get_event_loop()
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            if full_page:
                await loop.run_in_executor( None, self.driver.save_screenshot, file_path )
            else:
                screenshot_data = await loop.run_in_executor( None, self.driver.get_screenshot_as_png )
                with open(file_path, 'wb') as f: f.write(screenshot_data)
            logger.info(f"Screenshot saved: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False
    
    
    
    
    
    
    async def get_browser_info(self) -> Dict[str, Any]:
        """Tarayıcı bilgilerini al"""
        if not self.driver:
            logger.error("Browser is not initialized.")
            return {"error": "Browser is not initialized."}
        try:
            loop = asyncio.get_event_loop()
            return {
                "current_url": await loop.run_in_executor(None, lambda: self.driver.current_url),           # type: ignore
                "title": await loop.run_in_executor(None, lambda: self.driver.title),                       # type: ignore
                "window_size": await loop.run_in_executor(None, lambda: self.driver.get_window_size()),     # type: ignore
                "session_id": self.driver.session_id,
                "capabilities": self.driver.capabilities,
                "uptime": time.time() - self.start_time,
                "session_count": self.session_count
            }
        except Exception as e:
            logger.error(f"Failed to get browser info: {e}")
            return {}
    
    
    
    
    
    async def restart_browser(self) -> bool:
        """Tarayıcıyı yeniden başlat"""
        try:
            await self.close_browser()
            return await self.initialize_browser()
        except Exception as e:
            logger.error(f"Browser restart failed: {e}")
            return False
    
    async def close_browser(self):
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Browser closed successfully.")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None
                self.is_initialized = False
        try:
            if getattr(self, "_chromedriver_proc", None):
                proc = self._chromedriver_proc
                if proc and proc.poll() is None: proc.kill()
                self._chromedriver_proc = None
        except Exception as e: logger.debug(f"Chromedriver proc kill error: {e}")
        finally: self._chromedriver_proc = None


# Global browser_manager referansı
browser_manager: Optional[BrowserManager] = None

def get_browser_manager() -> BrowserManager:
    """BrowserManager nesnesini döner, yoksa oluşturur."""
    global browser_manager
    if browser_manager is None:
        browser_manager = BrowserManager()
    return browser_manager

