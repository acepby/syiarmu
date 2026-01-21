import time
import random
import threading
import cloudscraper
import instaloader
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from collections import Counter
from extensions import db
from models import Organization, Post, ActivityLog

# KONFIGURASI
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Safari/605.1.15'
]
LIMIT_PER_HOUR = 30
LIMIT_PER_DAY = 180
DELAY_MIN = 41
DELAY_MAX = 97
IG_SESSION_USER = "syiar_mu"

# GLOBAL STATE
scan_status = {'status': 'Idle', 'last_log': 'System ready', 'next_run': 'Now'}

class RateLimiter:
    def __init__(self):
        self.hourly_count = 0
        self.daily_count = 0
        self.last_reset_hour = datetime.now().hour
        self.last_reset_day = datetime.now().day
        self.lock = threading.Lock()

    def check_and_increment(self):
        with self.lock:
            now = datetime.now()
            if now.hour != self.last_reset_hour:
                self.hourly_count = 0; self.last_reset_hour = now.hour
            if now.day != self.last_reset_day:
                self.daily_count = 0; self.last_reset_day = now.day
            
            if self.hourly_count >= LIMIT_PER_HOUR: return False, "Hourly Limit"
            if self.daily_count >= LIMIT_PER_DAY: return False, "Daily Limit"
            
            self.hourly_count += 1
            self.daily_count += 1
            return True, "OK"

    def get_status(self):
        return {"hourly": f"{self.hourly_count}/{LIMIT_PER_HOUR}", "daily": f"{self.daily_count}/{LIMIT_PER_DAY}"}

limiter = RateLimiter()

def calculate_word_freq(source_name):
    posts = Post.query.filter_by(source=source_name).order_by(Post.id.desc()).with_entities(Post.title).all()
    if not posts: return [], []
    text_combined = " ".join([p.title for p in posts if p.title]).lower()
    text_combined = re.sub(r'https?://\S+|www\.\S+', '', text_combined) 
    text_combined = re.sub(r'\d+', '', text_combined)     
    text_combined = re.sub(r'[^\w\s]', '', text_combined) 
    words = text_combined.split()
    stopwords = set(['beri','berikan','sebut','diri','tetapi','saja','sekadar','segini','para','terus','dan', 'yang', 'di', 'ke', 'dari', 'ini', 'itu', 'untuk', 'pada', 'dengan', 'adalah', 'sebagai', 'karena', 'oleh', 'muhammadiyah', 'pwm', 'pimpinan', 'wilayah', 'daerah', 'cabang', 'ranting', 'kota', 'kabupaten', 'dalam', 'atas', 'bagi', 'juga', 'bisa', 'ada', 'tidak', 'saat', 'akan', 'atau', 'kami', 'kita', 'saya', 'anda', 'link', 'bio', 'klik', 'profil', 'kegiatan', 'bersama', 'selamat', 'tahun', 'hari', 'tanggal', '2024', '2025', 'https', 'http', 'read', 'more', 'post', 'posted', 'by', 'admin', 'news', 'berita', 'update', 'terbaru', 'caption', 'recent', 'posts', 'more', 'view', 'video', 'foto', 'reels', 'selengkapnya', 'assalamualaikum', 'waalaikumsalam', 'warahmatullahi', 'wabarakatuh', 'yogyakarta', 'surakarta', 'jakarta', 'indonesia', 'resmi', 'official','telah','setiap','harus','hingga','sampai','serta','semoga','mari','seluruh','lebih','melalui','setiap','jadi','menjadi','baru','semua','dapat','mereka','kini','kepada','masih','menuju','bukan','agar','hanya','tapi','setiap','saudarasaudara','belum','ketika','segera','secara','jangan','tersebut','sudah','tertentu','sebanyak','tetap','apakah','merupakan'])
    filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
    most_common = Counter(filtered_words).most_common(100) 
    if not most_common: return [], []
    return [w[0] for w in most_common], [w[1] for w in most_common]

def get_safe_instaloader_context():
    L = instaloader.Instaloader(user_agent=random.choice(USER_AGENTS), max_connection_attempts=1, request_timeout=10, fatal_status_codes=[401, 429])
    if IG_SESSION_USER:
        try: L.load_session_from_file(IG_SESSION_USER)
        except: pass
    return L

