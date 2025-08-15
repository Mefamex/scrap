#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Repository Sync Tool - Gelistirilmis Surum
GitHub'dan projenizi yerel sisteminize senkronize eder.
Sadece değisen dosyalari indirir, performansli ve guvenli calisir.
"""

import os, sys, logging, hashlib, requests, time, tempfile, shutil
from urllib.parse import urlencode
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from typing import Optional, Dict, List, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
try: from dateutil import parser
except: 
    print("[WARNING] dateutil modülü yüklenemedi, isoformat kullanalım")
    parser = None # isoformat kullanalim




loc_p = Path(__file__).resolve().parent
if loc_p.name in  ["scripts", "Scripts", "script", "Script"]: loc_p = loc_p.parent
# Gerekli sabitler
DEF_LOCAL_PATH   : str = str(loc_p)   # default olarak dosya dizini
DEF_GITHUB_USER  : str = "Mefamex"
DEF_GITHUB_REPO  : str = "scrap"
DEF_GITHUB_BRANCH: str = "main"
DEF_LOG_PATH     : str = str(Path(__file__).resolve().parent.parent / "logs" / "github_sync.log")
#OPSIYONELLER
DEF_GITHUB_TOKEN : str = ""    # rate limit icin
DEF_IGNORE_PTRN  : List[str] = [".git", ".venv"] # [".git", "__pycache__", "*.pyc", ".env", ".venv"]
DEF_MAX_WORKERS  : int = 4
DEF_RETRY_COUNT  : int = 3
DEF_TIMEOUT      : int = 30
DEF_REQUESTS_PER_SECOND: int = 5



# Loglama yapilandirmasi
try:
    _reconf = getattr(sys.stdout, "reconfigure", None)
    if callable(_reconf):
        _reconf(encoding="utf-8", errors="replace")
        _reconf_err = getattr(sys.stderr, "reconfigure", None)
        if callable(_reconf_err): _reconf_err(encoding="utf-8", errors="replace")
except Exception: pass
log_dir = os.path.dirname(DEF_LOG_PATH)
if log_dir and not os.path.exists(log_dir):
    try: os.makedirs(log_dir, exist_ok=True)
    except Exception: pass

# Loglama: dosya için UTF-8, konsol için sys.stdout üzerinde StreamHandler
file_handler = None
try: file_handler = logging.FileHandler(DEF_LOG_PATH, encoding='utf-8')
except Exception:  file_handler = None
stream_handler = logging.StreamHandler(stream=sys.stdout)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
if file_handler:  file_handler.setFormatter(formatter)
stream_handler.setFormatter(formatter)
if file_handler: logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
else: logging.basicConfig(level=logging.INFO, handlers=[stream_handler])
logger = logging.getLogger(__name__)




class GitHubSyncConfig:
    """Yapilandirma sinifi"""
    def __init__(self,  overrides: Optional[Dict] = None):
        default_config = { 
            "github_user": DEF_GITHUB_USER, "github_repo": DEF_GITHUB_REPO, "github_branch": DEF_GITHUB_BRANCH, "local_path": DEF_LOCAL_PATH,
            "github_token": DEF_GITHUB_TOKEN, "ignore_patterns": DEF_IGNORE_PTRN, "max_workers": DEF_MAX_WORKERS, "retry_count": DEF_RETRY_COUNT, "timeout": DEF_TIMEOUT
        }
        if overrides: default_config.update(overrides)
        self.config = default_config
    def __getattr__(self, name): return self.config.get(name)

class GitHubSyncManager:
    """GitHub senkronizasyon yoneticisi"""
    def __init__(self, config: GitHubSyncConfig):
        self.config = config
        self.session = requests.Session()
        retries = Retry(total=5, backoff_factor=0.5, status_forcelist=[429,500,502,503,504], allowed_methods=["GET","POST","PUT","DELETE","HEAD"])
        adapter = HTTPAdapter(max_retries=retries, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if config.github_token: headers['Authorization'] = f'token {config.github_token}'
        self.session.headers.update(headers)
        self.session.headers.setdefault("User-Agent", f"scrap2-sync/1.0 (+https://github.com/{self.config.github_user}/{self.config.github_repo})")
        self.last_request_time = 0.0
        try:
            rps = float(getattr(config, "requests_per_second", DEF_REQUESTS_PER_SECOND) or DEF_REQUESTS_PER_SECOND)
            self.min_request_interval = 1.0 / max(rps, 0.1)
        except Exception: self.min_request_interval = 1.0 / float(DEF_REQUESTS_PER_SECOND)
        self.stats = { 'downloaded': 0, 'skipped': 0, 'errors': 0, 'start_time': time.time() }
    
    
    def sync_item(self, item: Dict, local_base_path: str, github_path: str = "") -> None:
        """Tek bir item'i senkronize et (dosya veya klasör)"""
        try:
            item_path = item.get('path', '')
            if not item_path:
                logger.debug("sync_item: item path yok, atlanıyor")
                return
            if github_path:
                try: rel = os.path.relpath(item_path, github_path)
                except Exception: rel = item_path
            else: rel = item_path
            local_file_path = os.path.normpath(os.path.join(local_base_path, rel))
            if self.should_ignore_file(item_path):
                logger.debug(f"Ignore edildi: {item_path}")
                return
            typ = item.get('type')
            if typ == 'dir':
                self.sync_directory(item_path, os.path.join(local_base_path, rel))
            elif typ == 'file':
                if self.needs_update(item, local_file_path): self.download_file(item, local_file_path)
                else:
                    logger.debug(f"Guncel: {os.path.relpath(local_file_path)}")
                    self.stats['skipped'] += 1
            else: logger.debug(f"Bilinmeyen item tipi: {typ} - {item_path}")
        except Exception as e:
            logger.error(f"sync_item hata: {e}")
            self.stats['errors'] += 1
    
    
    def _rate_limit_wait(self):
        """Rate limiting icin bekleme"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval: time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    
    def _make_request(self, url: str, retry_count: int = -1, stream: bool = False, extra_headers: Optional[Dict] = None) -> Optional[requests.Response]:
        """Guvenli HTTP isteği yapma"""
        if retry_count == -1: retry_count = self.config.retry_count or DEF_RETRY_COUNT
        headers = {} 
        if extra_headers: headers.update(extra_headers)
        for attempt in range(retry_count):
            try:
                self._rate_limit_wait()
                response = self.session.get(url, timeout=int(self.config.timeout or DEF_TIMEOUT), stream=stream, headers=headers)
                if response.status_code == 403:
                    reset_time = response.headers.get('X-RateLimit-Reset')
                    if reset_time:
                        try: wait_time = int(reset_time) - int(time.time()) + 1
                        except Exception: wait_time = 60
                        logger.warning(f"Rate limit asildi. {wait_time} saniye bekleniyor...")
                        time.sleep(max(wait_time, 60))  # En az 1 dakika bekle
                        continue
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Istek hatasi (deneme {attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1: time.sleep(min(60, 2 ** attempt))
                else:
                    logger.error(f"Istek basarisiz: {url}")
                    self.stats['errors'] += 1
                    return None
        return None
    
    
    def get_repo_contents(self, path: str = "") -> Optional[Union[Dict, List[Dict]]]:
        """Repository iceriğini getir"""
        safe_path = quote(path or "", safe="/")
        url = f"https://api.github.com/repos/{self.config.github_user}/{self.config.github_repo}/contents/{safe_path}"
        if self.config.github_branch:  url += f"?ref={self.config.github_branch}"
        response = self._make_request(url)
        if not response: return None
        try: return response.json()
        except Exception as e:
            logger.error(f"JSON parse hatasi: {e}")
            logger.error(f"Response: {response.text}")
            try: logger.error(f"Response (snippet): {response.text[:1000]}")
            except Exception: pass
            self.stats['errors'] += 1
        return None

    def get_file_last_commit_date(self, file_path: str) -> Optional[datetime]:
        """Dosyanin son commit tarihini getir"""
        url = f"https://api.github.com/repos/{self.config.github_user}/{self.config.github_repo}/commits"
        params = { 'path': file_path, 'sha': self.config.github_branch, 'per_page': 1 }
        response = self._make_request(f"{url}?{urlencode(params)}")
        if not response: return None
        try:
            commits = response.json()
            if commits:
                commit_date = commits[0]['commit']['committer']['date']
                if parser: return parser.parse(commit_date)
                else:
                    try: return datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
                    except Exception: return None
        except Exception as e:
            logger.warning(f"Commit tarih parse edilemedi: {e}")
            return None
        return None
    
    
    def should_ignore_file(self, file_path: str) -> bool:
        """Dosyanin ignore edilip edilmeyeceğini kontrol et"""
        import fnmatch
        for pattern in self.config.ignore_patterns or []:
            if fnmatch.fnmatch(file_path, pattern) or fnmatch.fnmatch(Path(file_path).name, pattern) or Path(file_path).match(pattern): return True
            if pattern.endswith("/") and str(file_path).startswith(pattern.rstrip("/")): return True
        return False
    
    
    def download_file(self, file_info: Dict, local_path: str) -> bool:
        """Dosyayi indir (stream) ve atomik olarak kaydet.
        Metin/script uzantıları normalize edilir (utf-8, BOM kaldırma, LF newline).
        Binary dosyalar ham olarak yazılır.
        """
        try:
            local_path_p = Path(local_path)
            parent = local_path_p.parent
            if parent and not parent.exists(): parent.mkdir(parents=True, exist_ok=True)
            download_url = file_info.get("download_url")
            if download_url: response = self._make_request(download_url, stream=True)
            else:
                api_url = file_info.get("url") or file_info.get("html_url")
                if not api_url:
                    logger.error(f"Dosya için indirilebilecek URL yok: {file_info.get('path')}")
                    self.stats['errors'] += 1
                    return False
                response = self._make_request(api_url, stream=True, extra_headers={'Accept': 'application/vnd.github.v3.raw'})
            if not response: return False
            suffix = local_path_p.suffix  # Geçici dosyaya yaz (binary)
            with tempfile.NamedTemporaryFile(delete=False, dir=str(parent) if parent else None, suffix=suffix) as tmp:
                tmp_path = Path(tmp.name)
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk: tmp.write(chunk)
                tmp.flush()
            try:
                if suffix.lower() in {'.bat', '.cmd', '.sh', '.ps1', '.py', '.txt', '.md', '.json', '.yaml', '.yml', '.html', '.htm', '.css', '.js'}:
                    b, decoded = tmp_path.read_bytes(), None
                    for enc in ('utf-8-sig', 'utf-8', 'utf-16', 'latin-1'): # Denenecek enkodlar; utf-8-sig BOM'u temizler
                        try:
                            s = b.decode(enc) # Eğer içeriğinde NUL karakteri varsa muhtemelen binary -> skip decode
                            if '\x00' in s:
                                decoded = None
                                continue
                            decoded = s.replace('\r\n', '\n').replace('\r', '\n') # normalize newlines -> LF
                            break
                        except Exception: decoded = None
                    if decoded is not None:
                        tmp_path.write_text(decoded, encoding='utf-8', newline='\n') # yaz UTF-8 (BOM yok)
                    else: pass # decode edilemedi; bırak binary olarak
                # Binary dosyalar için olduğu gibi devam
            except Exception as e: logger.debug(f"encoding normalize hata: {e}")
            # Atomik taşımayı dene
            try:
                if local_path_p.exists():  # Eğer hedef zaten varsa üzerine yaz
                    try: local_path_p.unlink()
                    except Exception: pass
                shutil.move(str(tmp_path), str(local_path_p))
            except Exception as e:
                try: # fallback: copy then remove
                    shutil.copy2(str(tmp_path), str(local_path_p))
                    tmp_path.unlink(missing_ok=True)
                except Exception as e2:
                    logger.error(f"Dosya hedefe taşınamadı: {local_path} - {e2}")
                    self.stats['errors'] += 1
                    return False
            # Unix'te script uzantılarını çalıştırılabilir yap
            try:
                if os.name != 'nt' and suffix.lower() in {'.sh', '.py'}:
                    mode = os.stat(local_path_p).st_mode
                    os.chmod(local_path_p, mode | 0o111)
            except Exception: pass
            logger.info(f"Indirildi: {os.path.relpath(str(local_path_p))}")
            self.stats['downloaded'] += 1
            return True
        except Exception as e:
            logger.error(f"Dosya indirilemedi {local_path}: {e}")
            self.stats['errors'] += 1
            return False

    
    def needs_update(self, file_info: Dict, local_path: str) -> bool:
        """Dosyanin guncellenmesi gerekip gerekmediğini kontrol et"""
        try:
            if not os.path.exists(local_path): return True
            github_date = self.get_file_last_commit_date(file_info.get('path', ''))
            if not github_date:
                logger.debug(f"GitHub tarih bilgisi alinamadi: {file_info.get('path')}")
                return True
            local_mtime = datetime.fromtimestamp(os.path.getmtime(local_path), tz=timezone.utc)
            github_date = github_date.replace(tzinfo=timezone.utc)
            return github_date > local_mtime
        except Exception as e:
            logger.warning(f"Tarih karsilastirmasi yapilamadi: {e}")
            return True


    def sync_directory(self, github_path: str = "", local_path: str = "") -> None:
        """Dizini senkronize et"""
        if not local_path:
            local_path = self.config.local_path or DEF_LOCAL_PATH
        contents = self.get_repo_contents(github_path)
        if not contents:
            logger.error(f"Icerik alinamadi: {github_path}")
            return
        # Tek dosya ise
        if isinstance(contents, dict) and contents.get('type') == 'file':
            if not self.should_ignore_file(contents.get('path', '')):
                parent = os.path.dirname(local_path)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                if self.needs_update(contents, local_path):
                    self.download_file(contents, local_path)
                else:
                    logger.debug(f"Guncel: {os.path.relpath(local_path)}")
                    self.stats['skipped'] += 1
            return
        # Beklenmeyen format
        if not isinstance(contents, list):
            logger.error(f"Beklenmeyen icerik formati: {github_path}")
            return
        # Dosyaları paralel, alt dizinleri senkron olarak işle
        with ThreadPoolExecutor(max_workers=int(self.config.max_workers or DEF_MAX_WORKERS)) as executor:
            futures = []
            for item in contents:
                if self.should_ignore_file(item.get('path', '')):
                    continue
                if item.get('type') == 'file':
                    futures.append(executor.submit(self.sync_item, item, local_path, github_path))
                else:
                    # Klasörleri hemen işle (derinlik-first, ama thread yaratmayalım)
                    try:
                        self.sync_item(item, local_path, github_path)
                    except Exception as e:
                        logger.error(f"Klasor senkron hatasi: {e}")
                        self.stats['errors'] += 1
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Paralel islem hatasi: {e}")
                    self.stats['errors'] += 1


    def _get_remote_script_content(self) -> Optional[bytes]:
        """GitHub repo'dan bu script'in raw içeriğini almaya çalışır (scripts/ öncelikli)."""
        candidates = [f"scripts/{Path(__file__).name}", Path(__file__).name]
        for p in candidates:
            try:
                contents = self.get_repo_contents(str(p))
                if isinstance(contents, dict):
                    dl = contents.get("download_url") or contents.get("url")
                    if dl:
                        resp = self._make_request(dl)
                        if resp: return resp.content
            except Exception as e: logger.debug(f"remote script alma hatasi ({p}): {e}")
        return None


    def self_update(self) -> bool:
        """
        Uzakta yeni bir sürüm varsa indirir ve yereldeki dosyanın üzerine atomik yazma yapar.
        Text dosyaları normalize edilir (utf-8, BOM kaldırma, newline '\n') ve onlara göre karşılaştırma yapılır.
        Eğer güncelleme yapılırsa process'i aynı argümanlarla yeniden başlatır (os.execv).
        Döner: True => güncelleme yapıldı (ve execv sonrası bu dönüş olmaz), False => değişiklik yok veya hata.
        """
        try:
            remote = self._get_remote_script_content()
            if not remote:
                logger.debug("Self-update: remote içerik alınamadı veya bulunamadı.")
                return False
            local_path = Path(__file__).resolve()
            def normalize_bytes(b: bytes) -> bytes:
                # Text dosyaları için decode denemeleri ve normalize -> utf-8 (BOM removed), newlines '\n'
                if local_path.suffix.lower() in {'.bat','.cmd','.sh','.ps1','.py','.txt','.md','.json','.yaml','.yml','.html','.htm','.css','.js'}:
                    for enc in ('utf-8-sig','utf-8','utf-16','latin-1'):
                        try: return b.decode(enc).replace('\r\n', '\n').replace('\r', '\n').encode('utf-8')
                        except Exception: continue
                    return b
                else: return b

            # Normalize remote bytes for comparison/writing if applicable
            try: normalized_remote = normalize_bytes(remote)
            except Exception: normalized_remote = remote
            # Read and normalize local if exists
            try:
                with open(local_path, "rb") as f:  local = f.read()
            except Exception as e:
                logger.warning(f"Self-update: local dosya okunamadi: {e}")
                local = b""
            try: normalized_local = normalize_bytes(local) if local else None
            except Exception: normalized_local = local
            # Compare normalized content hashes
            remote_hash = hashlib.sha256(normalized_remote).hexdigest()
            local_hash = hashlib.sha256(normalized_local).hexdigest() if normalized_local else None
            if local_hash == remote_hash:
                logger.debug("Self-update: zaten güncel (normalize edilmiş içerik aynı).")
                return False
            parent = local_path.parent
            with tempfile.NamedTemporaryFile(delete=False, dir=str(parent)) as tmp:
                tmp.write(normalized_remote)
                tmp_path = Path(tmp.name)
            shutil.move(str(tmp_path), str(local_path))
            logger.info("Self-update: script güncellendi. Şimdi yeniden başlatılıyor...")
            try: logging.shutdown()
            except Exception: pass
            # Aynı Python yorumlayıcısını ve argümanları kullanarak değiştir
            os.execv(sys.executable, [sys.executable, str(local_path)] + sys.argv[1:])
            return True
        except Exception as e:
            logger.error(f"Self-update hata: {e}")
            self.stats['errors'] += 1
            return False


    def print_stats(self):
        """Istatistikleri yazdir"""
        duration = time.time() - self.stats['start_time']
        logger.info("\n" + "=" * 50)
        logger.info("SENKRONIZASYON TAMAMLANDI")
        logger.info("=" * 50)
        logger.info(f"Indirilen dosya: {self.stats['downloaded']}")
        logger.info(f"Atlanilan dosya: {self.stats['skipped']}")
        logger.info(f"Hatali islem: {self.stats['errors']}")
        logger.info(f"Toplam sure: {duration:.2f} saniye")
        logger.info("=" * 50)



def setup_config():
    config = GitHubSyncConfig()
    env_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env_token: config.config['github_token'] = env_token
    # Eğer hala gerekli alanlar yoksa kullanıcıdan al (düşük etkileşim)
    if not config.github_user or not config.github_repo:
        try:
            github_user = input("GitHub kullanici adiniz: ").strip() or DEF_GITHUB_USER
            github_repo = input("Repository adi: ").strip() or DEF_GITHUB_REPO
            github_branch = input("Branch (varsayilan: main): ").strip() or config.github_branch or DEF_GITHUB_BRANCH
            local_path = input(f"Yerel klasor yolu (varsayilan: {DEF_LOCAL_PATH}): ").strip() or config.local_path or DEF_LOCAL_PATH
            github_token = input("GitHub token (opsiyonel, rate limit icin): ").strip() or config.github_token
            config.config.update({"github_user": github_user, "github_repo": github_repo, "github_branch": github_branch, "local_path": local_path, "github_token": github_token})
        except Exception as e: logger.error(f"\nKonfigurasyon hatasi: {e}\n")
    return config




def _log_config(config: GitHubSyncConfig):
    """Konfigurasyonu güvenli şekilde logla (token gizlenir)."""
    try:
        cfg = dict(config.config)
        # token'i maskele
        if 'github_token' in cfg and cfg['github_token']: cfg['github_token'] = '***masked***'
        try:
            lp = Path(cfg.get('local_path') or DEF_LOCAL_PATH)
            if not lp.is_absolute(): lp = (loc_p / lp).resolve()
            cfg['local_path'] = str(lp)
        except Exception:  pass
    except Exception as e: logger.debug(f"Konfig log hatasi: {e}")




def main():
    """Ana fonksiyon"""
    try:
        config = setup_config()
        # Log config hemen; token içeriği maskelenmiş olarak yazılacak
        _log_config(config)
        # Önce kendini güncelle (güncelleme varsa os.execv ile yeniden başlatılacak)
        sync_manager = GitHubSyncManager(config)
        try: sync_manager.self_update()
        except Exception as e: logger.debug(f"Self-update kontrolü hata: {e}")
        if not config.github_user or not config.github_repo:
            logger.error("GitHub kullanici adi ve repository adi gerekli!")
            return 1
        logger.info(f"Senkronizasyon baslatiliyor: {config.github_user}/{config.github_repo}")
        logger.info(f"Hedef klasor: {config.local_path}")
        sync_manager.sync_directory()
        sync_manager.print_stats()
        return 0
    except KeyboardInterrupt:
        logger.info("\nSenkronizasyon kullanici tarafindan durduruldu.")
        return 1
    except Exception as e:
        logger.error(f"Beklenmeyen hata: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
