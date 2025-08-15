import logging, os
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path

def setup_logging():
    """Uygulama genelinde loglamayı yapılandırır."""
    pathh = ""
    try: pathh = os.path.join(os.path.expanduser("~"), "Desktop")
    except : pathh = Path(__file__).parent.parent
    
    log_dir = os.path.join(pathh, "saveAl")
    if not os.path.exists(log_dir): os.makedirs(log_dir)

    log_file_path = os.path.join(log_dir, f"scrapp-log-{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.log")

    # Root logger'ı al
    logger = logging.getLogger()
    logger.setLevel(logging.INFO) # Yakalanacak en düşük log seviyesi

    # Mevcut handler'ları temizle (tekrar tekrar eklenmesini önlemek için)
    if logger.hasHandlers(): logger.handlers.clear()

    # Log formatı oluştur
    formatter = logging.Formatter( '%(asctime)s - %(name)s - %(levelname)s - (%(filename)s) - %(funcName)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S' )

    # Konsol (Stream) Handler: Logları terminale basar
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # Dosya (File) Handler: Logları dosyaya yazar
    # RotatingFileHandler, dosya çok büyüdüğünde yeni bir dosyaya geçer.
    file_handler = RotatingFileHandler(log_file_path, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logging.info("Loglama yapılandırması tamamlandı.")

