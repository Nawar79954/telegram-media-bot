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
from urllib.request import urlretrieve

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
                from PIL import Image, ImageFilter, ImageEnhance
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
from PIL import Image, ImageFilter, ImageEnhance, ImageDraw, ImageFont
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
user_sessions = {}

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

# ========== Advanced Cleanup System ==========
class AdvancedCleanup:
    def __init__(self):
        self.active = True
        self.cleanup_interval = 1800  # 30 minutes
        
    def cleanup_old_files(self, max_age_minutes=30):
        """Clean up old temporary files"""
        try:
            current_time = time.time()
            deleted_files = 0
            deleted_size = 0
            
            for filename in os.listdir(TEMP_DIR):
                file_path = os.path.join(TEMP_DIR, filename)
                if os.path.isfile(file_path):
                    file_age = (current_time - os.path.getctime(file_path)) / 60
                    if file_age > max_age_minutes:
                        try:
                            file_size = os.path.getsize(file_path)
                            os.unlink(file_path)
                            deleted_files += 1
                            deleted_size += file_size
                        except Exception as e:
                            logger.error(f"Failed to delete {filename}: {e}")
            
            if deleted_files > 0:
                size_mb = deleted_size / (1024 * 1024)
                logger.info(f"🧹 Cleaned {deleted_files} files ({size_mb:.2f} MB)")
                return deleted_files
            return 0
                
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
            return 0
    
    def get_storage_info(self):
        """Get storage information"""
        try:
            total_size = 0
            file_count = 0
            
            if os.path.exists(TEMP_DIR):
                for filename in os.listdir(TEMP_DIR):
                    file_path = os.path.join(TEMP_DIR, filename)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
                        file_count += 1
            
            return file_count, total_size
        except Exception as e:
            logger.error(f"Storage info error: {e}")
            return 0, 0
    
    def start_cleanup_daemon(self):
        """Start background cleanup daemon"""
        def daemon_loop():
            while self.active:
                try:
                    self.cleanup_old_files()
                    time.sleep(self.cleanup_interval)
                except Exception as e:
                    logger.error(f"Cleanup daemon error: {e}")
                    time.sleep(300)
        
        thread = threading.Thread(target=daemon_loop, daemon=True)
        thread.start()
        logger.info("✅ Cleanup daemon started")

# Initialize cleanup system
cleanup_manager = AdvancedCleanup()
cleanup_manager.start_cleanup_daemon()

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
            'reddit.com', 'www.reddit.com',
            'bilibili.com', 'www.bilibili.com'
        ]
        
        domain = urllib.parse.urlparse(url).netloc.lower()
        return any(supported in domain for supported in supported_domains)
        
    except Exception as e:
        logger.error(f"URL validation error: {e}")
        return False

