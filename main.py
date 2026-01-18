from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
import yt_dlp
import tempfile
import os

app = FastAPI()


# --------------------------------------------------
# Endpoint 1: EXTRAER METADATOS Y AUDIO_URL (debug)
# --------------------------------------------------
@app.get("/extract")
def extract_audio(url: str = Query(..., description="YouTube Shorts or video URL")):
    ydl_opts = {
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get("formats", [])

            audio = next(
                (f for f in formats if f.get("acodec") != "none" and f.get("url")),
                None
            )

            if not audio:
                raise HTTPException(status_code=422, detail="No audio stream found")

            return JSONResponse({
                "title": info.get("title"),
                "duration": info.get("duration"),
                "audio_url": audio["url"],
                "ext": audio.get("ext", "m4a"),
                "source": info.get("webpage_url")
            })

    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# --------------------------------------------------
# Endpoint 2: DESCARGAR AUDIO REAL (SIN FFMPEG)
# --------------------------------------------------
@app.get("/audio")
def audio_file(url: str = Query(..., description="YouTube Shorts or video URL")):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, "audio.%(ext)s")

            ydl_opts = {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "outtmpl": outtmpl,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            files = os.listdir(tmpdir)
            if not files:
                raise HTTPException(status_code=500, detail="No audio file downloaded")

            path = os.path.join(tmpdir, files[0])

            if os.path.getsize(path) == 0:
                raise HTTPException(status_code=500, detail="Downloaded audio file is empty")

            def iterfile():
                with open(path, "rb") as f:
                    yield from f

            return StreamingResponse(
                iterfile(),
                media_type="audio/mpeg",
                headers={
                    "Content-Disposition": f'attachment; filename="{os.path.basename(path)}"'
                }
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error downloading audio: {e}")
