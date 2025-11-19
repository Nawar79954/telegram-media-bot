import os
import sys
import logging
import tempfile
import re
import time
import urllib.parse
import threading
import shutil
import subprocess
import glob
import requests
import json
import random

# ========== إعدادات السحابة المتقدمة ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/bot.log')
    ]
)
logger = logging.getLogger(__name__)

print("🚀 بدء تشغيل بوت الوسائط المتقدم على Railway...")

# ========== تثبيت الحزم المطلوبة ==========
def install_required_packages():
    """تثبيت جميع الحزم المطلوبة"""
    packages = [
        'pyTelegramBotAPI',
        'yt-dlp', 
        'pillow',
        'requests',
        'psutil'
    ]
    
    for package in packages:
        try:
            if package == 'pyTelegramBotAPI':
                import telebot
                print("✅ telebot - مثبت بالفعل")
            elif package == 'yt-dlp':
                import yt_dlp
                print("✅ yt-dlp - مثبت بالفعل")
            elif package == 'pillow':
                from PIL import Image
                print("✅ pillow - مثبت بالفعل")
            elif package == 'requests':
                import requests
                print("✅ requests - مثبت بالفعل")
            elif package == 'psutil':
                import psutil
                print("✅ psutil - مثبت بالفعل")
        except ImportError:
            print(f"📦 جاري تثبيت {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_required_packages()

# ========== استيراد المكتبات ==========
import telebot
from telebot import types
import yt_dlp
from PIL import Image, ImageFilter, ImageEnhance
import psutil

# ========== التهيئة ==========
API_TOKEN = os.environ.get('BOT_TOKEN')
if not API_TOKEN:
    print("❌ خطأ: لم يتم العثور على BOT_TOKEN في متغيرات البيئة!")
    sys.exit(1)

print(f"✅ تم تحميل توكن البوت بنجاح")

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# المجلد المؤقت للسحابة
TEMP_DIR = "/tmp/telegram_bot_files"
os.makedirs(TEMP_DIR, exist_ok=True)

CLOUD_DEPLOYMENT = 'RAILWAY_ENVIRONMENT' in os.environ

print(f"🌐 النشر السحابي: {CLOUD_DEPLOYMENT}")
print(f"📁 المجلد المؤقت: {TEMP_DIR}")

# ========== إدارة المستخدمين ==========
user_states = {}
user_sessions = {}

# ========== إعداد FFmpeg المحسن ==========
def setup_environment():
    """إعداد البيئة بما في ذلك FFmpeg مع تحسينات السحابة"""
    try:
        # في Railway، حاول تثبيت ffmpeg تلقائياً
        if CLOUD_DEPLOYMENT:
            print("🔧 جاري التحقق من FFmpeg في بيئة Railway...")
            try:
                # محاولة تثبيت ffmpeg باستخدام apt
                result = subprocess.run(['apt-get', 'update'], capture_output=True, text=True)
                result = subprocess.run(['apt-get', 'install', '-y', 'ffmpeg'], capture_output=True, text=True)
                if result.returncode == 0:
                    print("✅ تم تثبيت FFmpeg بنجاح في Railway")
            except Exception as e:
                print(f"⚠️ لا يمكن تثبيت FFmpeg تلقائياً: {e}")

        # التحقق من وجود FFmpeg
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode == 0:
            # اختبار FFmpeg
            test_result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=10)
            if test_result.returncode == 0:
                print("✅ FFmpeg متاح ويعمل بشكل صحيح")
                return True
            else:
                print("⚠️ FFmpeg موجود لكن لا يعمل بشكل صحيح")
                return False
        else:
            print("🔧 جاري البحث عن FFmpeg في المسارات البديلة...")
            # البحث في مسارات بديلة
            possible_paths = [
                '/usr/bin/ffmpeg',
                '/usr/local/bin/ffmpeg',
                '/app/bin/ffmpeg',
                '/opt/bin/ffmpeg'
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    print(f"✅ تم العثور على FFmpeg في: {path}")
                    # إضافة إلى PATH
                    os.environ["PATH"] = os.path.dirname(path) + os.pathsep + os.environ["PATH"]
                    return True
            
            print("⚠️ FFmpeg غير موجود، سيتم استخدام الميزات الأساسية فقط")
            return False
    except Exception as e:
        print(f"❌ خطأ في إعداد البيئة: {e}")
        return False

FFMPEG_AVAILABLE = setup_environment()

# ========== نظام التنظيف التلقائي ==========
class AutoCleanup:
    def __init__(self):
        self.is_running = False
        self.cleanup_thread = None
    
    def start_auto_cleanup(self):
        """بدء التنظيف التلقائي كل ساعة"""
        if self.is_running:
            return
        
        self.is_running = True
        self.cleanup_thread = threading.Thread(target=self._cleanup_scheduler, daemon=True)
        self.cleanup_thread.start()
        logger.info("🚀 بدء نظام التنظيف التلقائي")
    
    def _cleanup_scheduler(self):
        """جدولة التنظيف"""
        while self.is_running:
            try:
                deleted_files = self.cleanup_temp_files()
                if deleted_files > 0:
                    logger.info(f"🧹 التنظيف التلقائي - تم حذف {deleted_files} ملف")
                
                # في السحابة، تنظيف أكثر تكراراً
                sleep_time = 1800 if CLOUD_DEPLOYMENT else 3600
                time.sleep(sleep_time)
            except Exception as e:
                logger.error(f"خطأ في التنظيف التلقائي: {e}")
                time.sleep(300)
    
    def stop_auto_cleanup(self):
        """إيقاف التنظيف التلقائي"""
        self.is_running = False
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        logger.info("🛑 إيقاف التنظيف التلقائي")
    
    def cleanup_temp_files(self, max_age_minutes=30):
        """تنظيف الملفات المؤقتة"""
        try:
            current_time = time.time()
            deleted_files = 0
            total_size = 0
            
            if not os.path.exists(TEMP_DIR):
                return 0
            
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(file_path):
                    try:
                        file_age = current_time - os.path.getctime(file_path)
                        file_age_minutes = file_age / 60
                        
                        # في السحابة، تنظيف الملفات الأقدم من 30 دقيقة
                        cloud_max_age = 30 if CLOUD_DEPLOYMENT else max_age_minutes
                        if file_age_minutes > cloud_max_age:
                            file_size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            deleted_files += 1
                            total_size += file_size
                    except Exception as e:
                        logger.error(f"خطأ في حذف {filename}: {e}")
            
            if deleted_files > 0:
                size_mb = total_size / (1024 * 1024)
                logger.info(f"🧹 تم حذف {deleted_files} ملف مؤقت ({size_mb:.2f} ميجابايت)")
            
            return deleted_files
            
        except Exception as e:
            logger.error(f"خطأ في التنظيف: {e}")
            return 0

# تهيئة نظام التنظيف التلقائي
auto_cleanup = AutoCleanup()

# ========== دوال المساعدة ==========
def is_valid_url(url):
    """التحقق من صحة الرابط مع دعم النطاقات الشاملة"""
    try:
        url = url.strip()
        if not url:
            return False
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # تحليل الرابط
        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.lower()
        
        # إزالة www. إذا كانت موجودة
        if domain.startswith('www.'):
            domain = domain[4:]
        
        # النطاقات المدعومة الموسعة
        supported_domains = {
            'youtube.com', 'youtu.be', 'm.youtube.com', 'music.youtube.com',
            'youtube-nocookie.com', 'gaming.youtube.com',
            'instagram.com', 'www.instagram.com',
            'facebook.com', 'fb.com', 'fb.watch', 'www.facebook.com',
            'tiktok.com', 'vm.tiktok.com', 'www.tiktok.com',
            'twitter.com', 'x.com', 'www.twitter.com',
            'reddit.com', 'www.reddit.com', 'v.redd.it',
            'soundcloud.com', 'www.soundcloud.com',
            'spotify.com', 'open.spotify.com',
            'vimeo.com', 'www.vimeo.com',
            'dailymotion.com', 'www.dailymotion.com',
            'twitch.tv', 'www.twitch.tv',
            'bilibili.com', 'www.bilibili.com',
            'nicovideo.jp', 'www.nicovideo.jp',
            'rutube.ru', 'www.rutube.ru'
        }
        
        # التحقق مما إذا كان النطاق مدعومًا
        if domain not in supported_domains:
            return False
            
        # التحقق الأساسي من تنسيق الرابط
        url_pattern = re.compile(
            r'^(?:http|ftp)s?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        
        return re.match(url_pattern, url) is not None
        
    except Exception as e:
        logger.error(f"خطأ في التحقق من صحة الرابط '{url}': {e}")
        return False

def get_file_size(file_path):
    """الحصول على حجم الملف بصيغة مقروءة"""
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "غير معروف"

def clean_filename(filename):
    """تنظيف اسم الملف من الأحرف غير الصالحة"""
    if not filename:
        return "غير معروف"
    return re.sub(r'[<>:"/\\|?*]', '', filename)

def format_duration(duration):
    """تنسيق المدة من الثواني إلى MM:SS"""
    try:
        if duration is None:
            return "غير معروف"
        duration = int(duration)
        minutes = duration // 60
        seconds = duration % 60
        return f"{minutes}:{seconds:02d}"
    except:
        return "غير معروف"

def test_url_with_ytdlp(url):
    """اختبار ما إذا كان الرابط يمكن الوصول إليه باستخدام yt-dlp"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'extract_flat': True,
            'socket_timeout': 15,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info is not None
    except Exception as e:
        logger.error(f"فشل اختبار الرابط لـ {url}: {e}")
        return False

# ========== إعدادات yt-dlp المحسنة ==========
def get_ydl_opts(download_type='video', is_fast=False):
    """الحصول على خيارات yt-dlp بناءً على نوع التنزيل مع تحسينات السحابة"""
    
    # وكلاء مستخدم عشوائيون لتجنب الحظر
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]
    
    base_opts = {
        'outtmpl': os.path.join(TEMP_DIR, '%(title).100s.%(ext)s'),
        'retries': 10,  # زيادة عدد المحاولات
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ignoreerrors': False,
        'quiet': True,
        'socket_timeout': 60,  # زيادة وقت الانتظار
        'noplaylist': True,
        
        # إضافة رؤوس HTTP لتجنب الحظر
        'http_headers': {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        },
    }
    
    if download_type == 'audio':
        if FFMPEG_AVAILABLE:
            base_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
            })
        else:
            # خيارات بديلة عندما لا يكون FFmpeg متاحاً
            base_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
    elif is_fast:
        base_opts.update({
            'format': 'worst[height<=480]/worst',  # جودة أقل لسرعة أكبر
        })
    else:
        base_opts.update({
            'format': 'best[height<=720]/best[height<=480]/best',
        })
    
    return base_opts

# ========== نظام التنزيل المحسن ==========
def download_media(url, chat_id, download_type='video', is_fast=False):
    """تنزيل الوسائط مع معالجة الأخطاء الشاملة وتحسينات السحابة"""
    max_retries = 3  # زيادة عدد المحاولات
    for attempt in range(max_retries):
        try:
            bot.send_message(chat_id, f"🔄 جاري المعالجة (المحاولة {attempt + 1}/{max_retries})...")
            
            ydl_opts = get_ydl_opts(download_type, is_fast)
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # الحصول على معلومات الفيديو أولاً
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("لا يمكن الحصول على معلومات الفيديو")
                
                title = clean_filename(info.get('title', 'غير معروف'))
                duration = info.get('duration', 0)
                
                if duration > 1800:  # أكثر من 30 دقيقة
                    bot.send_message(chat_id, "⚠️ فيديو طويل - قد يستغرق هذا بعض الوقت")
                
                bot.send_message(chat_id, f"📥 جاري التنزيل: {title}")
                
                # بدء التنزيل
                ydl.download([url])
                
                # العثور على الملف الذي تم تنزيله
                file_pattern = os.path.join(TEMP_DIR, f"{title}.*")
                files = glob.glob(file_pattern)
                
                if files:
                    file_path = files[0]
                    # التحقق من أن الملف ليس فارغاً
                    if os.path.getsize(file_path) > 1024:  # 1KB كحد أدنى
                        return info, file_path
                    else:
                        os.unlink(file_path)  # حذف الملف الفارغ
                        raise Exception("الملف الذي تم تنزيله فارغ")
                else:
                    # الاحتياطي: الحصول على أحدث ملف في المجلد المؤقت
                    all_files = glob.glob(os.path.join(TEMP_DIR, "*"))
                    if all_files:
                        latest_file = max(all_files, key=os.path.getctime)
                        if os.path.getsize(latest_file) > 1024:
                            return info, latest_file
                        else:
                            raise Exception("أحدث ملف فارغ")
                    else:
                        raise Exception("الملف الذي تم تنزيله غير موجود")
                    
        except Exception as e:
            error_msg = str(e)
            logger.error(f"فشلت محاولة التنزيل {attempt + 1}: {error_msg}")
            
            # التعامل مع الأخطاء المتعلقة بـ FFmpeg
            if "ffprobe" in error_msg.lower() or "ffmpeg" in error_msg.lower():
                bot.send_message(chat_id, "❌ خطأ في FFmpeg! جاري التنزيل بدون تحويل...")
                ydl_opts = get_ydl_opts('audio', is_fast)
                if 'postprocessors' in ydl_opts:
                    del ydl_opts['postprocessors']
                
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.download([url])
                        files = glob.glob(os.path.join(TEMP_DIR, "*"))
                        if files:
                            latest_file = max(files, key=os.path.getctime)
                            if os.path.getsize(latest_file) > 1024:
                                return info, latest_file
                except Exception as inner_e:
                    logger.error(f"فشل التنزيل بدون FFmpeg: {inner_e}")
                    if attempt < max_retries - 1:
                        continue
                    else:
                        raise inner_e
                
            if attempt < max_retries - 1:
                bot.send_message(chat_id, f"⚠️ جاري إعادة المحاولة... (المحاولة {attempt + 2}/{max_retries})")
                time.sleep(3)  # زيادة وقت الانتظار بين المحاولات
            else:
                raise e
    
    return None, None

def process_download(chat_id, url, media_type, is_fast=False):
    """معالجة التنزيل مع معالجة الأخطاء الشاملة"""
    try:
        bot.send_message(chat_id, "🔍 جاري التحقق من الرابط...")
        
        # التحقق من صحة الرابط
        if not is_valid_url(url):
            bot.send_message(chat_id, "❌ تنسيق رابط غير صالح أو منصة غير مدعومة")
            send_welcome_by_id(chat_id)
            return
        
        # اختبار إمكانية الوصول إلى الرابط
        bot.send_message(chat_id, "🌐 جاري اختبار الاتصال...")
        if not test_url_with_ytdlp(url):
            bot.send_message(chat_id, "❌ لا يمكن الوصول إلى هذا الرابط أو المحتوى غير متاح")
            send_welcome_by_id(chat_id)
            return
        
        # تحديد نوع التنزيل
        if media_type == 'audio':
            action_msg = "🎵 جاري استخراج الصوت..."
            download_type = 'audio'
            
            # إضافة معلومات حول حالة FFmpeg
            if not FFMPEG_AVAILABLE:
                action_msg += "\n\n⚠️ **ملاحظة:** FFmpeg غير متاح - سيتم التنزيل بالتنسيق الأصلي للصوت"
        elif is_fast:
            action_msg = "⚡ بدء التنزيل السريع..."
            download_type = 'video'
        else:
            action_msg = "📥 بدء التنزيل..."
            download_type = 'video'
        
        bot.send_message(chat_id, action_msg, parse_mode='Markdown')
        bot.send_chat_action(chat_id, 'upload_video' if media_type != 'audio' else 'upload_audio')
        
        # تنزيل الوسائط
        info, file_path = download_media(url, chat_id, download_type, is_fast)
        
        if info and file_path and os.path.exists(file_path):
            file_size = get_file_size(file_path)
            title = clean_filename(info.get('title', 'غير معروف'))
            
            # التحقق النهائي من حجم الملف
            if os.path.getsize(file_path) < 1024:
                bot.send_message(chat_id, "❌ الملف الذي تم تنزيله فارغ أو صغير جداً")
                try:
                    os.unlink(file_path)
                except:
                    pass
                send_welcome_by_id(chat_id)
                return
            
            caption = f"✅ اكتمل التنزيل!\n🎬 {title}\n📊 الحجم: {file_size}"
            
            if media_type == 'audio' and not FFMPEG_AVAILABLE:
                caption += "\n⚠️ التنسيق الأصلي (FFmpeg غير متاح)"
            
            bot.send_message(chat_id, "📤 جاري رفع الملف...")
            
            try:
                if media_type == 'audio':
                    with open(file_path, 'rb') as audio_file:
                        if file_path.endswith(('.m4a', '.webm', '.opus')):
                            bot.send_document(chat_id, audio_file, caption=caption, timeout=120)
                        else:
                            bot.send_audio(chat_id, audio_file, caption=caption, timeout=120, title=title[:64])
                else:
                    with open(file_path, 'rb') as video_file:
                        bot.send_video(chat_id, video_file, caption=caption, timeout=120, supports_streaming=True)
                        
            except Exception as send_error:
                logger.error(f"خطأ في الرفع: {send_error}")
                # الاحتياطي: الإرسال كمستند
                try:
                    with open(file_path, 'rb') as doc_file:
                        bot.send_document(chat_id, doc_file, caption=caption, timeout=120)
                except Exception as doc_error:
                    logger.error(f"خطأ في رفع المستند: {doc_error}")
                    bot.send_message(chat_id, f"❌ فشل الرفع: {str(send_error)[:100]}")
            
            # تنظيف الملف الذي تم تنزيله
            try:
                os.unlink(file_path)
                logger.info(f"تم التنظيف: {file_path}")
            except Exception as e:
                logger.error(f"خطأ في التنظيف: {e}")
                
        else:
            bot.send_message(chat_id, "❌ فشل التنزيل - لم يتم استلام أي محتوى")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"خطأ في معالجة التنزيل: {error_msg}")
        
        # رسائل خطأ سهلة الفهم
        error_messages = {
            "Private video": "❌ فيديو خاص - لا يمكن الوصول",
            "Video unavailable": "❌ الفيديو غير متاح أو محذوف",
            "Sign in": "❌ المحتوى يتطلب تسجيل الدخول",
            "HTTP Error 403": "❌ تم حظر الوصول من هذا الموقع",
            "Unsupported URL": "❌ منصة غير مدعومة أو رابط",
            "No video formats": "❌ لم يتم العثور على تنسيق قابل للتشغيل",
            "This video is unavailable": "❌ الفيديو غير متاح في منطقتك",
            "Unable to download webpage": "❌ لا يمكن الوصول إلى هذا الرابط",
            "Video unavailable": "❌ الفيديو لم يعد متاحًا",
            "File is empty": "❌ الملف الناتج فارغ - قد يكون المحتوى محمياً"
        }
        
        for key, message in error_messages.items():
            if key in error_msg:
                bot.send_message(chat_id, message)
                break
        else:
            # رسالة خطأ عامة
            error_display = str(e)[:150]
            bot.send_message(chat_id, f"❌ خطأ: {error_display}")
    
    finally:
        send_welcome_by_id(chat_id)

# ========== نظام القائمة الرئيسية ==========
@bot.message_handler(commands=['start', 'help', 'menu'])
def send_welcome(message):
    user_states[message.chat.id] = 'main'
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('🔄 تحويل الصيغ')
    btn2 = types.KeyboardButton('📥 تنزيل عادي')
    btn3 = types.KeyboardButton('⚡ تنزيل سريع')
    btn4 = types.KeyboardButton('🎵 تنزيل صوت')
    btn5 = types.KeyboardButton('🔍 بحث أغنية')
    btn6 = types.KeyboardButton('ℹ️ المساعدة والمعلومات')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    ffmpeg_status = "✅ متاح" if FFMPEG_AVAILABLE else "❌ غير متاح"
    cloud_status = "🌐 سحابة Railway" if CLOUD_DEPLOYMENT else "💻 محلي"
    
    welcome_text = f"""
🎉 **مرحبًا بك في MediaBot Pro!**

⚡ **الميزات المتاحة:**

🔄 تحويل الصيغ - أدوات تحويل الصور/الفيديو
📥 تنزيل عادي - جودة عالية (720p) 
⚡ تنزيل سريع - جودة أقل (360p) للسرعة
🎵 تنزيل صوت - استخراج الصوت من الفيديوهات
🔍 بحث أغنية - البحث عن الموسيقى بالكلمات

🔧 **حالة النظام:**
النشر: {cloud_status}
FFmpeg: {ffmpeg_status}
التنظيف التلقائي: ✅ نشط

📋 **المنصات المدعومة:**
YouTube, Instagram, Facebook, TikTok, Twitter,
Reddit, SoundCloud, Spotify, Vimeo, Twitch والمزيد!

**اختر الوظيفة المطلوبة أدناه!**
    """
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=markup, parse_mode='Markdown')

def send_welcome_by_id(chat_id):
    """إرسال رسالة ترحيب باستخدام chat_id فقط"""
    try:
        user_states[chat_id] = 'main'
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        btn1 = types.KeyboardButton('🔄 تحويل الصيغ')
        btn2 = types.KeyboardButton('📥 تنزيل عادي')
        btn3 = types.KeyboardButton('⚡ تنزيل سريع')
        btn4 = types.KeyboardButton('🎵 تنزيل صوت')
        btn5 = types.KeyboardButton('🔍 بحث أغنية')
        btn6 = types.KeyboardButton('ℹ️ المساعدة والمعلومات')
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
        
        bot.send_message(chat_id, "🎛️ اختر الإجراء التالي:", reply_markup=markup)
    except Exception as e:
        logger.error(f"خطأ في رسالة الترحيب: {e}")

# ========== معالجات التنزيل ==========
@bot.message_handler(func=lambda message: message.text in ['📥 تنزيل عادي', '⚡ تنزيل سريع', '🎵 تنزيل صوت'])
def handle_download_request(message):
    chat_id = message.chat.id
    
    download_type = {
        '📥 تنزيل عادي': 'normal',
        '⚡ تنزيل سريع': 'fast', 
        '🎵 تنزيل صوت': 'audio'
    }[message.text]
    
    user_states[chat_id] = f'waiting_url_{download_type}'
    
    type_names = {
        'normal': 'جودة عادية 🎥',
        'fast': 'تنزيل سريع ⚡', 
        'audio': 'صوت فقط 🎵'
    }
    
    # معلومات إضافية بناءً على النوع
    extra_info = ""
    if download_type == 'audio' and not FFMPEG_AVAILABLE:
        extra_info = "\n\n⚠️ **ملاحظة:** FFmpeg غير متاح - التنزيل بتنسيق الصوت الأصلي"
    
    platforms_list = "\n\n📋 **المدعومة:** YouTube, Instagram, Facebook, TikTok, Twitter, Reddit, SoundCloud, Spotify, Vimeo, Twitch"
    
    bot.send_message(chat_id, 
                   f"**{type_names[download_type]}**\n\nيرجى إرسال رابط الفيديو:{extra_info}{platforms_list}",
                   reply_markup=types.ReplyKeyboardRemove(),
                   parse_mode='Markdown')

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, '').startswith('waiting_url_'))
def handle_url_input(message):
    chat_id = message.chat.id
    url = message.text.strip()
    
    current_state = user_states.get(chat_id, '')
    if not current_state.startswith('waiting_url_'):
        return
        
    download_type = current_state.replace('waiting_url_', '')
    is_fast = download_type == 'fast'
    media_type = 'audio' if download_type == 'audio' else 'video'
    
    user_states[chat_id] = 'processing'
    
    # بدء التنزيل في thread منفصل
    thread = threading.Thread(target=process_download, args=(chat_id, url, media_type, is_fast))
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 بدء عملية التنزيل...")

# ========== نظام تحويل الصيغ ==========
@bot.message_handler(func=lambda message: message.text == '🔄 تحويل الصيغ')
def handle_convert(message):
    user_states[message.chat.id] = 'convert'
    
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    btn1 = types.KeyboardButton('📷 صورة إلى PDF')
    btn2 = types.KeyboardButton('🎵 فيديو إلى MP3')
    btn3 = types.KeyboardButton('🖼️ صورة إلى JPG')
    btn_back = types.KeyboardButton('🔙 القائمة الرئيسية')
    markup.add(btn1, btn2, btn3, btn_back)
    
    ffmpeg_info = ""
    if not FFMPEG_AVAILABLE:
        ffmpeg_info = "\n\n⚠️ **تحويل الفيديو إلى MP3 يتطلب FFmpeg** (انظر /ffmpeg_help)"
    
    bot.send_message(message.chat.id, f"**أدوات تحويل الصيغ**{ffmpeg_info}", 
                   reply_markup=markup, parse_mode='Markdown')

# تحويل الصورة إلى PDF
@bot.message_handler(func=lambda message: message.text == '📷 صورة إلى PDF')
def handle_image_to_pdf(message):
    user_states[message.chat.id] = 'waiting_image_pdf'
    bot.send_message(message.chat.id, "📤 يرجى إرسال الصورة التي تريد تحويلها إلى PDF", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.chat.id) == 'waiting_image_pdf')
def process_image_to_pdf(message):
    try:
        bot.send_message(message.chat.id, "⏳ جاري معالجة صورتك...")
        
        # الحصول على أعلى جودة للصورة
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # حفظ الصورة المؤقتة
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg', dir=TEMP_DIR) as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name
        
        pdf_path = None
        try:
            # فتح ومعالجة الصورة
            image = Image.open(temp_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # إنشاء PDF
            pdf_path = temp_path.replace('.jpg', '.pdf')
            image.save(pdf_path, "PDF", resolution=100.0, quality=95)
            
            file_size = get_file_size(pdf_path)
            
            # إرسال PDF إلى المستخدم
            with open(pdf_path, 'rb') as pdf_file:
                bot.send_document(message.chat.id, pdf_file, 
                                caption=f"✅ تم التحويل إلى PDF بنجاح!\n📊 حجم الملف: {file_size}")
            
        except Exception as e:
            logger.error(f"خطأ في تحويل PDF: {e}")
            bot.send_message(message.chat.id, f"❌ فشل التحويل: {str(e)}")
        
        finally:
            # تنظيف الملفات المؤقتة
            for path in [temp_path, pdf_path]:
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except Exception as e:
                    logger.error(f"خطأ في التنظيف {path}: {e}")
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الصورة: {e}")
        bot.send_message(message.chat.id, f"❌ خطأ في المعالجة: {str(e)}")
    
    finally:
        send_welcome_by_id(message.chat.id)

# تحويل الفيديو إلى MP3
@bot.message_handler(func=lambda message: message.text == '🎵 فيديو إلى MP3')
def handle_video_to_mp3(message):
    if not FFMPEG_AVAILABLE:
        bot.send_message(message.chat.id,
                       "❌ **مطلوب FFmpeg**\n\n"
                       "هذه الميزة تحتاج إلى تثبيت FFmpeg:\n"
                       "💡 **الحل السريع:** استخدم '🎵 تنزيل صوت' لاستخراج الصوت المباشر من الفيديوهات عبر الإنترنت",
                       parse_mode='Markdown')
        return
    
    user_states[message.chat.id] = 'waiting_video_mp3'
    bot.send_message(message.chat.id, "🎬 أرسل ملف الفيديو لاستخراج الصوت منه (الحد الأقصى 50 ميجابايت)", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['video'], func=lambda message: user_states.get(message.chat.id) == 'waiting_video_mp3')
def process_video_to_mp3(message):
    try:
        # التحقق من حجم الملف
        if message.video.file_size > 50 * 1024 * 1024:
            bot.send_message(message.chat.id, "❌ الملف كبير جدًا! الحد الأقصى للحجم هو 50 ميجابايت")
            send_welcome_by_id(message.chat.id)
            return
            
        bot.send_message(message.chat.id, "⏳ جاري استخراج الصوت من الفيديو...")
        
        # تنزيل ملف الفيديو
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        video_path = os.path.join(TEMP_DIR, f"video_{message.message_id}.mp4")
        with open(video_path, 'wb') as f:
            f.write(downloaded_file)
        
        audio_path = None
        try:
            # تحويل الفيديو إلى MP3 باستخدام FFmpeg
            audio_path = os.path.join(TEMP_DIR, f"audio_{message.message_id}.mp3")
            
            ffmpeg_cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # لا فيديو
                '-acodec', 'libmp3lame',
                '-ab', '192k',  # معدل البت الصوتي
                '-ar', '44100',  # معدل العينة
                '-y',  # الكتابة فوق المخرجات
                audio_path
            ]
            
            result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=120)  # زيادة المهلة
            
            if result.returncode == 0 and os.path.exists(audio_path):
                file_size = get_file_size(audio_path)
                
                # التحقق من أن الملف ليس فارغاً
                if os.path.getsize(audio_path) < 1024:
                    raise Exception("ملف الصوت الناتج فارغ")
                
                # إرسال MP3 إلى المستخدم
                with open(audio_path, 'rb') as audio_file:
                    bot.send_audio(message.chat.id, audio_file, 
                                 caption=f"✅ تم استخراج الصوت بنجاح!\n📊 الحجم: {file_size}")
            else:
                error_msg = result.stderr[:200] if result.stderr else "فشل التحويل"
                raise Exception(f"فشل استخراج الصوت: {error_msg}")
                
        except subprocess.TimeoutExpired:
            bot.send_message(message.chat.id, "❌ انتهت مهلة التحويل - قد يكون الملف كبيرًا جدًا")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"خطأ في استخراج MP3: {error_msg}")
            bot.send_message(message.chat.id, f"❌ فشل الاستخراج: {str(e)[:100]}")
        
        finally:
            # تنظيف الملفات
            for path in [video_path, audio_path]:
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
        
    except Exception as e:
        logger.error(f"خطأ في معالجة الفيديو: {e}")
        bot.send_message(message.chat.id, f"❌ خطأ في المعالجة: {str(e)}")
    
    finally:
        send_welcome_by_id(message.chat.id)

# تحويل الصورة إلى JPG
@bot.message_handler(func=lambda message: message.text == '🖼️ صورة إلى JPG')
def handle_image_to_jpg(message):
    user_states[message.chat.id] = 'waiting_image_jpg'
    bot.send_message(message.chat.id, "📤 أرسل الصورة لتحويلها إلى تنسيق JPG", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.chat.id) == 'waiting_image_jpg')
def process_image_to_jpg(message):
    try:
        bot.send_message(message.chat.id, "⏳ جاري تحويل الصورة إلى JPG...")
        
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.temp', dir=TEMP_DIR) as temp_file:
            temp_file.write(downloaded_file)
            temp_path = temp_file.name
        
        jpg_path = None
        try:
            # التحويل إلى JPG
            image = Image.open(temp_path)
            image = image.convert('RGB')
            
            jpg_path = os.path.join(TEMP_DIR, f"converted_{message.message_id}.jpg")
            image.save(jpg_path, "JPEG", quality=95, optimize=True)
            
            file_size = get_file_size(jpg_path)
            
            # إرسال الصورة المحولة
            with open(jpg_path, 'rb') as jpg_file:
                bot.send_photo(message.chat.id, jpg_file, 
                             caption=f"✅ تم التحويل إلى JPG بنجاح!\n📊 الحجم: {file_size}")
            
        except Exception as e:
            bot.send_message(message.chat.id, f"❌ خطأ في التحويل: {str(e)}")
        
        finally:
            # التنظيف
            for path in [temp_path, jpg_path]:
                try:
                    if path and os.path.exists(path):
                        os.unlink(path)
                except:
                    pass
        
    except Exception as e:
        logger.error(f"خطأ في تحويل JPG: {e}")
        bot.send_message(message.chat.id, f"❌ خطأ في المعالجة: {str(e)}")
    
    finally:
        send_welcome_by_id(message.chat.id)

# ========== نظام البحث عن الأغاني ==========
@bot.message_handler(func=lambda message: message.text == '🔍 بحث أغنية')
def handle_lyrics_search(message):
    user_states[message.chat.id] = 'waiting_lyrics'
    bot.send_message(message.chat.id, "🎤 أدخل كلمات الأغنية أو العنوان للبحث:", 
                   reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_lyrics')
def search_by_lyrics(message):
    try:
        lyrics = message.text.strip()
        if len(lyrics) < 2:
            bot.send_message(message.chat.id, "❌ يرجى إدخال حرفين على الأقل")
            send_welcome_by_id(message.chat.id)
            return
        
        bot.send_message(message.chat.id, f"🔍 جاري البحث عن: '{lyrics}'")
        
        thread = threading.Thread(target=perform_song_search, args=(message.chat.id, lyrics))
        thread.daemon = True
        thread.start()
        
    except Exception as e:
        logger.error(f"خطأ في بدء البحث: {e}")
        bot.send_message(message.chat.id, "❌ فشل البحث. يرجى المحاولة مرة أخرى.")
        send_welcome_by_id(message.chat.id)

def perform_song_search(chat_id, lyrics):
    """إجراء بحث الأغاني في thread خلفي"""
    try:
        # إنشاء استعلام البحث
        search_query = f"{lyrics} official audio"
        
        bot.send_message(chat_id, "🎵 جاري البحث في YouTube...")
        
        # استخدام خيارات yt-dlp أبسط للبحث
        ydl_opts = {
            'quiet': True,
            'no_warnings': False,
            'extract_flat': True,  # استخدام الاستخراج المسطح للبحث الأسرع
            'socket_timeout': 15,
            'skip_download': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # البحث في YouTube باستخدام ytsearch
            search_url = f"ytsearch10:{search_query}"
            info = ydl.extract_info(search_url, download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                bot.send_message(chat_id, "❌ لم يتم العثور على نتائج لبحثك")
                return
            
            entries = info['entries']
            valid_entries = []
            
            # معالجة نتائج البحث
            for entry in entries:
                if entry and entry.get('url'):
                    title = entry.get('title', 'عنوان غير معروف')
                    duration = entry.get('duration')
                    duration_str = format_duration(duration)
                    url = entry.get('url')
                    
                    # تصفية البث المباشر والفيديوهات الطويلة جدًا
                    if duration and duration > 36000:  # أطول من 10 ساعات
                        continue
                        
                    valid_entries.append({
                        'title': title,
                        'url': url,
                        'duration': duration_str
                    })
            
            if not valid_entries:
                bot.send_message(chat_id, "❌ لم يتم العثور على نتائج صالحة")
                return
            
            # عرض أفضل النتائج
            results_text = "🎵 **أفضل النتائج:**\n\n"
            for i, entry in enumerate(valid_entries[:5], 1):
                results_text += f"{i}. {entry['title']}\n"
                results_text += f"   ⏱️ {entry['duration']}\n\n"
            
            results_text += "⬇️ جاري تنزيل أول نتيجة..."
            bot.send_message(chat_id, results_text, parse_mode='Markdown')
            
            # تنزيل أول نتيجة
            first_result = valid_entries[0]
            bot.send_message(chat_id, f"🎵 جاري التنزيل: {first_result['title']}")
            
            # استخدام نظام التنزيل الموجود
            process_download(chat_id, first_result['url'], 'audio', False)
                
    except Exception as e:
        logger.error(f"خطأ في بحث الأغاني: {e}")
        error_msg = str(e)
        
        # تقديم رسائل خطأ محددة
        if "Unable to download webpage" in error_msg:
            bot.send_message(chat_id, "❌ خدمة البحث غير متاحة. يرجى المحاولة مرة أخرى لاحقًا.")
        elif "No results found" in error_msg:
            bot.send_message(chat_id, "❌ لم يتم العثور على نتائج. جرب كلمات مختلفة.")
        else:
            bot.send_message(chat_id, f"❌ خطأ في البحث: {error_msg[:100]}")
            
    finally:
        send_welcome_by_id(chat_id)

# ========== الأوامر الإضافية ==========
@bot.message_handler(func=lambda message: message.text == '🔙 القائمة الرئيسية')
def handle_back(message):
    send_welcome(message)

@bot.message_handler(func=lambda message: message.text == 'ℹ️ المساعدة والمعلومات')
def handle_help(message):
    help_text = """
🛠️ **MediaBot Pro - الدليل الكامل**

⚡ **خيارات التنزيل:**
- 📥 تنزيل عادي: فيديوهات عالية الجودة (720p)
- ⚡ تنزيل سريع: جودة أقل (360p) للسرعة
- 🎵 تنزيل صوت: استخراج الصوت من أي فيديو

🔄 **أدوات التحويل:**
- 📷 صورة إلى PDF: تحويل الصور إلى مستندات PDF
- 🎵 فيديو إلى MP3: استخراج الصوت من ملفات الفيديو
- 🖼️ صورة إلى JPG: تحويل الصور إلى تنسيق JPG

🔍 **بحث الموسيقى:**
- البحث بالكلمات أو عنوان الأغنية
- التنزيل التلقائي لأفضل نتيجة

📋 **المنصات المدعومة:**
- YouTube, Instagram, Facebook, TikTok
- Twitter, Reddit, SoundCloud, Spotify  
- Vimeo, Twitch, Dailymotion, والمزيد!

🔧 **المعلومات الفنية:**
- التنظيف التلقائي كل ساعة
- الدعم لتنسيقات متعددة
- معالجة الأخطاء المهنية

💡 **الأوامر السريعة:**
/start - القائمة الرئيسية
/status - حالة النظام  
/clean - تنظيف الملفات المؤقتة
/ffmpeg_help - دليل إعداد FFmpeg

🚀 **جاهز للاستخدام! اختر أي خيار من القائمة الرئيسية.**
    """
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['status'])
def check_status(message):
    """عرض حالة النظام الشاملة"""
    chat_id = message.chat.id
    
    ffmpeg_status = "✅ مثبت ويعمل" if FFMPEG_AVAILABLE else "❌ غير متاح - استخدام الميزات الأساسية"
    cloud_status = "🌐 سحابة Railway" if CLOUD_DEPLOYMENT else "💻 محلي"
    
    # عد الملفات المؤقتة
    temp_files = len([f for f in os.listdir(TEMP_DIR) if os.path.isfile(os.path.join(TEMP_DIR, f))])
    
    status_text = f"""
🤖 **تقرير حالة النظام**

📍 **النشر:** {cloud_status}
🐍 **إصدار Python:** {sys.version.split()[0]}
📁 **الملفات المؤقتة:** {temp_files} ملف
🔧 **حالة FFmpeg:** {ffmpeg_status}
👥 **الجلسات النشطة:** {len(user_states)}
🧹 **التنظيف التلقائي:** ✅ نشط

🔄 **جميع الأنظمة:** ✅ تعمل
💡 **الحالة:** 🟢 تعمل بشكل مثالي

💡 **ملاحظة:** { "جميع الميزات متاحة" if FFMPEG_AVAILABLE else "بعض الميزات المتقدمة غير متاحة بسبب عدم توفر FFmpeg" }
"""
    
    bot.send_message(chat_id, status_text, parse_mode='Markdown')

@bot.message_handler(commands=['clean'])
def clean_temp(message):
    """أمر التنظيف الفوري"""
    deleted_files = auto_cleanup.cleanup_temp_files(max_age_minutes=0)
    if deleted_files > 0:
        bot.send_message(message.chat.id, f"🧹 تم تنظيف {deleted_files} ملف مؤقت!")
    else:
        bot.send_message(message.chat.id, "✅ لا توجد ملفات مؤقتة للتنظيف")

@bot.message_handler(commands=['ffmpeg_help'])
def ffmpeg_help(message):
    """دليل تثبيت FFmpeg"""
    help_text = """
🔧 **حول FFmpeg في السحابة**

ℹ️ **المعلومات:**
- في بيئة Railway السحابية، قد لا يكون FFmpeg متاحاً افتراضياً
- هذا لا يؤثر على الميزات الأساسية للبوت
- يمكنك仍然 تنزيل الفيديوهات واستخراج الصوت بالتنسيقات الأصلية

⚡ **الميزات المتاحة بدون FFmpeg:**
- ✅ تنزيل الفيديوهات بجميع الجودات
- ✅ استخراج الصوت بالتنسيقات الأصلية (MP4, M4A, WEBM)
- ✅ البحث عن الموسيقى والتنزيل
- ✅ تحويل الصور إلى PDF وJPG

💡 **نصائح للاستخدام:**
- استخدم "🎵 تنزيل صوت" لاستخراج الصوت من الفيديوهات
- الملفات الصوتية ستكون بالتنسيق الأصلي (عادةً M4A)
- معظم مشغلات الصوت تدعم التنسيقات الأصلية

🚀 **البوت يعمل بكامل طاقته حتى بدون FFmpeg!**
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    """التعامل مع الأوامر غير المعروفة"""
    if message.chat.id not in user_states:
        send_welcome(message)
    else:
        bot.send_message(message.chat.id, 
                        "❌ أمر غير معترف به\n\n"
                        "يرجى استخدام أزرار القائمة أو /help للمساعدة")

# ========== التنفيذ الرئيسي ==========
if __name__ == "__main__":
    print("=" * 60)
    
    if CLOUD_DEPLOYMENT:
        print("🚀 تم اكتشاف النشر السحابي لـ Railway")
        print("📍 المجلد المؤقت:", TEMP_DIR)
        print("🌐 الرابط العام: متاح عبر Railway")
    else:
        print("🖥️ تم اكتشاف النشر المحلي")
    
    print("🤖 بدء تشغيل بوت متعدد الوظائف...")
    print("=" * 60)
    
    # التنظيف الأولي
    initial_cleanup = auto_cleanup.cleanup_temp_files()
    if initial_cleanup > 0:
        print(f"🧹 التنظيف الأولي: تمت إزالة {initial_cleanup} ملف")
    
    # بدء نظام التنظيف التلقائي
    auto_cleanup.start_auto_cleanup()
    
    try:
        # الحصول على معلومات البوت
        bot_info = bot.get_me()
        print(f"✅ تم تهيئة البوت: @{bot_info.username}")
        print(f"🐍 إصدار Python: {sys.version.split()[0]}")
        print(f"🔧 حالة FFmpeg: {'✅ متاح' if FFMPEG_AVAILABLE else '❌ غير متاح - استخدام الميزات الأساسية'}")
        print("🧹 التنظيف التلقائي: ✅ نشط")
        print("📊 النظام جاهز للطلبات...")
        print("=" * 60)
        
        # بدء الاستطلاع
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f"❌ خطأ fatal: {e}")
        logger.error(f"تحطم البوت: {e}")
    finally:
        print("🛑 إيقاف البوت...")
        auto_cleanup.stop_auto_cleanup()
        final_cleanup = auto_cleanup.cleanup_temp_files()
        if final_cleanup > 0:
            print(f"🧹 التنظيف النهائي: تمت إزالة {final_cleanup} ملف")
        print("✅ تم إيقاف البوت بنجاح")