# ========== Enhanced Download System ==========
def get_ydl_options(download_type='video', quality='best', format_spec=None):
    """Get yt-dlp options for different download types"""
    
    base_options = {
        'outtmpl': os.path.join(TEMP_DIR, '%(title).100s.%(ext)s'),
        'quiet': True,
        'no_warnings': False,
        'socket_timeout': 30,
        'retries': 3,
        'fragment_retries': 3,
        'skip_unavailable_fragments': True,
        'noplaylist': True,
        'extract_flat': False,
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
    elif format_spec:
        base_options.update({
            'format': format_spec,
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

def download_media(chat_id, url, download_type='video', quality='best', format_spec=None):
    """Download media with progress updates"""
    try:
        progress_msg = bot.send_message(chat_id, "🔍 <b>Analyzing URL...</b>")
        
        # First get video info
        ydl_opts = get_ydl_options(download_type, quality, format_spec)
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

📥 <b>Starting download...</b>
            """
            bot.edit_message_text(info_text, chat_id, progress_msg.message_id)
        
        # Actual download
        ydl_opts = get_ydl_options(download_type, quality, format_spec)
        ydl_opts['skip_download'] = False
        
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
            
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise

# ========== Core Download Handler ==========
def handle_download_process(chat_id, url, download_type='video', quality='best', format_spec=None):
    """Handle the complete download process"""
    try:
        # Validate URL
        if not is_supported_url(url):
            bot.send_message(chat_id, "❌ <b>Unsupported URL</b>\n\nSupported platforms: YouTube, Instagram, TikTok, Facebook, Twitter, SoundCloud, Vimeo, etc.")
            return
        
        # Start download
        info, file_path = download_media(chat_id, url, download_type, quality, format_spec)
        
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
        
        # User-friendly error messages
        if "Private" in error_msg:
            bot.send_message(chat_id, "❌ <b>Private content</b> - Cannot access this video")
        elif "unavailable" in error_msg.lower():
            bot.send_message(chat_id, "❌ <b>Content unavailable</b> - Video may be deleted or restricted")
        elif "Sign in" in error_msg:
            bot.send_message(chat_id, "❌ <b>Login required</b> - This content requires authentication")
        elif "georestricted" in error_msg.lower():
            bot.send_message(chat_id, "❌ <b>Geo-restricted</b> - Content not available in your region")
        else:
            bot.send_message(chat_id, f"❌ <b>Processing error:</b>\n{error_msg[:200]}")
    
    finally:
        show_main_menu(chat_id)

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
            '🛠️ Utilities',
            '📊 Status',
            'ℹ️ Help'
        ]
        
        # Add buttons in rows
        for i in range(0, len(buttons), 2):
            row = buttons[i:i+2]
            markup.add(*[types.KeyboardButton(btn) for btn in row])
        
        # Get system info
        file_count, total_size = cleanup_manager.get_storage_info()
        total_size_mb = total_size / (1024 * 1024)
        
        welcome_text = f"""
 <b>Welcome to MasTerDCS</b>

 <b>We Can Help You with::</b>

• <b>Download Video</b> - High quality (720p)
• <b>Fast Download</b> - Lower quality for speed  
• <b>Audio Only</b> - Extract audio from videos
• <b>Search Music</b> - Find songs by lyrics/name
• <b>Convert Media</b> - File format conversion
• <b>Utilities</b> - Image editing tools


📋 <b>Supported Platforms:</b>
YouTube, Instagram, TikTok, Facebook, Twitter, 
SoundCloud, Vimeo, Twitch, Reddit, and more!

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
• DailyMotion, Bilibili

💡 <b>Tips:</b>
• Use direct video links
• Avoid private/restricted content
• Large videos may take longer

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
    
    bot.send_message(chat_id, "🚀 <b>Starting download process...</b>")

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
        
        # Use yt-dlp to search YouTube
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'socket_timeout': 15,
        }
        
        search_url = f"ytsearch10:{query} official"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_url, download=False)
            
            if not info or 'entries' not in info or not info['entries']:
                bot.send_message(chat_id, "❌ <b>No results found</b>\n\nTry different keywords or check spelling.")
                show_main_menu(chat_id)
                return
            
            # Filter valid results
            entries = [e for e in info['entries'] if e and e.get('duration', 0) < 3600][:5]
            
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
            
            results_text += "⬇️ <b>Downloading first result...</b>"
            bot.send_message(chat_id, results_text)
            
            # Download first result
            first_result = entries[0]
            handle_download_process(chat_id, first_result['url'], 'audio', 'best')
            
    except Exception as e:
        logger.error(f"Music search error: {e}")
        bot.send_message(chat_id, f"❌ <b>Search error:</b> {str(e)[:100]}")
        show_main_menu(chat_id)

# ========== Media Conversion System ==========
@bot.message_handler(func=lambda message: message.text == '🔄 Convert Media')
def handle_conversion_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        '📷 Image to PDF', 
        '🎵 Video to MP3', 
        '🖼️ Image to JPG',
        '📹 Extract Audio',
        '🔙 Main Menu'
    ]
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.add(*[types.KeyboardButton(btn) for btn in row])
    
    bot.send_message(
        message.chat.id,
        "🔄 <b>Media Conversion Tools</b>\n\nChoose conversion type:",
        reply_markup=markup
    )

