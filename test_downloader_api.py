import os
import shutil
import pytest
from fastapi.testclient import TestClient
from downloader_api import app # Assuming your FastAPI app instance is named 'app'

client = TestClient(app)

# --- Test Data ---
# A well-known, generally available YouTube video.
# Replace with a more stable public domain or Creative Commons video if possible.
VALID_YOUTUBE_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
# An example of a URL that yt-dlp might identify as unavailable or private.
# This is hard to guarantee. If tests are flaky, mocking yt_dlp.YoutubeDL is better.
# For now, we use a URL format that would trigger yt-dlp to check.
# Using a non-existent video ID.
UNAVAILABLE_YOUTUBE_URL = "https://www.youtube.com/watch?v=hopefullyNoOneUsesThisID"
INVALID_URL_FORMAT = "not_a_youtube_url_at_all"
DOWNLOAD_DIR = "downloaded_videos"


# --- Helper for Cleanup ---
def cleanup_downloaded_file(filepath):
    if filepath and os.path.exists(filepath):
        os.remove(filepath)
    if os.path.exists(DOWNLOAD_DIR) and not os.listdir(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)
    elif os.path.exists(DOWNLOAD_DIR) and os.path.isdir(DOWNLOAD_DIR) and len(os.listdir(DOWNLOAD_DIR)) == 0 : # Redundant check, but safe
        shutil.rmtree(DOWNLOAD_DIR)


# --- Test Functions ---

def test_download_video_success():
    """Tests successful video download."""
    downloaded_filepath = None
    try:
        response = client.post("/download_video/", json={"youtube_url": VALID_YOUTUBE_URL})

        assert response.status_code == 200
        response_data = response.json()

        assert "status" in response_data
        assert "filename" in response_data
        assert "filepath" in response_data
        assert response_data["status"] == "success"

        downloaded_filepath = response_data.get("filepath")
        assert downloaded_filepath is not None, "Filepath should not be null"
        assert os.path.exists(downloaded_filepath), f"File not found at {downloaded_filepath}"
        assert os.path.isfile(downloaded_filepath), f"Path is not a file {downloaded_filepath}"
        assert os.path.getsize(downloaded_filepath) > 0, "Downloaded file is empty"

    finally:
        # Cleanup
        if downloaded_filepath:
            cleanup_downloaded_file(downloaded_filepath)


def test_download_video_invalid_url_format():
    """Tests download attempt with a malformed/invalid YouTube URL."""
    response = client.post("/download_video/", json={"youtube_url": INVALID_URL_FORMAT})

    assert response.status_code == 400 # As per refined error handling
    response_data = response.json()
    assert "detail" in response_data
    assert "Invalid YouTube URL format" in response_data["detail"]


def test_download_video_unavailable_or_private():
    """
    Tests download attempt for a video that is unavailable or private.
    Note: The stability of UNAVAILABLE_YOUTUBE_URL is a concern.
    Mocking yt_dlp may be needed if this test is flaky.
    """
    response = client.post("/download_video/", json={"youtube_url": UNAVAILABLE_YOUTUBE_URL})

    # Expecting 403 (private) or 404 (unavailable) or 500 (general yt-dlp download error)
    # based on the refined error handling in downloader_api.py
    assert response.status_code in [403, 404, 500]
    response_data = response.json()
    assert "detail" in response_data
    # The detail message will come from yt-dlp, so it can vary.
    # Example: "Video unavailable", "Private video", or other yt-dlp errors.
    assert "Download failed:" in response_data["detail"] or "unavailable" in response_data["detail"].lower()


# --- Optional: Test for download directory creation (if not covered by success test implicitly) ---
def test_download_directory_created_on_startup():
    """
    Tests if the DOWNLOAD_DIR is created by the startup event if it doesn't exist.
    This test is a bit indirect as TestClient doesn't fully run startup events
    in the same way a real server does for every test.
    However, the first call to the client *should* trigger it.
    A more direct way would be to call the startup event handler manually if needed.
    """
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR) # Ensure it doesn't exist before test

    # Make any request to trigger startup event if it hasn't run
    client.post("/download_video/", json={"youtube_url": INVALID_URL_FORMAT})

    # The directory should be created by the startup event in downloader_api.py
    assert os.path.exists(DOWNLOAD_DIR)
    assert os.path.isdir(DOWNLOAD_DIR)

    # Clean up the directory after test
    if os.path.exists(DOWNLOAD_DIR):
        shutil.rmtree(DOWNLOAD_DIR)

# To run these tests:
# Ensure you have installed pytest and httpx (they are in requirements.txt)
# From the terminal, in the root directory of the project:
# pytest
#
# You might need to set PYTHONPATH if downloader_api is not found:
# export PYTHONPATH=.
# pytest
#
# Or:
# python -m pytest
#
# Note on `VALID_YOUTUBE_URL` and `UNAVAILABLE_YOUTUBE_URL`:
# These URLs might become invalid over time. For robust CI/CD, consider:
# 1. Using videos you own and control.
# 2. Mocking the `yt_dlp.YoutubeDL` class to return predictable results
#    without actual network calls. This is the most robust solution for unit tests.
#    For this exercise, live calls are used as per initial instructions.
