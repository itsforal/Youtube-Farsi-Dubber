# 🎥 AutoDubber: Automated Video Translation Pipeline

An experimental Python utility designed to automate the dubbing workflow for educational videos. It integrates **OpenAI Whisper** for transcription and **Edge TTS** for voice synthesis to create bilingual audio overlays.

## Key Features
- **Batch Processing:** Iterates through YouTube playlists to process multiple videos sequentially.
- **Context-Aware Voice Switching:** Alternates between English (for technical/math terms) and Farsi (for explanations) to preserve scientific accuracy.
- **Temporal Alignment:** Dynamically adjusts the speed (tempo) of the generated audio to match the original video segments.
- **Error Handling:** Implements logic to skip corrupted streams and resume processing automatically.

## Prerequisites
1. **Python 3.8+**
2. **FFmpeg:** Required for audio extraction and merging operations. [Download Here](https://ffmpeg.org/download.html).
