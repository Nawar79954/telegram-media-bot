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
    """Install all required packages"""
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
                print("✅ telebot - already installed")
            elif package == 'yt-dlp':
                import yt_dlp
                print("✅ yt-dlp - already installed")
            elif package == 'pillow':
                from PIL import Image
                print("✅ pillow - already installed")
            elif package == 'requests':
                import requests
                print("✅ requests - already installed")
            elif package == 'psutil':
                import psutil
                print("✅ psutil - already installed")
        except ImportError:
            print(f"📦 Installing {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

install_required_packages()

# ========== Import Libraries ==========
import telebot
from telebot import types
import yt_dlp
from PIL import Image
import psutil

# ========== Configuration ==========
API_TOKEN = os.environ.get('BOT_TOKEN')
if not API_TOKEN:
    logger.error("❌ BOT_TOKEN not found in environment variables!")
    sys.exit(1)

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
        # Check if FFmpeg is available
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
    """Get optimized yt-dlp options to avoid 403 errors"""
    
    # Random user agents to avoid blocking
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:90.0) Gecko/20100101 Firefox/90.0',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
    ]
    
    base_options = {
        'outtmpl': os.path.join(TEMP_DIR, '%(title).100s.%(ext)s'),
        'quiet': True,
        'no_warnings': False,
        
        # Enhanced HTTP settings to avoid 403
        'socket_timeout': 30,
        'retries': 10,
        'fragment_retries': 10,
        'skip_unavailable_fragments': True,
        'ignoreerrors': False,
        'no_check_certificate': True,
        
        # Browser simulation
        'http_headers': {
            'User-Agent': random.choice(user_agents),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-us,en;q=0.5',
            'Sec-Fetch-Mode': 'navigate',
            'Accept-Encoding': 'gzip, deflate, br',
        },
        
        'noplaylist': True,
        'extract_flat': False,
        
        # Throttling to avoid rate limits
        'throttledratelimit': 1000000,
        
        # YouTube specific options
        'youtube_include_dash_manifest': False,
        'youtube_include_hls_manifest': False,
    }
    
    if download_type == 'audio':
        if FFMPEG_AVAILABLE:
            base_options.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'prefer_ffmpeg': True,
            })
        else:
            base_options.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
    else:
        if quality == 'fast':
            base_options.update({
                'format': 'worst[height<=480]/worst',
            })
        elif quality == 'hd':
            base_options.update({
                'format': 'best[height<=1080]/best[height<=720]/best',
            })
        else:  # best
            base_options.update({
                'format': 'best[height<=720]/best[height<=480]/best',
            })
    
    return base_options

# ========== Enhanced Download Function ==========
def download_media(chat_id, url, download_type='video', quality='best'):
    """Download media with enhanced error handling and retry logic"""
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                bot.send_message(chat_id, f"🔄 Retry attempt {attempt + 1}/{max_retries}...")
                time.sleep(2)  # Wait before retry
            
            progress_msg = bot.send_message(chat_id, "🔍 <b>Analyzing URL...</b>")
            
            # First get video info with different options
            ydl_opts = get_ydl_options(download_type, quality)
            ydl_opts['skip_download'] = True
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise Exception("Could not extract video information")
                
                title = sanitize_filename(info.get('title', 'Unknown Content'))
                duration = info.get('duration', 0)
                uploader = info.get('uploader', 'Unknown')
                
                # Update with video info
                info_text = f"""
🎬 <b>{title}</b>
👤 <b>Uploader:</b> {uploader}
⏱️ <b>Duration:</b> {format_duration(duration)}

📥 <b>Starting download (Attempt {attempt + 1}/{max_retries})...</b>
                """
                bot.edit_message_text(info_text, chat_id, progress_msg.message_id)
            
            # Actual download with different options for retry
            ydl_opts = get_ydl_options(download_type, quality)
            ydl_opts['skip_download'] = False
            
            # On retry, try different format
            if attempt > 0:
                if download_type == 'audio':
                    ydl_opts['format'] = 'bestaudio/best'
                else:
                    ydl_opts['format'] = 'best[height<=480]/best'
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            pattern = os.path.join(TEMP_DIR, f"{title}.*")
            files = glob.glob(pattern)
            
            if not files:
                # Find latest file
                all_files = glob.glob(os.path.join(TEMP_DIR, "*"))
                if all_files:
                    files = [max(all_files, key=os.path.getctime)]
            
            if files and os.path.exists(files[0]):
                return info, files[0]
            else:
                raise Exception("Downloaded file not found")
                
        except yt_dlp.DownloadError as e:
            error_msg = str(e)
            logger.error(f"Download error (attempt {attempt + 1}): {error_msg}")
            
            if "HTTP Error 403" in error_msg:
                if attempt < max_retries - 1:
                    continue
                else:
                    raise Exception("Server blocked the request (403 Forbidden). Please try again later or try a different video.")
            elif "Video unavailable" in error_msg:
                raise Exception("Video is unavailable. It may be private, deleted, or restricted.")
            elif "Private video" in error_msg:
                raise Exception("This is a private video and cannot be accessed.")
            else:
                if attempt < max_retries - 1:
                    continue
                else:
                    raise e
                    
        except Exception as e:
            logger.error(f"Unexpected error (attempt {attempt + 1}): {e}")
            if attempt < max_retries - 1:
                continue
            else:
                raise e
    
    raise Exception("All download attempts failed")

