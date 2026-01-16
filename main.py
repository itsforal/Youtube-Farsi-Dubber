import os
import logging
import asyncio
import shutil
import yt_dlp
import edge_tts
import nest_asyncio
import re
import time
from pathlib import Path
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator
from pydub import AudioSegment, effects

# Apply nest_asyncio to allow nested event loops (useful for Jupyter or specific IDEs)
nest_asyncio.apply()

# ==========================================
#              CONFIGURATION
# ==========================================

# INSERT YOUR YOUTUBE PLAYLIST OR VIDEO LINK HERE
TARGET_PLAYLIST_URL = "" 

# Destination directory for the final videos
# Ensure you have write permissions for this path
BASE_ROOT = Path(r"C:\persian youtub")     

# Whisper Model Size (Options: tiny, base, small, medium, large)
# 'medium.en' is recommended for good accuracy on English content.
MODEL_SIZE = "medium.en"

# --- Voice Settings ---
# Voice for general explanations (Farsi)
VOICE_FA = "fa-IR-DilaraNeural"  
# Voice for technical terms, math formulas, or code (English)
VOICE_EN = "en-US-JennyNeural"   

# ==========================================
#              LOGGING SETUP
# ==========================================
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger("AutoDubber")

class YouTubeToFarsiDub:
    def __init__(self, url, model_instance):
        self.url = url
        # Use a shared model instance to prevent reloading large models for every video
        self.model = model_instance 
        self.translator = GoogleTranslator(source='en', target='fa')
        self.video_title = ""
        self.work_dir = None
        self.temp_dir = None

    def sanitize_filename(self, name):
        """
        Cleans the filename to ensure compatibility with Windows file systems.
        Removes characters like / \ : * ? " < > |
        """
        clean_name = re.sub(r'[\\/*?:"<>|]', "", name).strip()
        # Limit length to 60 chars to prevent path length errors
        return clean_name[:60] 

    def clean_text(self, text):
        """
        Removes Whisper AI artifacts such as [Music], (Silence), etc.
        """
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\(.*?\)', '', text)
        return text.strip()

    def is_english_heavy(self, text):
        """
        Heuristic to determine if a sentence is mostly English/Math formulas.
        Returns True if English characters outnumber Farsi characters.
        """
        english_count = len(re.findall(r'[a-zA-Z0-9]', text))
        farsi_count = len(re.findall(r'[\u0600-\u06FF]', text))
        return english_count > farsi_count

    def setup_directories(self):
        """
        Fetches video metadata and creates the necessary folders.
        """
        logger.info(f"🔍 Fetching metadata for: {self.url}")
        try:
            # Extract video info without downloading
            with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
                info = ydl.extract_info(self.url, download=False)
                raw_title = info.get('title', 'Video_Untitled')
                self.video_title = self.sanitize_filename(raw_title)
                
            # Set paths
            self.work_dir = BASE_ROOT / self.video_title
            
            if not self.work_dir.exists():
                self.work_dir.mkdir(parents=True, exist_ok=True)
            
            self.temp_dir = self.work_dir / "temp_files"
            self.temp_dir.mkdir(exist_ok=True)
            
            return True
        except Exception as e:
            logger.error(f"❌ Error setting up directories: {e}")
            return False

    def download_video(self):
        """
        Downloads the video using yt-dlp.
        """
        logger.info(f" Downloading video...")
        output_path = self.work_dir / 'original_video.mp4'
        
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'outtmpl': str(output_path),
            'quiet': True,
            'no_warnings': True,
            'overwrites': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
                return output_path
        except Exception as e:
            logger.error(f"❌ Download Error: {e}")
            return None

    def transcribe_and_translate(self, video_path):
        """
        Extracts audio, transcribes it, translates it, and determines the best voice.
        """
        logger.info(" Extracting and Transcribing...")
        
        # Extract audio to a temp file
        audio_temp = self.temp_dir / "temp_audio.mp3"
        # -y: overwrite, -q:a 0: best quality audio
        cmd = f'ffmpeg -y -i "{video_path}" -q:a 0 -map a "{audio_temp}" -loglevel quiet'
        os.system(cmd)

        # Transcribe
        segments, _ = self.model.transcribe(str(audio_temp), beam_size=5, language="en", vad_filter=True)

        processed_segments = []
        logger.info(" Translating segments...")

        for i, segment in enumerate(segments):
            original_text = self.clean_text(segment.text)
            if len(original_text) < 2: continue
            
            try:
                # 1. Translate
                translated_text = self.translator.translate(original_text)
                
                # 2. Decide Voice (Hybrid Approach)
                if self.is_english_heavy(translated_text):
                    final_text = original_text 
                    voice = VOICE_EN
                else:
                    final_text = translated_text
                    voice = VOICE_FA

                processed_segments.append({
                    "start": segment.start,
                    "end": segment.end,
                    "text": final_text,
                    "voice": voice
                })
                
                if i % 10 == 0: print(".", end="", flush=True)
            except:
                continue
        
        print("\n")
        return processed_segments

    async def create_synced_audio(self, segments, total_duration):
        """
        Generates TTS audio and synchronizes it with the video timeline.
        """
        logger.info("🎹 Synthesizing Audio...")
        
        # Create a silent base track
        final_audio = AudioSegment.silent(duration=total_duration * 1000)
        
        for i, seg in enumerate(segments):
            start_ms = int(seg['start'] * 1000)
            end_ms = int(seg['end'] * 1000)
            available_duration_ms = end_ms - start_ms
            
            if available_duration_ms <= 0: continue

            temp_tts_path = self.temp_dir / f"seg_{i}.mp3"
            try:
                # Generate audio
                communicate = edge_tts.Communicate(seg['text'], seg['voice'])
                await communicate.save(str(temp_tts_path))
                
                seg_audio = AudioSegment.from_mp3(str(temp_tts_path))
                current_len_ms = len(seg_audio)

                # Time Stretching (Sync Logic)
                # If audio is too long, speed it up (max 1.5x to avoid chipmunk effect)
                if current_len_ms > available_duration_ms:
                    speed_factor = current_len_ms / available_duration_ms
                    if speed_factor > 1.5: 
                        speed_factor = 1.5
                    
                    seg_audio = effects.speedup(seg_audio, playback_speed=speed_factor)
                
                # Overlay on timeline
                final_audio = final_audio.overlay(seg_audio, position=start_ms)

            except Exception:
                pass

        output_audio = self.temp_dir / "final_farsi_audio.mp3"
        final_audio.export(output_audio, format="mp3")
        return output_audio

    def merge_output(self, video_path, farsi_audio_path):
        """
        Merges the original video with the new Farsi audio track using FFmpeg.
        """
        logger.info("🎬 Rendering Final Video...")
        output_filename = f"{self.video_title}_FARSI_DUBBED.mp4"
        final_path = self.work_dir / output_filename
        
        # Replace audio stream without re-encoding video stream
        cmd = (
            f'ffmpeg -y -i "{video_path}" -i "{farsi_audio_path}" '
            f'-c:v copy -map 0:v:0 -map 1:a:0 '
            f'-shortest "{final_path}" -loglevel error'
        )
        os.system(cmd)
        
        if final_path.exists():
            logger.info(f"✅ Video Saved: {final_path}")
        else:
            logger.error("❌ Error creating video.")

    async def process_video(self):
        """
        Runs the full pipeline for a single video.
        """
        if not self.setup_directories(): return

        video_path = self.download_video()
        if not video_path: return

        # Get duration
        try:
            probe = yt_dlp.ffmpeg.ffmpeg_probe(str(video_path))
            duration = float(probe['format']['duration'])
        except:
            duration = 600 # Default fallback

        segments = self.transcribe_and_translate(video_path)
        farsi_audio = await self.create_synced_audio(segments, duration)
        self.merge_output(video_path, farsi_audio)

        # Cleanup
        try:
            shutil.rmtree(self.temp_dir)
            logger.info("🧹 Temp files cleaned up.")
        except: pass

