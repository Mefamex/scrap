# -*- coding: utf-8 -*-
"""
===========================================================
        SCRAPY BRIDGE - LAUNCHER SCRIPT
===========================================================

Description:
    ScrapyBridge uygulamasını başlatmak için ana script.
    GUI veya API modunda çalıştırır.

Author:
    mefamex (info@mefamex.com)



===========================================================
"""

__file_path__="run.py"

import sys, os, argparse
from pathlib import Path

# Proje root dizinini sys.path'e ekle
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def main():
    """Ana başlatıcı fonksiyon"""    
    try:
        
        print("🎨 Starting ScrapyBridge GUI...")
        from src.main import main
        main()
            
    except KeyboardInterrupt:
        print("\n👋 ScrapyBridge kapatılıyor...")
        sys.exit(0)
    except Exception as e:
        print(f"Hata (run.py): {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
