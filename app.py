import os
import re
import uuid
import glob
import subprocess
import requests
import streamlit as st
import yt_dlp

st.set_page_config(page_title="Downloader Pro", layout="centered")
st.title("Downloader Pro")
st.caption("Twitter (X), FB, Insta, YouTube & 1000+ Sites — 4K Video & MP3 Converter")

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


url = st.text_input("Video / Reel / Tweet Link Paste Karein", placeholder="https://...")
quality = st.selectbox(
    "Quality / Format Select Karein",
    ["1080p Full HD", "4K (2160p)", "720p HD", "Audio Only (MP3)"]
)
cookie_file = st.file_uploader("Optional: cookies.txt (Sirf YouTube/Private links ke liye)", type=["txt"])

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

                # 2) Baqi tamam sites (ya agar Twitter API fail ho) ke liye yt-dlp
                if not file_path:
                    out_tmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}_%(title).50s.%(ext)s")
                    ydl_opts = {
                        "outtmpl": out_tmpl,
                        "noplaylist": True,
                        "quiet": True,
                        "no_warnings": True,
                        "geo_bypass": True,
                        "nocheckcertificate": True,
                        "cachedir": False,
                        "source_address": "0.0.0.0",
                    }

                    # Sirf YouTube ke liye 403 bypass clients
                    if "youtube.com" in clean_url or "youtu.be" in clean_url:
                        ydl_opts["extractor_args"] = {
                            "youtube": {
                                "player_client": ["android_vr", "tv_embedded", "web"]
                            }
                        }

                    cookie_path = os.path.join(DOWNLOAD_DIR, f"{job_id}_cookies.txt")
                    if cookie_file is not None:
                        with open(cookie_path, "wb") as f:
                            f.write(cookie_file.getvalue())
                        ydl_opts["cookiefile"] = cookie_path
                    else:
                        try:
                            if "YOUTUBE_COOKIES" in st.secrets:
                                with open(cookie_path, "w", encoding="utf-8") as f:
                                    f.write(st.secrets["YOUTUBE_COOKIES"])
                                ydl_opts["cookiefile"] = cookie_path
                        except Exception:
                            pass

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
                            "4K (2160p)": "2160",
                            "1080p Full HD": "1080",
                            "720p HD": "720",
                        }
                        height = height_map[quality]
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
