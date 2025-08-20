# Simple YouTube Downloader Extension

A lightweight browser extension that connects to a local Python backend powered by [yt-dlp](https://github.com/yt-dlp/yt-dlp).  
It lets you download videos or audio directly from your browser with a simple and reliable interface.

## Features
- Clean and minimal design
- One-click video/audio download
- Progress bars for download stages
- Background process with persistent state
- Powered by `yt-dlp` for maximum compatibility

## Usage
### Running from source
1. Run the local Python backend with `yt-dlp`.
2. Install and load the extension in your browser.
3. Open a supported site, click the extension, and start downloading.

### Use Prebuilt binaries


## Building
To build extension to distribute, run:
`python build_extension.py`

To build server for windows, run:
`pyinstaller --onefile --add-binary "ffmpeg.exe;." backend/server.py`

## License
MIT
~ Vibecoded