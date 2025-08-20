import http.server
import socketserver
import json
import os
import sys
import uuid
import threading
from urllib.parse import urlparse, parse_qs
import yt_dlp # Requires: pip install yt-dlp
import re
from functools import lru_cache
import subprocess
from mutagen.mp3 import MP3
from mutagen.id3 import ID3
from mutagen.id3._frames import APIC

# --- Configuration ---
HOST = "127.0.0.1"
PORT = 8765
BGUTIL_BASE_URL = "http://stonelet:4416"
DOWNLOAD_JOBS = {}


def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)   

def get_default_download_path():
    if os.name == 'nt': return os.path.join(os.environ['USERPROFILE'], 'Downloads')
    else: return os.path.join(os.path.expanduser('~'), 'Downloads')
DOWNLOAD_PATH=get_default_download_path()


def get_youtube_video_id(url: str) -> str | None:
    pattern = re.compile(r"(?:https?:\/\/)?(?:www\.)?(?:m\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})")
    match = pattern.search(url)
    return match.group(1) if match else None

@lru_cache()
def _get_info_by_id(video_id: str):
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL({"noplaylist": True, "quiet": True, "extractor_args": {"youtubepot-bgutilhttp": {"base_url": BGUTIL_BASE_URL}}}) as ydl:
        return ydl.extract_info(url, download=False)

def get_info(url: str):
    video_id = get_youtube_video_id(url)
    if not video_id: raise ValueError(f"Invalid YouTube URL: {url}")
    return _get_info_by_id(video_id)

def time_str_to_seconds(time_str):
    try:
        parts = time_str.split(':'); h, m, s = int(parts[0]), int(parts[1]), float(parts[2])
        return h * 3600 + m * 60 + s
    except (ValueError, IndexError): return 0.0