# ========== Enhanced Download Handler ==========
def handle_download_process(chat_id, url, download_type='video', quality='best'):
    """Handle the complete download process with enhanced error handling"""
    try:
        # Validate URL
        if not is_supported_url(url):
            bot.send_message(chat_id, "❌ <b>Unsupported URL</b>\n\nSupported platforms: YouTube, Instagram, TikTok, Facebook, Twitter, SoundCloud, Vimeo, etc.")
            return
        
        # Start download
        info, file_path = download_media(chat_id, url, download_type, quality)
        
        if not info or not file_path:
            bot.send_message(chat_id, "❌ <b>Download failed - No content received</b>")
            return
        
        # Prepare file info
        title = sanitize_filename(info.get('title', 'Unknown'))
        file_size = get_file_size(file_path)
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'Unknown')
        
        caption = f"""
✅ <b>Download Complete!</b>

🎬 <b>Title:</b> {title}
👤 <b>Uploader:</b> {uploader}
⏱️ <b>Duration:</b> {format_duration(duration)}
📊 <b>Size:</b> {file_size}
        """
        
        # Send file
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
            # Fallback to document
            try:
                with open(file_path, 'rb') as file:
                    bot.send_document(chat_id, file, caption=caption, timeout=120)
            except Exception as doc_error:
                logger.error(f"Document upload error: {doc_error}")
                bot.send_message(chat_id, f"❌ <b>Upload failed:</b> {str(upload_error)[:100]}")
        
        # Cleanup
        try:
            os.unlink(file_path)
        except Exception as e:
            logger.error(f"File cleanup error: {e}")
            
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Download processing error: {error_msg}")
        
        # Specific error handling
        if "403" in error_msg or "blocked" in error_msg.lower():
            error_response = """
❌ <b>Download Blocked (403 Error)</b>

This usually happens because:
• The server is temporarily blocking requests
• The video has restrictions
• Too many requests from this IP

💡 <b>Solutions:</b>
• Try again in a few minutes
• Try a different video
• Use the 'Fast Download' option
• The issue might resolve automatically
            """
        elif "unavailable" in error_msg.lower():
            error_response = "❌ <b>Video unavailable</b> - The video may be private, deleted, or restricted in your region."
        elif "private" in error_msg.lower():
            error_response = "❌ <b>Private video</b> - This video requires login or is not publicly available."
        elif "sign in" in error_msg.lower():
            error_response = "❌ <b>Login required</b> - This content requires authentication."
        else:
            error_response = f"❌ <b>Download error:</b>\n{error_msg[:200]}"
        
        bot.send_message(chat_id, error_response)
    
    finally:
        show_main_menu(chat_id)

