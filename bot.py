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

# ========== Advanced Cloud Settings ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('/tmp/bot.log')
    ]
)
logger = logging.getLogger(__name__)

print("🚀 Starting Advanced Media Bot on Railway...")

# ========== Install Required Packages ==========
def install_required_packages():
    """Install all required packages with compatibility fixes"""
    packages = [
        'pyTelegramBotAPI==4.14.0',
        'yt-dlp==2024.4.9',
        'Pillow==10.2.0',
        'requests==2.31.0',
        'psutil==5.9.6'
    ]
    
    for package in packages:
        try:
            package_name = package.split('==')[0]
            if package_name == 'pyTelegramBotAPI':
                import telebot
                print(f"✅ {package_name} - already installed")
            elif package_name == 'yt-dlp':
                import yt_dlp
                print(f"✅ {package_name} - already installed")
            elif package_name == 'Pillow':
                from PIL import Image
                print(f"✅ {package_name} - already installed")
            elif package_name == 'requests':
                import requests
                print(f"✅ {package_name} - already installed")
            elif package_name == 'psutil':
                import psutil
                print(f"✅ {package_name} - already installed")
        except ImportError:
            print(f"📦 Installing {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                print(f"✅ Successfully installed {package}")
            except Exception as e:
                print(f"❌ Failed to install {package}: {e}")
                # Try without version pinning
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])
                    print(f"✅ Successfully installed {package_name} (latest)")
                except:
                    print(f"❌ Critical: Could not install {package_name}")

install_required_packages()

# ========== Import Libraries ==========
try:
    import telebot
    from telebot import types
    print("✅ telebot imported successfully")
except ImportError as e:
    print(f"❌ Failed to import telebot: {e}")
    sys.exit(1)

try:
    import yt_dlp
    print("✅ yt-dlp imported successfully")
except ImportError as e:
    print(f"❌ Failed to import yt-dlp: {e}")
    sys.exit(1)

try:
    from PIL import Image
    print("✅ PIL imported successfully")
except ImportError as e:
    print(f"❌ Failed to import PIL: {e}")
    sys.exit(1)

try:
    import psutil
    print("✅ psutil imported successfully")
except ImportError as e:
    print(f"❌ Failed to import psutil: {e}")
    # Continue without psutil

# ========== Configuration ==========
API_TOKEN = os.environ.get('BOT_TOKEN')
if not API_TOKEN:
    print("❌ ERROR: BOT_TOKEN not found in environment variables!")
    sys.exit(1)

print(f"✅ Bot token loaded successfully")

bot = telebot.TeleBot(API_TOKEN, parse_mode='HTML')

# Temporary directory for cloud
TEMP_DIR = "/tmp/telegram_bot_files"
os.makedirs(TEMP_DIR, exist_ok=True)

CLOUD_DEPLOYMENT = 'RAILWAY_ENVIRONMENT' in os.environ

print(f"🌐 Cloud Deployment: {CLOUD_DEPLOYMENT}")
print(f"📁 Temp Directory: {TEMP_DIR}")

# ========== User Management ==========
user_states = {}

