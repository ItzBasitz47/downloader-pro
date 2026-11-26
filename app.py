import os
import re
import uuid
import glob
import subprocess
import requests
import streamlit as st
import yt_dlp
from pytubefix import YouTube

st.set_page_config(page_title="Downloader Pro", layout="centered")
st.title("Downloader Pro")
st.caption("YouTube (8K/4K), Twitter (X), Insta, FB, TikTok & 1000+ Sites — Video & MP3")

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)


def fetch_twitter_video(tweet_url):
    match = re.search(r"(?:twitter\.com|x\.com)/([^/]+)/status/(\d+)", tweet_url)
    if not match:
        return None, None

    user, tweet_id = match.groups()
    api_url = f"https://api.fxtwitter.com/{user}/status/{tweet_id}"
    headers = {"User-Agent": "DownloaderPro/1.0"}

    try:
        r = requests.get(api_url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            videos = data.get("tweet", {}).get("media", {}).get("videos", [])
            if videos:
                video_url = videos[0].get("url")
                return video_url, f"twitter_{user}_{tweet_id}"
    except Exception:
        pass

    return None, None


def download_youtube_pytubefix(yt_url, quality, job_id):
    yt = None
    for client in ["ANDROID_VR", "WEB", "ANDROID"]:
        try:
            yt = YouTube(yt_url, client=client)
            if yt.streams:
                break
        except Exception:
            yt = None

    if yt is None:
        raise Exception("YouTube streams load nahi ho sake.")

    safe_title = re.sub(r'[\\/*?:"<>|]', "", yt.title or "youtube_video")[:50].strip() or "youtube_video"

    if quality == "Audio Only (MP3)":
        audio_stream = yt.streams.get_audio_only()
        raw_audio = audio_stream.download(
            output_path=DOWNLOAD_DIR,
            filename=f"{job_id}_yt_audio.{audio_stream.subtype}"
        )
        mp3_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_{safe_title}.mp3")
        subprocess.run(
            ["ffmpeg", "-y", "-i", raw_audio, "-vn", "-ab", "192k", mp3_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return mp3_path, f"{safe_title}.mp3"

    target_map = {
        "8K (4320p)": 4320,
        "4K (2160p)": 2160,
        "1080p Full HD": 1080,
        "720p HD": 720,
    }
    target_h = target_map.get(quality, 1080)

    video_streams = [
        s for s in yt.streams.filter(adaptive=True, only_video=True)
        if s.resolution and s.resolution.endswith("p")
    ]
    video_streams.sort(key=lambda s: int(s.resolution[:-1]), reverse=True)

    chosen_video = None
    for s in video_streams:
        if int(s.resolution[:-1]) <= target_h:
            chosen_video = s
            break
    if not chosen_video and video_streams:
        chosen_video = video_streams[0]

    audio_stream = yt.streams.get_audio_only()

    if chosen_video and audio_stream:
        vid_path = chosen_video.download(
            output_path=DOWNLOAD_DIR,
            filename=f"{job_id}_yt_vid.{chosen_video.subtype}"
        )
        aud_path = audio_stream.download(
            output_path=DOWNLOAD_DIR,
            filename=f"{job_id}_yt_aud.{audio_stream.subtype}"
        )
        merged_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_{safe_title}.mp4")
        subprocess.run(
            ["ffmpeg", "-y", "-i", vid_path, "-i", aud_path, "-c:v", "copy", "-c:a", "aac", merged_path],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return merged_path, f"{safe_title}.mp4"

    prog = yt.streams.get_highest_resolution()
    prog_path = prog.download(output_path=DOWNLOAD_DIR, filename=f"{job_id}_{safe_title}.mp4")
    return prog_path, f"{safe_title}.mp4"


url = st.text_input("Video / Reel / Tweet Link Paste Karein", placeholder="https://...")
quality = st.selectbox(
    "Quality / Format Select Karein",
    ["1080p Full HD", "4K (2160p)", "8K (4320p)", "720p HD", "Audio Only (MP3)"]
)
cookie_file = st.file_uploader("Optional: cookies.txt (Sirf private links ke liye)", type=["txt"])

if st.button("Process & Prepare Download", type="primary", use_container_width=True):
    clean_url = url.strip()
    if not clean_url:
        st.error("Pehle koi link paste karein.")
    else:
        job_id = str(uuid.uuid4())[:8]

        with st.spinner("Download aur convert ho raha hai... thora intezar karein"):
            try:
                file_path = None
                file_name = None

                # 1) Twitter / X ke liye direct fast API
                if "x.com/" in clean_url or "twitter.com/" in clean_url:
                    tw_video_url, base_name = fetch_twitter_video(clean_url)
                    if tw_video_url:
                        raw_mp4 = os.path.join(DOWNLOAD_DIR, f"{job_id}_{base_name}.mp4")
                        with requests.get(tw_video_url, stream=True, timeout=60) as resp:
                            resp.raise_for_status()
                            with open(raw_mp4, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=1024 * 256):
                                    if chunk:
                                        f.write(chunk)

                        if quality == "Audio Only (MP3)":
                            mp3_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_{base_name}.mp3")
                            subprocess.run(
                                ["ffmpeg", "-y", "-i", raw_mp4, "-vn", "-ab", "192k", mp3_path],
                                check=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            file_path = mp3_path
                            file_name = f"{base_name}.mp3"
                        else:
                            file_path = raw_mp4
                            file_name = f"{base_name}.mp4"

                # 2) YouTube ke liye pytubefix (bina cookies, 4K/8K support)
                elif "youtube.com" in clean_url or "youtu.be" in clean_url:
                    file_path, file_name = download_youtube_pytubefix(clean_url, quality, job_id)

                # 3) Baqi tamam sites (Insta, FB, TikTok, etc.) ke liye yt-dlp
                if not file_path:
                    out_tmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}_%(title).50s.%(ext)s")
                    ydl_opts = {
                        "outtmpl": out_tmpl,
                        "noplaylist": True,
                        "quiet": True,
                        "no_warnings": True,
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                    }

                    if cookie_file is not None:
                        cookie_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_cookies.txt")
                        with open(cookie_path, "wb") as f:
                            f.write(cookie_file.getvalue())
                        ydl_opts["cookiefile"] = cookie_path

                    if quality == "Audio Only (MP3)":
                        ydl_opts.update({
                            "format": "bestaudio/best",
                            "postprocessors": [{
                                "key": "FFmpegExtractAudio",
                                "preferredcodec": "mp3",
                                "preferredquality": "192",
                            }],
                        })
                    else:
                        height_map = {
                            "8K (4320p)": "4320",
                            "4K (2160p)": "2160",
                            "1080p Full HD": "1080",
                            "720p HD": "720",
                        }
                        height = height_map.get(quality, "1080")
                        ydl_opts.update({
                            "format": f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b",
                            "merge_output_format": "mp4",
                        })

                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        ydl.extract_info(clean_url, download=True)

                    matched_files = [
                        f for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}_*"))
                        if not f.endswith("_cookies.txt")
                    ]
                    if matched_files:
                        file_path = matched_files[0]
                        file_name = os.path.basename(file_path).replace(f"{job_id}_", "")

                if not file_path or not os.path.exists(file_path):
                    st.error("File download nahi ho saki. Link check karein.")
                else:
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()

                    st.success("Tayyar hai! Neeche button se save kar lein.")
                    st.download_button(
                        label=f"Save {file_name}",
                        data=file_bytes,
                        file_name=file_name,
                        mime="application/octet-stream",
                        use_container_width=True
                    )
            except Exception as e:
                st.error(f"Error: {str(e)}")
