import os
import uuid
import glob
import streamlit as st
import yt_dlp

st.set_page_config(page_title="Downloader Pro", layout="centered")
st.title("Downloader Pro")
st.caption("YouTube, Insta, FB, X (Twitter) & 1000+ Sites — 4K Video & MP3 Converter")

DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

url = st.text_input("Video / Reel Link Paste Karein", placeholder="https://...")
quality = st.selectbox(
    "Quality / Format Select Karein",
    ["1080p Full HD", "4K (2160p)", "720p HD", "Audio Only (MP3)"]
)
cookie_file = st.file_uploader("Optional: cookies.txt (Agar YouTube/Insta bot error de)", type=["txt"])

if st.button("Process & Prepare Download", type="primary", use_container_width=True):
    if not url.strip():
        st.error("Pehle koi link paste karein.")
    else:
        job_id = str(uuid.uuid4())[:8]
        out_tmpl = os.path.join(DOWNLOAD_DIR, f"{job_id}_%(title).50s.%(ext)s")

        ydl_opts = {
            "outtmpl": out_tmpl,
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "geo_bypass": True,
            "nocheckcertificate": True,
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

        with st.spinner("Download aur convert ho raha hai... thora intezar karein"):
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.extract_info(url.strip(), download=True)

                matched_files = [
                    f for f in glob.glob(os.path.join(DOWNLOAD_DIR, f"{job_id}_*"))
                    if not f.endswith("_cookies.txt")
                ]

                if not matched_files:
                    st.error("File download nahi ho saki.")
                else:
                    file_path = matched_files[0]
                    file_name = os.path.basename(file_path).replace(f"{job_id}_", "")
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
