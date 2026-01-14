# 🎥 AutoDubber: AI YouTube Video Dubbing Tool

An automated tool that downloads YouTube videos (or playlists), transcribes the audio using OpenAI's Whisper, translates it, generates voiceovers using Edge TTS, and synchronizes the new audio with the original video.

## 🚀 Features
- **Playlist Support:** Automatically processes all videos in a YouTube playlist.
- **Hybrid Voice Logic:** Uses English voice for math/technical terms and Farsi voice for explanations.
- **Auto Sync:** Adjusts speech speed to match the original video timing.
- **Resume Capability:** Skips videos that trigger errors and moves to the next.

## 🛠 Prerequisites
1. **Python 3.8+**
2. **FFmpeg:** Must be installed and added to your system PATH. [Download Here](https://ffmpeg.org/download.html).

## 📦 Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/AutoDubber.git
   cd AutoDubber