# ========== Utility Functions ==========
def sanitize_filename(filename):
    """Sanitize filename for safe usage"""
    if not filename:
        return "media_file"
    
    # Remove unsafe characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename).strip()
    
    # Limit length
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
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
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
            'twitch.tv', 'www.twitch.tv',
            'reddit.com', 'www.reddit.com'
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
        
    def cleanup_old_files(self, max_age_minutes=30):
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
                    time.sleep(1800)  # 30 minutes
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
            '🔄 Convert Media',
            '📊 Status',
            'ℹ️ Help'
        ]
        
        # Add buttons in rows
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            markup.add(*[types.KeyboardButton(btn) for btn in row])
        
        welcome_text = """
🎉 <b>Welcome to Advanced Media Bot!</b>

⚡ <b>Available Features:</b>

• <b>Download Video</b> - High quality (720p)
• <b>Fast Download</b> - Lower quality for speed  
• <b>Audio Only</b> - Extract audio from videos
• <b>Search Music</b> - Find songs by lyrics/name
• <b>Convert Media</b> - File format conversion

🔧 <b>Enhanced System:</b>
• Better error handling
• Automatic retries
• Cloud optimized

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
        '📥 Download Video': {'type': 'video', 'quality': 'best', 'desc': 'High Quality Video Download'},
        '⚡ Fast Download': {'type': 'video', 'quality': 'fast', 'desc': 'Fast Download (Lower Quality)'},
        '🎵 Audio Only': {'type': 'audio', 'quality': 'best', 'desc': 'Audio Extraction from Video'}
    }
    
    config = configs[message.text]
    user_states[chat_id] = f'waiting_url_{config["type"]}_{config["quality"]}'
    
    instructions = f"""
📋 <b>{config['desc']}</b>

🔗 <b>Send the video URL now</b>

🌐 <b>Supported Platforms:</b>
• YouTube, Instagram, TikTok
• Facebook, Twitter, SoundCloud  
• Vimeo, Twitch, Reddit

💡 <b>Enhanced Features:</b>
• Automatic retry on errors
• Better error handling
• Multiple quality options

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
    
    # Extract configuration from state
    parts = current_state.split('_')
    download_type = parts[2]  # video or audio
    quality = parts[3]        # best or fast
    
    user_states[chat_id] = 'processing'
    
    # Start download in background thread
    thread = threading.Thread(
        target=handle_download_process,
        args=(chat_id, url, download_type, quality)
    )
    thread.daemon = True
    thread.start()
    
    bot.send_message(chat_id, "🚀 <b>Starting enhanced download process...</b>")

# ========== Music Search System ==========
@bot.message_handler(func=lambda message: message.text == '🔍 Search Music')
def handle_music_search(message):
    user_states[message.chat.id] = 'waiting_music_query'
    bot.send_message(
        message.chat.id,
        "🎵 <b>Music Search</b>\n\nSend song lyrics or title to search:\n\n<code>Example: shape of you ed sheeran</code>",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(func=lambda message: user_states.get(message.chat.id) == 'waiting_music_query')
def process_music_search(message):
    chat_id = message.chat.id
    query = message.text.strip()
    
    if len(query) < 2:
        bot.send_message(chat_id, "❌ <b>Please enter at least 2 characters</b>")
        show_main_menu(chat_id)
        return
    
    try:
        bot.send_message(chat_id, f"🔍 <b>Searching for:</b> <code>{query}</code>")
        
        # Enhanced yt-dlp options for search
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 15,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            },
        }
        
        search_url = f"ytsearch5:{query} official"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                bot.send_message(chat_id, "❌ <b>No results found</b>\n\nTry different keywords or check spelling.")
                show_main_menu(chat_id)
                return
            
            # Filter valid results
            entries = [e for e in info['entries'] if e and e.get('duration', 0) < 3600][:3]
            
            if not entries:
                bot.send_message(chat_id, "❌ <b>No valid results found</b>")
                show_main_menu(chat_id)
                return
            
            # Show results
            results_text = "🎵 <b>Top Results:</b>\n\n"
            for i, entry in enumerate(entries, 1):
                title = entry.get('title', 'Unknown Title')
                duration = format_duration(entry.get('duration'))
                results_text += f"{i}. {title}\n   ⏱️ {duration}\n\n"
            
            results_text += "⬇️ <b>Downloading first result with enhanced system...</b>"
            bot.send_message(chat_id, results_text)
            
            # Download first result
            first_result = entries[0]
            handle_download_process(chat_id, first_result['url'], 'audio', 'best')
            
    except Exception as e:
        logger.error(f"Music search error: {e}")
        bot.send_message(chat_id, f"❌ <b>Search error:</b> {str(e)[:100]}")
        show_main_menu(chat_id)

