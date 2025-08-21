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

### Use Prebuilt binaries
Navigate to [releases page](./releases), then download a server and extension suitable for your usage.
- Extension: Packed and or signed packages are `ext-chrome.crx` (Compatible with all chromium based browsers), and `ext-firefox.crx` (Compatible with all firefox based browsers).
- Server: with the format `server-<OSName>.` All of which is prebuilt server binaries. In windows, you might get a warning from smartscreen, this can be safely ignored.

After downloading the prerequisites, import the extension to your browser.

Before opening the extension popup for usage, make sure to start the binary and wait until it is ready, you will know this by the `HTTP server started at http://127.0.0.1:8765` Message on the console.

While the server is running, you can use the extension to download any yt yt-dlp compatible videos, which will be stored in your default download folder. This behaviour can be changed by passing an extra argument to the server binary, e.g: `server-windows --download-directory=./`, which will send the downloaded files to the cwd.

Another possible option that can be passed is the base url required for an internally used plugin, which is [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider). You can use this by providing your own base url. e.g: `server-windows --bg-util-base="http://127.0.0.1:8080"`.



## Building
To build extension to distribute, run:
`python build_extension.py`

To build server for windows, run:
`pyinstaller --onefile --add-binary "ffmpeg.exe;." backend/server.py`

## License
MIT
~ Vibecoded