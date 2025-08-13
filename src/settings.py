# -*- coding: utf-8 -*-
"""
===========================================================
        SCRAPY BRIDGE - MICROSERVICE SETTINGS
===========================================================

Description:
    Web scraping mikroservisi için ayarlar ve konfigürasyon.

Author:
    mefamex (info@mefamex.com)

===========================================================
"""

from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Optional, List
import subprocess, re, platform
from shutil import which


class Settings(BaseSettings):
    """Mikroservis ayarları"""
    
    class BROWSER_CONFIG:
        headless: bool = False
        window_size: tuple = (1066, 600)
        user_agent: str = ""
        user_agent_2: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        disable_images: bool = False
        disable_javascript: bool = False
        chrome_options: List[str] = []
        proxy: Optional[str] = None

    # Config Ayarları
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    # Uygulama Bilgileri
    app_name: str = "ScrapyBridge Microservice"
    app_version: str = "1.0.0"
    app_base_dir: str = str(Path(__file__).resolve().parent.parent)
    print(app_base_dir)
    debug: bool = False
    
    # Server Ayarları
    host: str = "127.0.0.1"
    port: int = 8080
    auto_reload: bool = False
    
    # Browser Ayarları
    browser_config: BROWSER_CONFIG = BROWSER_CONFIG()
    browser_timeout: int = 60
    max_concurrent_requests: int = 5
    
    # Chrome/ChromeDriver Ayarları
    chrome_binary_path: Optional[str] = None
    chromedriver_path: Optional[str] = None
    
    # Güvenlik
    allowed_domains: List[str] = []
    max_requests_per_minute: int = 600
    
    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None
    
    # Cache
    enable_cache: bool = True
    cache_ttl: int = 300  # 5 dakika

def _candidate_chrome_paths():
    system = platform.system()
    if system == "Windows":
        program_files = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        program_files_x86 = Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe")
        yield from [program_files, program_files_x86]
    elif system == "Linux":
        for name in ("google-chrome", "chrome", "chromium", "chromium-browser"):
            p = which(name)
            if p: yield Path(p)
    elif system == "Darwin":
        mac_path = Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
        yield mac_path

def _extract_version(text: str) -> Optional[str]:
    # Ör: "Google Chrome 124.0.6367.207"
    m = re.search(r"(\d+\.\d+\.\d+\.\d+)", text)
    return m.group(1) if m else None

def _get_chrome_version(explicit_path: Optional[str]) -> Optional[str]:
    paths = []
    if explicit_path:
        paths.append(Path(explicit_path))
    paths.extend(_candidate_chrome_paths())
    for p in paths:
        if not p or not p.exists():
            continue
        try:
            proc = subprocess.run([str(p), "--version"], capture_output=True, text=True, timeout=5)
            out = (proc.stdout or proc.stderr or "").strip()
            ver = _extract_version(out)
            if ver:
                return ver
        except Exception:
            continue
    return None

def _build_user_agent(version: str) -> str:
    # Windows NT kısmını platforma göre uyarlayabilirsin; şimdilik sabit Windows UA formatı.
    return f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36"

def _detect_system_chrome_user_agent(chrome_path: Optional[str]) -> str:
    version = _get_chrome_version(chrome_path)
    if version: return _build_user_agent(version)
    return settings.browser_config.user_agent_2

# Global settings instance
settings = Settings()

# Otomatik user-agent doldurma
if settings.browser_config.user_agent in (None, "", "auto"): settings.browser_config.user_agent = _detect_system_chrome_user_agent(settings.chrome_binary_path)

# İstersen log seviyesine göre bildir
# print("Aktif User-Agent:", settings.browser_config.user_agent)


# Global settings instance
settings = Settings()