def scrape_instagram_safe(org_id, url):
    allowed, msg = limiter.check_and_increment()
    if not allowed: return 0, msg
    try:
        username = urlparse(url).path.strip('/').split('/')[0]
        L = get_safe_instaloader_context()
        time.sleep(random.randint(DELAY_MIN, DELAY_MAX))
        profile = instaloader.Profile.from_username(L.context, username)
        posts = profile.get_posts()
        
        # 1. Ambil URL yang sudah ada di DB untuk org ini (Optimasi)
        existing_urls = {
            res.url for res in db.session.query(Post.url).filter_by(org_id=org_id).all()
        }

        added = []
        for i, post in enumerate(posts):
            if i >= 3: break
            post_url = f"https://www.instagram.com/p/{post.shortcode}/"
            
            # 2. Cek di Python Set (Sangat Cepat & Hemat Koneksi DB)
            if post_url not in existing_urls:
                caption = post.caption if post.caption else "No Caption"
                title = (caption[:400] + '..') if len(caption) > 400 else caption
                added.append(Post(org_id=org_id, source='Instagram', title=title, url=post_url, fetched_at=post.date_utc))
                existing_urls.add(post_url) # Tambahkan ke set sementara agar tidak duplikat di loop yang sama
        
        if added:
            db.session.add_all(added)
            db.session.commit()
        return len(added), "OK"
    except Exception as e: return 0, str(e)[:200]

def scrape_website(org_id, url):
    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=20)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # PERUBAHAN 1: Kita cari Heading (h1-h6) DAN tag 'a' sekaligus
            candidates = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a'], limit=50)
            
            existing_urls = {
                res.url for res in db.session.query(Post.url).filter_by(org_id=org_id).all()
            }

            added = []
            for tag in candidates:
                link = None
                text = ""

                # --- LOGIKA A: Struktur Standar (<h2><a href="...">Judul</a></h2>) ---
                if tag.name.startswith('h'):
                    a_tag = tag.find('a')
                    if a_tag:
                        link = a_tag.get('href')
                        text = a_tag.get_text().strip()
                        # Kadang text ada di h2, bukan di a
                        if not text: text = tag.get_text().strip()

                # --- LOGIKA B: Struktur Modern (<a class="h5 title">Judul</a>) ---
                elif tag.name == 'a':
                    # Ambil daftar class dari tag <a> tersebut
                    css_classes = tag.get('class', []) # Mengembalikan list, misal ['h5', 'card-title']
                    
                    # Jika tidak punya class, kemungkinan besar bukan judul (cuma link biasa)
                    if not css_classes:
                        continue
                        
                    # Gabung class jadi string agar mudah dicek
                    class_str = " ".join(css_classes).lower()
                    
                    # Cek Kata Kunci: Apakah class mengandung indikator judul?
                    # Kita cari 'h5', 'h4', 'title', 'headline', 'post'
                    is_title_candidate = any(x in class_str for x in ['h1','h2','h3','h4','h5','h6', 'title', 'headline', 'news-link'])
                    
                    if is_title_candidate:
                        link = tag.get('href')
                        text = tag.get_text().strip()

                # --- PROSES VALIDASI & SIMPAN (Sama seperti sebelumnya) ---
                if link and text:
                    # Normalisasi Link
                    if not link.startswith('http'): 
                        base = "{0.scheme}://{0.netloc}".format(urlparse(url))
                        link = base.rstrip('/') + '/' + link.lstrip('/')
                    
                    # Filter Kualitas
                    if len(text) > 15 and link not in existing_urls:
                        # Membersihkan text dari newlines berlebih
                        clean_title = " ".join(text.split())
                        added.append(Post(org_id=org_id, source='Website', title=clean_title, url=link))
                        existing_urls.add(link) # Cegah duplikat di loop yg sama

            if added:
                db.session.add_all(added)
                db.session.commit()
            return len(added), "OK"
            
    except Exception as e: return 0, str(e)[:50]
    return 0, "Failed"

def worker_loop(app_instance):
    global scan_status
    DATA_FRESHNESS_HOURS = 3
    while True:
        with app_instance.app_context():
            try:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=DATA_FRESHNESS_HOURS)
                target = Organization.query.filter((Organization.last_scraped_at < cutoff) | (Organization.last_scraped_at == None)).order_by(Organization.last_scraped_at.asc()).first()
                if not target:
                    long_sleep = random.randint(600, 900)
                    scan_status['status'] = f"Idle. Sleeping {long_sleep//60} mins..."
                    time.sleep(long_sleep); continue
                if limiter.hourly_count >= LIMIT_PER_HOUR:
                    time.sleep(1800); continue

                scan_status['status'] = f"Processing: {target.name}"
                w_msg, i_msg = "-", "-"
                
                if target.website_link:
                    wc, w_msg = scrape_website(target.id, target.website_link)
                    if wc > 0: db.session.add(ActivityLog(org_id=target.id, source='Website', post_count=wc, status_msg=w_msg))
                if target.instagram_link:
                    ic, i_msg = scrape_instagram_safe(target.id, target.instagram_link)
                    if ic > 0: db.session.add(ActivityLog(org_id=target.id, source='Instagram', post_count=ic, status_msg=i_msg))
                
                target.last_scraped_at = datetime.now(timezone.utc)
                db.session.commit()
                scan_status['last_log'] = f"Done {target.name}. Web: {w_msg}, IG: {i_msg}"
                time.sleep(random.randint(DELAY_MIN, DELAY_MAX))
            except Exception as e:
                print(f"Worker Error: {e}"); db.session.rollback(); time.sleep(DELAY_MAX)
            finally: db.session.remove()