# Image to PDF Conversion
@bot.message_handler(func=lambda message: message.text == '📷 Image to PDF')
def handle_image_to_pdf(message):
    user_states[message.chat.id] = 'waiting_image_pdf'
    bot.send_message(
        message.chat.id,
        "📄 <b>Image to PDF Converter</b>\n\nSend the image you want to convert to PDF:",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(content_types=['photo'], func=lambda message: user_states.get(message.chat.id) == 'waiting_image_pdf')
def convert_image_to_pdf(message):
    try:
        chat_id = message.chat.id
        bot.send_message(chat_id, "⏳ <b>Processing your image...</b>")
        
        # Download the image
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # Save temporary image
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg', dir=TEMP_DIR) as tmp_img:
            tmp_img.write(downloaded_file)
            img_path = tmp_img.name
        
        pdf_path = None
        try:
            # Convert to PDF
            image = Image.open(img_path)
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            pdf_path = img_path.replace('.jpg', '.pdf')
            image.save(pdf_path, "PDF", resolution=100.0, quality=95)
            
            file_size = get_file_size(pdf_path)
            
            # Send PDF
            with open(pdf_path, 'rb') as pdf_file:
                bot.send_document(
                    chat_id, 
                    pdf_file, 
                    caption=f"✅ <b>Converted to PDF successfully!</b>\n📊 Size: {file_size}"
                )
                
        except Exception as e:
            bot.send_message(chat_id, f"❌ <b>Conversion error:</b> {str(e)}")
        
        finally:
            # Cleanup
            for path in [img_path, pdf_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
                    
    except Exception as e:
        logger.error(f"PDF conversion error: {e}")
        bot.send_message(message.chat.id, "❌ <b>Processing error</b>")
    
    finally:
        show_main_menu(message.chat.id)

# Video to MP3 Conversion
@bot.message_handler(func=lambda message: message.text == '🎵 Video to MP3')
def handle_video_to_mp3(message):
    user_states[message.chat.id] = 'waiting_video_mp3'
    bot.send_message(
        message.chat.id,
        "🎵 <b>Video to MP3 Converter</b>\n\nSend the video file to extract audio from (max 20MB):",
        reply_markup=types.ReplyKeyboardRemove()
    )

@bot.message_handler(content_types=['video'], func=lambda message: user_states.get(message.chat.id) == 'waiting_video_mp3')
def convert_video_to_mp3(message):
    try:
        chat_id = message.chat.id
        
        # Check file size
        if message.video.file_size > 20 * 1024 * 1024:
            bot.send_message(chat_id, "❌ <b>File too large!</b> Maximum size is 20MB")
            show_main_menu(chat_id)
            return
            
        bot.send_message(chat_id, "⏳ <b>Extracting audio from video...</b>")
        
        # Download video
        file_info = bot.get_file(message.video.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        video_path = os.path.join(TEMP_DIR, f"video_{message.message_id}.mp4")
        with open(video_path, 'wb') as f:
            f.write(downloaded_file)
        
        audio_path = None
        try:
            if FFMPEG_AVAILABLE:
                # Convert using FFmpeg
                audio_path = os.path.join(TEMP_DIR, f"audio_{message.message_id}.mp3")
                
                ffmpeg_cmd = [
                    'ffmpeg', '-i', video_path,
                    '-vn', '-acodec', 'libmp3lame',
                    '-ab', '192k', '-ar', '44100',
                    '-y', audio_path
                ]
                
                result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True, timeout=60)
                
                if result.returncode == 0 and os.path.exists(audio_path):
                    file_size = get_file_size(audio_path)
                    
                    with open(audio_path, 'rb') as audio_file:
                        bot.send_audio(
                            chat_id, 
                            audio_file,
                            caption=f"✅ <b>Audio extracted successfully!</b>\n📊 Size: {file_size}"
                        )
                else:
                    raise Exception("FFmpeg conversion failed")
            else:
                bot.send_message(chat_id, "❌ <b>FFmpeg not available</b> - This feature requires FFmpeg")
                
        except Exception as e:
            logger.error(f"MP3 extraction error: {e}")
            bot.send_message(chat_id, f"❌ <b>Extraction failed:</b> {str(e)[:100]}")
        
        finally:
            # Cleanup
            for path in [video_path, audio_path]:
                if path and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except:
                        pass
        
    except Exception as e:
        logger.error(f"Video to MP3 error: {e}")
        bot.send_message(message.chat.id, "❌ <b>Processing error</b>")
    
    finally:
        show_main_menu(message.chat.id)

# ========== Utilities System ==========
@bot.message_handler(func=lambda message: message.text == '🛠️ Utilities')
def handle_utilities_menu(message):
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [
        '📊 System Info',
        '🧹 Clean Storage', 
        '🔄 Format List',
        '🔙 Main Menu'
    ]
    
    for i in range(0, len(buttons), 2):
        row = buttons[i:i+2]
        markup.add(*[types.KeyboardButton(btn) for btn in row])
    
    bot.send_message(
        message.chat.id,
        "🛠️ <b>Utility Tools</b>\n\nChoose a utility:",
        reply_markup=markup
    )

@bot.message_handler(func=lambda message: message.text == '📊 System Info')
def show_system_info(message):
    """Show detailed system information"""
    try:
        # Get storage info
        file_count, total_size = cleanup_manager.get_storage_info()
        total_size_mb = total_size / (1024 * 1024)
        
        # Get system info
        disk_usage = psutil.disk_usage('/')
        memory_usage = psutil.virtual_memory()
        
        status_text = f"""
🤖 <b>System Status Report</b>

📍 <b>Deployment:</b> {'🌐 Railway Cloud' if CLOUD_DEPLOYMENT else '💻 Local'}
🔧 <b>FFmpeg:</b> {'✅ Available' if FFMPEG_AVAILABLE else '❌ Not Available'}
🐍 <b>Python:</b> {sys.version.split()[0]}

💾 <b>Storage Information:</b>
• Temporary Files: {file_count}
• Storage Used: {total_size_mb:.1f} MB
• Total Disk: {disk_usage.total // (1024**3)} GB
• Free Disk: {disk_usage.free // (1024**3)} GB

📊 <b>System Resources:</b>
• Memory Usage: {memory_usage.percent}%
• Active Users: {len(user_states)}

🔄 <b>Services Status:</b>
• Download System: ✅ Operational
• Conversion Tools: ✅ Operational  
• Search System: ✅ Operational
• Cleanup System: ✅ Active

✅ <b>All systems are running optimally</b>
        """
        
        bot.send_message(message.chat.id, status_text)
        
    except Exception as e:
        logger.error(f"System info error: {e}")
        bot.send_message(message.chat.id, "❌ <b>Error getting system information</b>")

@bot.message_handler(func=lambda message: message.text == '🧹 Clean Storage')
def handle_storage_cleanup(message):
    """Clean temporary storage"""
    deleted_files = cleanup_manager.cleanup_old_files(max_age_minutes=0)
    if deleted_files > 0:
        bot.send_message(message.chat.id, f"🧹 <b>Cleaned {deleted_files} temporary files!</b>")
    else:
        bot.send_message(message.chat.id, "✅ <b>No temporary files to clean</b>")

# ========== Additional Commands ==========
@bot.message_handler(func=lambda message: message.text == '🔙 Main Menu')
def handle_back_to_main(message):
    show_main_menu(message.chat.id)

@bot.message_handler(func=lambda message: message.text == '📊 Status')
def handle_quick_status(message):
    """Quick status command"""
    file_count, total_size = cleanup_manager.get_storage_info()
    total_size_mb = total_size / (1024 * 1024)
    
    status_text = f"""
📊 <b>Quick Status</b>

• Active Users: {len(user_states)}
• Temp Files: {file_count}
• Storage Used: {total_size_mb:.1f} MB
• FFmpeg: {'✅' if FFMPEG_AVAILABLE else '❌'}
• System: ✅ Operational
    """
    
    bot.send_message(message.chat.id, status_text)

@bot.message_handler(func=lambda message: message.text == 'ℹ️ Help')
def handle_help_command(message):
    """Comprehensive help guide"""
    help_text = """
🛠️ <b>Advanced Media Bot - Complete Guide</b>

⚡ <b>Download Options:</b>
• <b>Download Video</b> - High quality (720p) videos
• <b>Fast Download</b> - Lower quality for faster downloads
• <b>Audio Only</b> - Extract audio from any video

🔍 <b>Music Search:</b>
• Search by lyrics or song title
• Automatic download of best match

🔄 <b>Conversion Tools:</b>
• <b>Image to PDF</b> - Convert images to PDF documents
• <b>Video to MP3</b> - Extract audio from video files
• <b>Image to JPG</b> - Convert images to JPG format

🛠️ <b>Utilities:</b>
• System information and status
• Storage management
• Format information

📋 <b>Supported Platforms:</b>
YouTube, Instagram, TikTok, Facebook, Twitter, 
SoundCloud, Vimeo, Twitch, Reddit, DailyMotion, Bilibili

💡 <b>Quick Commands:</b>
/start - Main menu
/status - System status
/clean - Clean temporary files

🚀 <b>Ready to use! Choose any option from the main menu.</b>
    """
    
    bot.send_message(message.chat.id, help_text)

# ========== Admin Commands ==========
@bot.message_handler(commands=['status'])
def command_status(message):
    handle_quick_status(message)

@bot.message_handler(commands=['clean'])
def command_clean(message):
    handle_storage_cleanup(message)

@bot.message_handler(commands=['stats'])
def command_stats(message):
    """Detailed statistics"""
    file_count, total_size = cleanup_manager.get_storage_info()
    total_size_mb = total_size / (1024 * 1024)
    
    stats_text = f"""
📈 <b>Bot Statistics</b>

👥 <b>Users:</b>
• Active Sessions: {len(user_states)}
• Total Memory: {len(user_sessions)}

💾 <b>Storage:</b>
• Temporary Files: {file_count}
• Total Size: {total_size_mb:.1f} MB

🌐 <b>Environment:</b>
• Platform: {'Railway' if CLOUD_DEPLOYMENT else 'Local'}
• FFmpeg: {'Available' if FFMPEG_AVAILABLE else 'Not Available'}
• Python: {sys.version.split()[0]}

🕒 <b>Uptime:</b> Bot is running smoothly
    """
    
    bot.send_message(message.chat.id, stats_text)

# ========== Fallback Handler ==========
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
    print("🚀 Starting Advanced Media Bot...")
    print(f"🌐 Cloud Environment: {CLOUD_DEPLOYMENT}")
    print(f"📁 Temporary Directory: {TEMP_DIR}")
    print(f"🔧 FFmpeg Available: {FFMPEG_AVAILABLE}")
    print("=" * 60)
    
    try:
        # Test bot initialization
        bot_info = bot.get_me()
        print(f"✅ Bot initialized: @{bot_info.username}")
        
        # Initial cleanup
        initial_cleanup = cleanup_manager.cleanup_old_files(max_age_minutes=0)
        if initial_cleanup > 0:
            print(f"🧹 Initial cleanup: {initial_cleanup} files removed")
        
        print("📊 Bot is ready to receive requests...")
        print("=" * 60)
        
        # Start polling
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        logger.error(f"Bot crash: {e}")
    finally:
        print("🛑 Shutting down bot...")
        cleanup_manager.active = False
        final_cleanup = cleanup_manager.cleanup_old_files(max_age_minutes=0)
        if final_cleanup > 0:
            print(f"🧹 Final cleanup: {final_cleanup} files removed")
        print("✅ Bot stopped successfully")
