# -*- coding: utf-8 -*-
"""
===========================================================
        SCRAPY BRIDGE - LAUNCHER SCRIPT
===========================================================

Description:
    ScrapyBridge uygulamasını başlatmak için ana script.
    Sadece konsol modunda çalışır.

Author:
    mefamex (info@mefamex.com)
===========================================================
"""
import sys
import asyncio
from pathlib import Path

# Proje root dizinini sys.path'e ekle.
# Bu, 'src' gibi modüllerin doğru şekilde import edilmesini sağlar.
project_root = Path(__file__).parent
if str(project_root) not in sys.path: sys.path.insert(0, str(project_root))

# --- Loglamayı, diğer her şeyden önce yapılandır ---
from src.log_config import setup_logging
setup_logging()
# ---------------------------------------------------

# Ana uygulama mantığını import et
from src.main import async_main


if __name__ == "__main__":
    try:
        # Doğrudan src/main.py içerisindeki ana async fonksiyonu çalıştır.
        # Bu, uygulamanın tek ve doğru başlangıç noktasıdır.
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\n👋 ScrapyBridge kullanıcı tarafından kapatılıyor...")
    except Exception as e:
        # Beklenmedik bir hata olursa logla
        import logging
        logging.critical(f"Kritik Hata (run.py): {e}", exc_info=True)
    finally:
        print("Uygulama sonlandı.")
