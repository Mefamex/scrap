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
from selenium.common.exceptions import TimeoutException, WebDriverException

from webdriver_manager.chrome import ChromeDriverManager
import asyncio
import logging
import time
import os
import base64
from typing import Optional, Dict, Any, List, Union
from pathlib import Path

from src.settings import settings

# Logger initialization
logger = logging.getLogger(__name__)



class BrowserManager:
    """Tarayıcı yöneticisi sınıfı"""
    
    def __init__(self):
        self.driver: webdriver.Chrome
        self.is_initialized = False
        self.config = settings.browser_config
        self.start_time = time.time()
        self.session_count = 0
        
    async def initialize_browser(self) -> bool:
        """Tarayıcıyı başlat ve açık tut"""
        try:
            chrome_options = Options()
            
            # Temel ayarlar
            if self.config.headless: chrome_options.add_argument("--headless=new")
            
            # Pencere boyutu
            width, height = self.config.window_size
            chrome_options.add_argument(f"--window-size={width},{height}")
            
            # Performans optimizasyonları
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--disable-web-security")
            chrome_options.add_argument("--disable-features=VizDisplayCompositor")
            chrome_options.add_argument("--disable-extensions")
            chrome_options.add_argument("--disable-plugins")
            
            # Gizlilik ve güvenlik
            chrome_options.add_experimental_option('useAutomationExtension', False)
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_argument("--disable-blink-features=AutomationControlled")
            
            # User Agent
            if self.config.user_agent: chrome_options.add_argument(f"--user-agent={self.config.user_agent}")
            else: chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Resimler ve JavaScript
            prefs = {}
            if self.config.disable_images:  prefs["profile.managed_default_content_settings.images"] = 2
            if self.config.disable_javascript:  prefs["profile.managed_default_content_settings.javascript"] = 2
            
            if prefs: chrome_options.add_experimental_option("prefs", prefs)
            
            # Özel Chrome seçenekleri
            for option in self.config.chrome_options: chrome_options.add_argument(option)
            
            # Proxy ayarları
            if self.config.proxy:  chrome_options.add_argument(f"--proxy-server={self.config.proxy}")
            
            # ChromeDriver servisini oluştur
            if settings.chromedriver_path and os.path.exists(settings.chromedriver_path): service = Service(executable_path=settings.chromedriver_path)
            else: service = Service(ChromeDriverManager().install())
            
            # Chrome binary path
            if settings.chrome_binary_path and os.path.exists(settings.chrome_binary_path): chrome_options.binary_location = settings.chrome_binary_path
            
            # Async içinde browser başlat
            loop = asyncio.get_event_loop()
            self.driver = await loop.run_in_executor( None,  lambda: webdriver.Chrome(service=service, options=chrome_options) )
            
            # Bot detection bypass
            await loop.run_in_executor(None, self._setup_stealth)
            
            # Başlangıçta API ana sayfasını aç
            # API ana sayfasını açmayı ayrı bir task'e al
            asyncio.create_task(self._delayed_api_load())

            # Timeout ayarları
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
    
    async def _delayed_api_load(self):
        """API hazır olduktan sonra ana sayfayı aç"""
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
        try:            
            # WebDriver property'sini gizle
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            # Chrome Detection bypass
            self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            })
            
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
            
        except Exception as e:
            logger.warning(f"Stealth setup failed: {e}")
    
    async def navigate_to_url(self, url: str, timeout: Optional[int] = None) -> bool:
        """URL'ye git"""
        try:
            if not self.is_initialized: await self.initialize_browser()
            timeout = timeout or settings.browser_timeout
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.driver.get, url)
            # Sayfa yüklenene kadar bekle
            await loop.run_in_executor(  None, lambda: WebDriverWait(self.driver, timeout).until(lambda d: d.execute_script("return document.readyState") == "complete" ) )
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
        try:
            loop = asyncio.get_event_loop()
            return {
                "current_url": await loop.run_in_executor(None, lambda: self.driver.current_url),
                "title": await loop.run_in_executor(None, lambda: self.driver.title),
                "window_size": await loop.run_in_executor(None, lambda: self.driver.get_window_size()),
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
        """Tarayıcıyı kapat"""
        drv = getattr(self, "driver", None)
        if drv:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, drv.quit)
            except Exception as e: logger.error(f"Error closing browser: {e}")
            finally:
                self.driver = None  # type: ignore
                self.is_initialized = False
                logger.info("Browser closed")


# Global browser manager instance
browser_manager = BrowserManager()