def run_download(job_id, url, format_id, directory):
    """Runs the download, captures FFmpeg progress, and embeds thumbnails with mutagen."""
    temp_audio_path, temp_thumb_path = None, None
    try:
        DOWNLOAD_JOBS[job_id] = {"status": "starting", "progress": 0}
        download_path = directory or DOWNLOAD_PATH
        
        # We only need the full info dict for the duration in the MP3 case
        total_duration = 0
        if format_id == 'mp3':
            info = get_info(url)
            total_duration = info.get('duration', 0)

        ffmpeg_exe = "ffmpeg.exe" if os.name == 'nt' else "ffmpeg"
        final_filepath_from_hook = None
        info_dict_from_hook = {}

        def progress_hook(d):
            nonlocal final_filepath_from_hook, info_dict_from_hook
            if d['status'] == 'downloading':
                progress_str = re.search(r"(\d+\.?\d*)%", d.get('_percent_str', '0%'))
                if progress_str:
                    DOWNLOAD_JOBS[job_id].update({"status": "downloading", "progress": float(progress_str.group(1))})
            if d['status'] == 'finished':
                # THE FIX: Capture the info_dict here to get the correct filename and duration later.
                info_dict_from_hook = d.get('info_dict', {})
                final_filepath_from_hook = info_dict_from_hook.get('_filename')
                if format_id == 'mp3':
                    DOWNLOAD_JOBS[job_id].update({"status": "postprocessing", "progress": 0})
                    print(f"[JOB {job_id}] Download finished. Starting FFmpeg post-processing...")

        if format_id == 'mp3':
            temp_filename_base = f"{job_id}"
            ydl_opts_dl = {
                'format': 'bestaudio/best', 
                'outtmpl': os.path.join(download_path, f"{temp_filename_base}---%(title)s.%(ext)s"), 
                'progress_hooks': [progress_hook], 
                'noplaylist': True, 
                'quiet': True, 
                'no_color': True, 
                'writethumbnail': True
            }
            
            # THE FIX: Use a single YoutubeDL instance for the download.
            with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
                ydl.download([url])
            
            # Now that the download is done, info_dict_from_hook is populated.
            # We can now reliably get the final, sanitized filename.
            for f in os.listdir(download_path):
                if f.startswith(temp_filename_base):
                    if f.endswith(('.webp', '.jpg', '.png', '.jpeg')): temp_thumb_path = os.path.join(download_path, f)
                    else: temp_audio_path = os.path.join(download_path, f)
            if not temp_audio_path: raise Exception("Could not find temporary downloaded audio file.")
            final_mp3_path = os.path.join(download_path, temp_audio_path.split(f"{temp_filename_base}---")[1].split('.')[0]+'.mp3')
            # print(temp_audio_path, final_mp3_path)
            # print(resource_path(ffmpeg_exe))
            
            ffmpeg_command = [resource_path(ffmpeg_exe), '-y', '-i', temp_audio_path, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', final_mp3_path]
            
            process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            for line in iter(process.stderr.readline, ''):
                time_match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
                if time_match and total_duration > 0:
                    percent = (time_str_to_seconds(time_match.group(1)) / total_duration) * 100
                    DOWNLOAD_JOBS[job_id]["progress"] = min(percent, 100)
            
            # THE FIX: Ensure the FFmpeg process is completely finished before proceeding.
            process.wait()
            
            if temp_thumb_path:
                try:
                    print(f"[JOB {job_id}] Embedding thumbnail with mutagen...")
                    
                    # Convert thumbnail to a standard format (JPG) for max compatibility
                    temp_jpg_path = os.path.splitext(temp_thumb_path)[0] + '.jpg'
                    subprocess.run(['ffmpeg', '-y', '-i', temp_thumb_path, temp_jpg_path], check=True, capture_output=True)

                    # Now that FFmpeg is done, mutagen can safely access the file.
                    audio = MP3(final_mp3_path, ID3=ID3)
                    with open(temp_jpg_path, 'rb') as art:
                        audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=art.read()))
                    audio.save()
                    os.remove(temp_jpg_path) # Clean up the converted JPG
                    print(f"[JOB {job_id}] Thumbnail embedded.")
                except Exception as e:
                    print(f"[JOB {job_id}] Failed to embed thumbnail. Caught error: {e}")
            
            # ffmpeg_command = ['ffmpeg', '-y', '-i', temp_audio_path]
            # if temp_thumb_path:
            #     ffmpeg_command.extend(['-i', temp_thumb_path, '-map', '0:a:0', '-map', '1:v:0', '-c:v', 'copy', '-id3v2_version', '3'])
            
            # ffmpeg_command.extend(['-c:a', 'libmp3lame', '-b:a', '192k', final_mp3_path])
            
            # process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            # for line in iter(process.stderr.readline, ''):
            #     time_match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
            #     if time_match and total_duration > 0:
            #         percent = (time_str_to_seconds(time_match.group(1)) / total_duration) * 100
            #         DOWNLOAD_JOBS[job_id]["progress"] = min(percent, 100)
            # process.wait()

            # --- FFmpeg Conversion with Progress ---
            # ffmpeg_command = ['ffmpeg', '-y', '-i', temp_audio_path, '-vn', '-ar', '44100', '-ac', '2', '-b:a', '192k', final_mp3_path]
            # process = subprocess.Popen(ffmpeg_command, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            # for line in iter(process.stderr.readline, ''):
            #     time_match = re.search(r"time=(\d{2}:\d{2}:\d{2}\.\d{2})", line)
            #     if time_match and total_duration > 0:
            #         percent = (time_str_to_seconds(time_match.group(1)) / total_duration) * 100
            #         DOWNLOAD_JOBS[job_id]["progress"] = min(percent, 100)
            # process.wait()
            
            # --- Embed thumbnail using mutagen ---
            # if temp_thumb_path:
            #     print(f"[JOB {job_id}] Converting thumbnail and embedding...")
            #     temp_jpg_path = os.path.splitext(temp_thumb_path)[0] + '.jpg'
            #     subprocess.run(['ffmpeg', '-y', '-i', temp_thumb_path, temp_jpg_path], check=True, capture_output=True)
                
            #     audio = MP3(final_mp3_path, ID3=ID3)
            #     with open(temp_jpg_path, 'rb') as art:
            #         audio.tags.add(APIC(encoding=3, mime='image/jpeg', type=3, desc=u'Cover', data=art.read()))
            #     audio.save()
            #     os.remove(temp_jpg_path)
            #     print(f"[JOB {job_id}] Thumbnail embedded.")

            # --- Cleanup ---
            os.remove(temp_audio_path)
            if temp_thumb_path and os.path.exists(temp_thumb_path): os.remove(temp_thumb_path)
            DOWNLOAD_JOBS[job_id]["filepath"] = final_mp3_path
        else: # For regular video downloads
            ydl_opts = {'format': format_id, 'outtmpl': os.path.join(download_path, '%(title)s.%(ext)s'), 'progress_hooks': [progress_hook], 'noplaylist': True, 'quiet': True, 'no_color': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: ydl.download([url])
            DOWNLOAD_JOBS[job_id]["filepath"] = final_filepath_from_hook

        DOWNLOAD_JOBS[job_id].update({"status": "completed", "progress": 100})
        print(f"[JOB {job_id}] All processes complete.")
    except Exception as e:
        if temp_audio_path and os.path.exists(temp_audio_path): os.remove(temp_audio_path)
        if temp_thumb_path and os.path.exists(temp_thumb_path): os.remove(temp_thumb_path)
        print(f"[JOB {job_id}] Error: {e}")
        DOWNLOAD_JOBS[job_id] = {"status": "error", "details": str(e)}

class RequestHandler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self): self.send_header('Access-Control-Allow-Origin', '*'); self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'); self.send_header('Access-Control-Allow-Headers', 'Content-Type'); super().end_headers()
    def do_OPTIONS(self): self.send_response(204); self.end_headers()
    def do_GET(self):
        parsed_path = urlparse(self.path); query = parse_qs(parsed_path.query)
        if parsed_path.path == '/get_info':
            url = query.get('url', [None])[0]
            if not url: return self.send_error(400, "URL missing.")
            try:
                info = get_info(url)
                formats = []
                for f in info.get("formats", []):
                    if not f.get('format_id') or (f.get('vcodec') == 'none' and f.get('acodec') == 'none'): continue
                    size = f.get('filesize') or f.get('filesize_approx'); size_str = f"{(size / (1024*1024)):.2f} MB" if size else "N/A"
                    type_str = 'Video' if f.get('vcodec') != 'none' and f.get('acodec') != 'none' else 'Audio'
                    quality = f.get('format_note', f.get('resolution', 'Audio')); label = f"{quality} ({type_str})"
                    formats.append({"id": f['format_id'], "label": label, "size": size_str})
                response_data = {"title": info.get('title', 'Unknown'), "duration": f"{int(info.get('duration', 0) / 60)}:{int(info.get('duration', 0) % 60):02d}", "thumbnail": info.get('thumbnail', ''), "formats": formats}
                self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(response_data).encode('utf-8'))
            except Exception as e: self.send_error(500, f"Server error: {e}")
        elif parsed_path.path.startswith('/progress/'):
            job_id = parsed_path.path.split('/')[-1]; job_info = DOWNLOAD_JOBS.get(job_id)
            if job_info:
                self.send_response(200); self.send_header("Content-type", "application/json"); self.end_headers(); self.wfile.write(json.dumps(job_info).encode('utf-8'))
                if job_info["status"] in ["completed", "error"]: del DOWNLOAD_JOBS[job_id]
            else: self.send_error(404, "Job not found")
        else: self.send_error(404, "Endpoint not found")
    def do_POST(self):
        if self.path == '/download':
            try:
                payload = json.loads(self.rfile.read(int(self.headers['Content-Length']))); job_id = str(uuid.uuid4())
                threading.Thread(target=run_download, args=(job_id, payload["url"], payload["formatId"], "")).start()
                self.send_response(202); self.send_header("Content-type", "application/json"); self.end_headers(); self.wfile.write(json.dumps({"job_id": job_id}).encode('utf-8'))
            except Exception as e: self.send_error(400, f"Bad Request: {e}")
        else: self.send_error(404, "Endpoint not found")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("-b", "--bgutil-base", dest="bgutil_base_url", default=None, help="Overrides BG Util Base Url for DRM bypass.")
    parser.add_argument("-d", "--download-directory", dest="download_dir", default=get_default_download_path(), help="Override the download path, default='%s'" % get_default_download_path())
    args = parser.parse_args()
    if args.bgutil_base_url:
        BGUTIL_BASE_URL = args.bgutil_base_url
    if args.download_dir:
        DOWNLOAD_PATH=args.download_dir
    
    with socketserver.TCPServer((HOST, PORT), RequestHandler) as httpd:
        print(f"HTTP server started at http://{HOST}:{PORT}"); httpd.serve_forever()