import os
import time
import logging
import asyncio
import yt_dlp
import edge_tts
from pathlib import Path
from faster_whisper import WhisperModel
from deep_translator import GoogleTranslator

# تنظیمات لاگ
logger = logging.getLogger("AutoDubber")

class YouTubeToFarsiDub:
    def __init__(self, output_dir: str = "output", model_size: str = "medium.en", tts_voice: str = "fa-IR-DilaraNeural"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_size = model_size
        self.tts_voice = tts_voice
        self.model = None
        self.translator = GoogleTranslator(source='en', target='fa')

    def _load_whisper(self):
        if not self.model:
            logger.info(f"⚙️ Loading Whisper Model ({self.model_size})...")
            # استفاده از float32 برای سازگاری بیشتر (یا int8 برای سرعت)
            try:
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
            except Exception:
                logger.warning("⚠️ Int8 failed, falling back to float32")
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="float32")

    def download_audio(self, url: str):
        logger.info(f"📥 Downloading audio from YouTube...")
        timestamp = int(time.time())
        temp_path = self.output_dir / f"original_eng_{timestamp}"
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': str(temp_path),
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3'}],
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                final_path = f"{temp_path}.mp3"
                title = info.get('title', 'video')
                return Path(final_path), title
        except Exception as e:
            logger.error(f"❌ Download Error: {e}")
            return None, None

    def transcribe_and_translate(self, audio_path: Path):
        self._load_whisper()
        logger.info("🎙️ Transcribing English Audio...")
        
        segments, _ = self.model.transcribe(
            str(audio_path), 
            beam_size=5, 
            language="en",
            vad_filter=True
        )

        full_farsi_text = []
        logger.info("🌍 Translating segments to Farsi...")
        
        for i, segment in enumerate(segments):
            eng_text = segment.text.strip()
            if len(eng_text) < 2: continue
            
            try:
                farsi_text = self.translator.translate(eng_text)
                full_farsi_text.append(farsi_text)
                
                if i % 10 == 0:
                    print(".", end="", flush=True)
            except Exception:
                pass

        print("\n")
        return " ".join(full_farsi_text)

    async def generate_farsi_audio(self, text: str, title: str):
        if not text:
            logger.error("❌ No text to convert.")
            return

        safe_title = "".join([c for c in title if c.isalnum() or c in " -_"]).strip()
        output_file = self.output_dir / f"{safe_title}_FARSI_DUB.mp3"
        
        logger.info(f"🗣️ Generating Farsi Voice ({self.tts_voice})...")
        
        try:
            communicate = edge_tts.Communicate(text, self.tts_voice)
            await communicate.save(str(output_file))
            logger.info(f"✅ DONE! Farsi Audio Saved: {output_file}")
            return output_file
        except Exception as e:
            logger.error(f"❌ TTS Error: {e}")
            return None

    async def process_video(self, url: str):
        # 1. Download
        result = self.download_audio(url)
        if not result or result[0] is None:
            return
        
        audio_path, title = result

        try:
            # 2 & 3. Transcribe & Translate (Run in thread to avoid blocking)
            farsi_text = await asyncio.to_thread(self.transcribe_and_translate, audio_path)
            
            # Save transcript
            text_file = audio_path.with_suffix(".txt")
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(farsi_text)
            logger.info(f"📝 Transcript saved to: {text_file}")
            
            # 4. Generate Audio
            await self.generate_farsi_audio(farsi_text, title)

        finally:
            if audio_path.exists():
                os.remove(audio_path)
                logger.info("🧹 Cleanup done.")