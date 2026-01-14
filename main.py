import argparse
import asyncio
import sys
import shutil
import logging
import nest_asyncio
from src.dubber import YouTubeToFarsiDub

# Apply nest_asyncio just in case relevant environments are used
nest_asyncio.apply()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Main")

def check_ffmpeg():
    if not shutil.which("ffmpeg"):
        logger.critical("❌ FFmpeg not found! Please install FFmpeg and add it to your PATH.")
        sys.exit(1)

def parse_arguments():
    parser = argparse.ArgumentParser(description="YouTube English to Farsi AI Dubber")
    parser.add_argument("url", help="The YouTube URL to process")
    parser.add_argument("--output", "-o", default="Farsi_Dubbed_Output", help="Output directory")
    parser.add_argument("--model", "-m", default="medium.en", help="Whisper model size (tiny.en, base.en, small.en, medium.en)")
    parser.add_argument("--voice", "-v", default="fa-IR-DilaraNeural", help="Edge-TTS Voice (fa-IR-DilaraNeural or fa-IR-FaridNeural)")
    return parser.parse_args()

async def main():
    check_ffmpeg()
    args = parse_arguments()

    print(f"""
    🚀 Starting AI Dubber
    ---------------------
    🔗 URL:    {args.url}
    📂 Output: {args.output}
    🧠 Model:  {args.model}
    🗣️ Voice:  {args.voice}
    ---------------------
    """)

    dubber = YouTubeToFarsiDub(
        output_dir=args.output,
        model_size=args.model,
        tts_voice=args.voice
    )
    
    await dubber.process_video(args.url)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Process stopped by user.")