# ==========================================
#           PLAYLIST MANAGEMENT
# ==========================================
async def process_playlist():
    if not TARGET_PLAYLIST_URL:
        logger.error("❌ Please set the 'TARGET_PLAYLIST_URL' variable at the top of the script.")
        return

    # 1. Load Whisper Model ONCE
    logger.info(" Loading Whisper Model (Medium)...")
    shared_model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    
    # 2. Extract Playlist URLs
    logger.info(f" Extracting videos from playlist...")
    ydl_opts = {
        'extract_flat': True,
        'quiet': True,
    }
    
    video_urls = []
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(TARGET_PLAYLIST_URL, download=False)
        if 'entries' in info:
            for entry in info['entries']:
                video_urls.append(entry['url'])
    
    total_videos = len(video_urls)
    logger.info(f"🚀 Found {total_videos} videos in playlist.")
    
    # 3. Loop through videos
    for index, url in enumerate(video_urls):
        logger.info(f"\n{'='*40}")
        logger.info(f" Processing Video {index + 1}/{total_videos}")
        logger.info(f" URL: {url}")
        logger.info(f"{'='*40}\n")
        
        try:
            dubber = YouTubeToFarsiDub(url, shared_model)
            await dubber.process_video()
            
            # Small pause to be gentle on system resources
            time.sleep(2) 
        except Exception as e:
            logger.error(f"❌ Failed to process video {url}: {e}")
            continue 

if __name__ == "__main__":
    # Ensure FFmpeg is available
    if not shutil.which("ffmpeg"):
        logger.critical("❌ FFmpeg not found! Please install it and add it to System PATH.")
    else:
        asyncio.run(process_playlist())
