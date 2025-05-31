import os
import re
import uuid
import yt_dlp
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

# Directory to store downloaded videos
DOWNLOAD_DIR = "downloaded_videos"

# Basic regex to validate YouTube video URLs (can be improved for more complex cases)
# Covers:
# - youtube.com/watch?v=VIDEO_ID
# - youtu.be/VIDEO_ID
# - youtube.com/embed/VIDEO_ID
# - youtube.com/shorts/VIDEO_ID
YOUTUBE_URL_PATTERN = re.compile(
    r"^(https?://)?(www\.)?"
    r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
    r"(watch\?v=|embed/|v/|.+\?v=|shorts/|sandalsResorts#\w+/\w+/)"
    r"([^&=%\?]{11})"
)

class VideoRequest(BaseModel):
    youtube_url: str

@app.on_event("startup")
async def startup_event():
    # Create download directory if it doesn't exist
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)

@app.post("/download_video/")
async def download_video(request: VideoRequest):
    video_url = request.youtube_url

    # Validate YouTube URL format
    if not YOUTUBE_URL_PATTERN.match(video_url):
        raise HTTPException(status_code=400, detail="Invalid YouTube URL format. Please provide a valid video URL.")

    unique_suffix = str(uuid.uuid4())[:8]
    filename_template = os.path.join(DOWNLOAD_DIR, f"%(title)s_%(id)s_{unique_suffix}.%(ext)s")

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': filename_template,
        'noplaylist': True,
        # 'quiet': True,
        # 'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)

            downloaded_filepath = None
            if 'requested_downloads' in info_dict and info_dict['requested_downloads']:
                downloaded_filepath = info_dict['requested_downloads'][0].get('filepath')
                if not downloaded_filepath:
                     downloaded_filepath = ydl.prepare_filename(info_dict['requested_downloads'][0])
            elif 'filepath' in info_dict:
                downloaded_filepath = info_dict.get('filepath')

            if not downloaded_filepath:
                downloaded_filepath = ydl.prepare_filename(info_dict)

            if not downloaded_filepath or not os.path.exists(downloaded_filepath):
                # This can happen if yt-dlp fails to report the path or the file is unexpectedly missing
                raise HTTPException(status_code=500, detail="Download succeeded but could not determine file path or file is missing.")

            filename = os.path.basename(downloaded_filepath)

            return {
                "status": "success",
                "filename": filename,
                "filepath": downloaded_filepath
            }

    except yt_dlp.utils.DownloadError as e:
        # This catches errors specifically from yt-dlp, like "video unavailable", "private video", etc.
        # The error message from yt-dlp (str(e)) is often informative.
        error_message = str(e)
        status_code = 500 # Default to 500
        if "video unavailable" in error_message.lower():
            status_code = 404 # Or another appropriate status
        elif "private video" in error_message.lower():
            status_code = 403
        # Add more specific checks if needed
        raise HTTPException(status_code=status_code, detail=f"Download failed: {error_message}")

    except HTTPException:
        # Re-raise HTTPException if it was raised intentionally (like the 400 or 500 above)
        raise

    except Exception as e:
        # Catches other unexpected errors during the process
        # Log this error for debugging as it's unexpected
        # logger.error(f"Unexpected error during video download: {str(e)}") # Placeholder for logging
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during the download process: {str(e)}")

# To run this app (from the terminal, in the directory of this file):
# uvicorn downloader_api:app --reload
# Then you can send POST requests to http://127.0.0.1:8000/download_video/
# with a JSON body like: {"youtube_url": "YOUR_YOUTUBE_VIDEO_URL_HERE"}