# ========== Additional Handlers ==========
@bot.message_handler(func=lambda message: message.text == '🔄 Convert Media')
def handle_conversion_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        '📷 Image to PDF', 
        '🎵 Video to MP3', 
        '🔙 Main Menu'
    ]
    
    markup.add(*[types.KeyboardButton(btn) for btn in buttons])
    
    bot.send_message(
        message.chat.id,
        "🔄 <b>Media Conversion Tools</b>\n\nChoose conversion type:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📊 Status')
def handle_status(message):
    status_text = """
📊 <b>System Status</b>

✅ <b>All Systems Operational</b>

🔧 <b>Enhanced Features:</b>
• Better error handling for 403 issues
• Automatic retry system (3 attempts)
• Multiple user agents to avoid blocking
• Improved download success rate

🌐 <b>Platform Support:</b>
• YouTube, Instagram, TikTok
• Facebook, Twitter, SoundCloud
• Vimeo, Twitch, Reddit

🚀 <b>Ready for downloads!</b>
    """
    
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help')
def handle_help(message):
    help_text = """
🛠️ <b>Enhanced Media Bot - Help Guide</b>

⚡ <b>Download Options:</b>
• <b>Download Video</b> - High quality (720p) with retry system
• <b>Fast Download</b> - Lower quality, faster download
• <b>Audio Only</b> - Extract audio from videos

🔍 <b>Music Search:</b>
• Search by lyrics or song title
• Automatic download of best match

🔄 <b>Conversion Tools:</b>
• Image to PDF conversion
• Video to MP3 extraction

🚀 <b>Enhanced Features:</b>
• Automatic retry on errors
• Better handling of 403 blocks
• Multiple fallback options
• Cloud-optimized performance

💡 <b>Tips for Success:</b>
• If one download fails, try the 'Fast Download' option
• The system automatically retries failed downloads
• Some videos may have restrictions that prevent download

<code>Choose any option from the main menu to start!</code>
    """
    
    bot.send_message(message.chat.id, help_text)

@bot.message_handler(func=lambda message: message.text == '🔙 Main Menu')
def handle_back_to_main(message):
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_unknown_messages(message):
    """Handle unknown messages"""
    if message.chat.id not in user_states:
        show_main_menu(message.chat.id)
    else:
        bot.send_message(
            message.chat.id,
            "❌ <b>Unknown command</b>\n\nPlease use the menu buttons or type /help for assistance."
        )

# ========== Main Execution ==========
if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Enhanced Media Bot...")
    print(f"🌐 Cloud Environment: {CLOUD_DEPLOYMENT}")
    print(f"📁 Temporary Directory: {TEMP_DIR}")
    print(f"🔧 FFmpeg Available: {FFMPEG_AVAILABLE}")
    print("=" * 60)
    print("🛡️  Enhanced features enabled:")
    print("   • Automatic retry system")
    print("   • Multiple user agents")
    print("   • Better 403 error handling")
    print("   • Enhanced download success rate")
    print("=" * 60)
    
    try:
        # Test bot initialization
        bot_info = bot.get_me()
        print(f"✅ Bot initialized: @{bot_info.username}")
        
        # Initial cleanup
        cleanup_manager.cleanup_old_files(max_age_minutes=0)
        
        print("📊 Enhanced bot is ready to receive requests...")
        print("=" * 60)
        
        # Start polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Bot crash: {e}")
    finally:
        print("🛑 Shutting down bot...")
        cleanup_manager.active = False
        print("✅ Bot stopped successfully")