# ========== FFmpeg Setup ==========
def setup_environment():
    """Setup environment including FFmpeg"""
    try:
        result = subprocess.run(['which', 'ffmpeg'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ FFmpeg is available")
            return True
        else:
            print("⚠️ FFmpeg not found, some features will be limited")
            return False
    except Exception as e:
        print(f"❌ Environment setup error: {e}")
        return False

FFMPEG_AVAILABLE = setup_environment()

# ========== Enhanced yt-dlp Configuration ==========
def get_ydl_options(download_type='video', quality='best'):
    """Get optimized yt-dlp options"""
    
    base_options = {
        'outtmpl': os.path.join(TEMP_DIR, '%(title).100s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
        
        # Enhanced HTTP settings
        'socket_timeout': 60,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ignoreerrors': False,
        'no_check_certificate': True,
        
        # Browser simulation
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Sec-Fetch-Mode': 'navigate',
        },
        
        'noplaylist': True,
        'extract_flat': False,
        
        # Downloader options
        'buffersize': 1024 * 1024,
        'http_chunk_size': 10485760,
    }
    
    if download_type == 'audio':
        base_options.update({
            'format': 'bestaudio/best',
            'writethumbnail': False,
        })
        
        if FFMPEG_AVAILABLE:
            base_options.update({
                'postprocessors': [
                    {
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }
                ],
                'prefer_ffmpeg': True,
            })
        else:
            base_options.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
    else:
        if quality == 'fast':
            base_options.update({
                'format': 'best[height<=480]/best[height<=360]/worst',
            })
        else:  # best
            base_options.update({
                'format': 'best[height<=720]/best[height<=480]/best',
            })
    
    return base_options

# ========== Download Function ==========
def download_media(chat_id, url, download_type='video', quality='best'):
    """Download media with enhanced error handling"""
    
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                bot.send_message(chat_id, f"🔄 Retry attempt {attempt + 1}/{max_retries}...")
            
            # Get download options
            ydl_opts = get_ydl_options(download_type, quality)
            
            # Create unique filename
            timestamp = int(time.time())
            ydl_opts['outtmpl'] = os.path.join(TEMP_DIR, f'download_{timestamp}_%(title)s.%(ext)s')
            
            print(f"🎯 Download attempt {attempt + 1}")
            
            # Extract info first
            with yt_dlp.YoutubeDL({**ydl_opts, 'skip_download': True}) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("Could not extract video information")
                
                title = sanitize_filename(info.get('title', 'Unknown'))
                bot.send_message(chat_id, f"📥 <b>Downloading:</b> {title}")
            
            # Perform download
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            time.sleep(2)
            pattern = os.path.join(TEMP_DIR, f"download_{timestamp}_*")
            files = glob.glob(pattern)
            
            if not files:
                all_files = glob.glob(os.path.join(TEMP_DIR, "*"))
                if all_files:
                    all_files.sort(key=os.path.getmtime, reverse=True)
                    files = [all_files[0]]
            
            # Verify file
            for file_path in files:
                try:
                    file_size = os.path.getsize(file_path)
                    if file_size > 1024:
                        return info, file_path
                    else:
                        os.unlink(file_path)
                except:
                    continue
            
            raise Exception("Download completed but no valid file found")
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Download error (attempt {attempt + 1}): {error_msg}")
            
            # Clean up partial files
            try:
                pattern = os.path.join(TEMP_DIR, f"download_{timestamp}_*")
                for file_path in glob.glob(pattern):
                    os.unlink(file_path)
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                if "HTTP Error 403" in error_msg:
                    raise Exception("Server blocked the request. Try again later.")
                elif "Video unavailable" in error_msg:
                    raise Exception("Video is unavailable or restricted.")
                else:
                    raise Exception(f"Download failed: {error_msg[:100]}")
                    
        except Exception as e:
            logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
            
            try:
                pattern = os.path.join(TEMP_DIR, f"download_{timestamp}_*")
                for file_path in glob.glob(pattern):
                    os.unlink(file_path)
            except:
                pass
            
            if attempt < max_retries - 1:
                time.sleep(3)
                continue
            else:
                raise e
    
    raise Exception("All download attempts failed")

# ========== Download Handler ==========
def handle_download_process(chat_id, url, download_type='video', quality='best'):
    """Handle the complete download process"""
    try:
        if not is_supported_url(url):
            bot.send_message(chat_id, "❌ <b>Unsupported URL</b>")
            show_main_menu(chat_id)
            return
        
        bot.send_message(chat_id, "🔍 <b>Starting download...</b>")
        
        info, file_path = download_media(chat_id, url, download_type, quality)
        
        if not info or not file_path:
            bot.send_message(chat_id, "❌ <b>Download failed</b>")
            show_main_menu(chat_id)
            return
        
        # Verify file
        if not os.path.exists(file_path) or os.path.getsize(file_path) < 1024:
            bot.send_message(chat_id, "❌ <b>Downloaded file is invalid</b>")
            try:
                os.unlink(file_path)
            except:
                pass
            show_main_menu(chat_id)
            return
        
        # Prepare file info
        title = sanitize_filename(info.get('title', 'Unknown'))
        file_size_str = get_file_size(file_path)
        
        caption = f"""
✅ <b>Download Complete!</b>

🎬 <b>Title:</b> {title}
📊 <b>Size:</b> {file_size_str}
        """
        
        # Send file
        bot.send_message(chat_id, "📤 <b>Uploading file...</b>")
        bot.send_chat_action(chat_id, 'upload_document')
        
        try:
            with open(file_path, 'rb') as file:
                if download_type == 'audio':
                    bot.send_audio(chat_id, file, caption=caption, title=title[:64], timeout=120)
                else:
                    bot.send_video(chat_id, file, caption=caption, timeout=120, supports_streaming=True)
            
            bot.send_message(chat_id, "✅ <b>Upload successful!</b>")
            
        except Exception as upload_error:
            logger.error(f"Upload error: {upload_error}")
            try:
                with open(file_path, 'rb') as file:
                    bot.send_document(chat_id, file, caption=caption, timeout=120)
                bot.send_message(chat_id, "✅ <b>Upload completed as document!</b>")
            except Exception as doc_error:
                logger.error(f"Document upload failed: {doc_error}")
                bot.send_message(chat_id, f"❌ <b>Upload failed:</b> {str(upload_error)[:100]}")
        
        # Cleanup
        try:
            if os.path.exists(file_path):
                os.unlink(file_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download processing error: {error_msg}")
        
        if "unavailable" in error_msg.lower():
            bot.send_message(chat_id, "❌ <b>Video unavailable or restricted</b>")
        elif "blocked" in error_msg.lower():
            bot.send_message(chat_id, "❌ <b>Server blocked the request</b>")
        else:
            bot.send_message(chat_id, f"❌ <b>Error:</b> {error_msg[:150]}")
    
    finally:
        show_main_menu(chat_id)

# ========== Utility Functions ==========
def sanitize_filename(filename):
    """Sanitize filename for safe usage"""
    if not filename:
        return "media_file"
    
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename or "media_file"

def get_file_size(file_path):
    """Get human readable file size"""
    try:
        size = os.path.getsize(file_path)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    except:
        return "Unknown"

def format_duration(seconds):
    """Format duration from seconds"""
    try:
        seconds = int(seconds)
        minutes = seconds // 60
        seconds = seconds % 60
        hours = minutes // 60
        minutes = minutes % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"
    except:
        return "Unknown"

def is_supported_url(url):
    """Check if URL is from supported platform"""
    try:
        url = url.strip()
        if not url:
            return False
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        supported_domains = [
            'youtube.com', 'youtu.be', 'music.youtube.com',
            'instagram.com', 'www.instagram.com',
            'facebook.com', 'fb.watch', 'www.facebook.com',
            'tiktok.com', 'vm.tiktok.com', 'www.tiktok.com',
            'twitter.com', 'x.com', 'www.twitter.com',
            'soundcloud.com', 'www.soundcloud.com',
            'vimeo.com', 'www.vimeo.com',
            'dailymotion.com', 'www.dailymotion.com',
        ]
        
        domain = urllib.parse.urlparse(url).netloc.lower()
        return any(supported in domain for supported in supported_domains)
        
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False

# ========== Cleanup System ==========
class CleanupManager:
    def __init__(self):
        self.active = True
        
    def cleanup_old_files(self, max_age_minutes=10):
        """Clean up old temporary files"""
        try:
            current_time = time.time()
            deleted_files = 0
            
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(file_path):
                    file_age = (current_time - os.path.getctime(file_path)) / 60
                    if file_age > max_age_minutes:
                        try:
                            os.unlink(file_path)
                            deleted_files += 1
                        except Exception as e:
                            logger.error(f"Failed to delete {filename}: {e}")
            
            if deleted_files > 0:
                logger.info(f"🧹 Cleaned {deleted_files} temporary files")
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    def start_cleanup_daemon(self):
        """Start background cleanup daemon"""
        def daemon_loop():
            while self.active:
                try:
                    self.cleanup_old_files()
                    time.sleep(300)
                except Exception as e:
                    logger.error(f"Cleanup daemon error: {e}")
                    time.sleep(300)
        
        thread = threading.Thread(target=daemon_loop, daemon=True)
        thread.start()
        logger.info("✅ Cleanup daemon started")

# Initialize cleanup system
cleanup_manager = CleanupManager()
cleanup_manager.start_cleanup_daemon()

# ========== Menu System ==========
def show_main_menu(chat_id):
    """Display the main menu"""
    try:
        markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
        
        buttons = [
            '📥 Download Video', 
            '⚡ Fast Download',
            '🎵 Audio Only',
            '🔍 Search Music',
            '📊 Status',
            'ℹ️ Help'
        ]
        
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            markup.add(*[types.KeyboardButton(btn) for btn in row])
        
        welcome_text = """
🎉 <b>Welcome to MasTerDCS!</b>

⚡ <b>We Can help You with:</b>

• <b>Download Video</b> - High quality
• <b>Fast Download</b> - Lower quality  
• <b>Audio Only</b> - Extract audio
• <b>Search Music</b> - Find songs

<code>Choose your desired option below 👇</code>
        """
        
        bot.send_message(chat_id, welcome_text, reply_markup=markup)
        user_states[chat_id] = 'main'
        
    except Exception as e:
        logger.error(f"Menu error: {e}")

# ========== Command Handlers ==========
@bot.message_handler(commands=['start', 'help', 'menu'])
def handle_start(message):
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text in ['📥 Download Video', '⚡ Fast Download', '🎵 Audio Only'])
def handle_download_selection(message):
    chat_id = message.chat.id
    
    configs = {
        '📥 Download Video': {'type': 'video', 'quality': 'best', 'desc': 'High Quality Video'},
        '⚡ Fast Download': {'type': 'video', 'quality': 'fast', 'desc': 'Fast Download'},
        '🎵 Audio Only': {'type': 'audio', 'quality': 'best', 'desc': 'Audio Extraction'}
    }
    
    config = configs[message.text]
    user_states[chat_id] = f'waiting_url_{config["type"]}_{config["quality"]}'
    
    instructions = f"""
📋 <b>{config['desc']}</b>

🔗 <b>Send the video URL now</b>

<code>Paste your URL below...</code>
    """
    
    bot.send_message(chat_id, instructions, reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(func=lambda message: user_states.get(message.chat.id, '').startswith('waiting_url_'))
def process_url_input(message):
    chat_id = message.chat.id
    url = message.text.strip()
    
    current_state = user_states.get(chat_id, '')
    if not current_state.startswith('waiting_url_'):
        return
    
    parts = current_state.split('_')
    download_type = parts[2]
    quality = parts[3]
    
    user_states[chat_id] = 'processing'
    
    thread = threading.Thread(
        target=handle_download_process,
        args=(chat_id, url, download_type, quality)
    )
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 <b>Starting download...</b>")

# ========== Additional Handlers ==========
@bot.message_handler(func=lambda message: message.text == '🔍 Search Music')
def handle_music_search(message):
    user_states[message.chat.id] = 'waiting_music_query'
    bot.send_message(
        message.chat.id,
        "🎵 <b>Music Search</b>\n\nSend song lyrics or title:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda message: message.text == '📊 Status')
def handle_status(message):
    status_text = """
📊 <b>System Status</b>

✅ <b>All Systems Operational</b>

🚀 <b>Ready for downloads!</b>
    """
    
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help')
def handle_help(message):
    help_text = """
🛠️ <b>Media Bot Help</b>

⚡ <b>Download Options:</b>
• Download Video - High quality
• Fast Download - Lower quality
• Audio Only - Extract audio

🔍 <b>Music Search:</b>
• Search by lyrics or title

💡 <b>Tips:</b>
• Use direct video links
• Some videos may be restricted

<code>Choose from the main menu!</code>
    """
    
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(func=lambda message: True)
def handle_unknown_messages(message):
    """Handle unknown messages"""
    if message.chat.id not in user_states:
        show_main_menu(message.chat.id)
    else:
        bot.send_message(
            message.chat.id,
            "❌ <b>Unknown command</b>\n\nUse the menu buttons or /help."
        )

# ========== Main Execution ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Media Bot...")
    print(f"🌐 Cloud Environment: {CLOUD_DEPLOYMENT}")
    print("=" * 60)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Bot initialized: @{bot_info.username}")
        
        cleanup_manager.cleanup_old_files(max_age_minutes=0)
        
        print("📊 Bot is ready to receive requests...")
        print("=" * 60)
        
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Bot crash: {e}")
    finally:
        print("🛑 Shutting down bot...")
        cleanup_manager.active = False
        print("✅ Bot stopped successfully")
