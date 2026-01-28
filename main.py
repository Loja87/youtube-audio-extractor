from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
import yt_dlp
import tempfile
import os
import shutil

app = FastAPI()


def _cleanup_dir(path: str):
    shutil.rmtree(path, ignore_errors=True)


@app.get("/extract")
def extract_audio(url: str = Query(...)):
    """
    Extrae metadata básica del vídeo (título/duración) y un audio_url (si está disponible).
    Usa cookies (YTDLP_COOKIES) para evitar el bloqueo "Sign in to confirm you're not a bot".
    """
    cookies_txt = os.getenv("YTDLP_COOKIES")
    tmpdir = tempfile.mkdtemp(prefix="ytdlp_extract_")
    cookies_path = None

    try:
        if cookies_txt:
            cookies_path = os.path.join(tmpdir, "cookies.txt")
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_txt)

        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "skip_download": True,
        }

        if cookies_path:
            ydl_opts["cookiefile"] = cookies_path

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
    finally:
        _cleanup_dir(tmpdir)


@app.get("/audio")
def audio_file(
    background_tasks: BackgroundTasks,
    url: str = Query(...)
):
    """
    Descarga el audio y devuelve un MP3.
    Usa cookies (YTDLP_COOKIES) para evitar bloqueos de YouTube.
    Limpia el directorio temporal al terminar la respuesta.
    """
    tmpdir = tempfile.mkdtemp(prefix="ytdlp_")
    outtmpl = os.path.join(tmpdir, "audio.%(ext)s")

    try:
        # --- COOKIES ---
        cookies_txt = os.getenv("YTDLP_COOKIES")
        cookies_path = None
        if cookies_txt:
            cookies_path = os.path.join(tmpdir, "cookies.txt")
            with open(cookies_path, "w", encoding="utf-8") as f:
                f.write(cookies_txt)

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

        if cookies_path:
            ydl_opts["cookiefile"] = cookies_path

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        mp3_path = next(
            (os.path.join(tmpdir, f) for f in os.listdir(tmpdir) if f.lower().endswith(".mp3")),
            None
        )

        if not mp3_path or os.path.getsize(mp3_path) == 0:
            raise HTTPException(status_code=500, detail="Audio file empty or not created")

        # Limpieza después de enviar el archivo (importantísimo)
        background_tasks.add_task(_cleanup_dir, tmpdir)

        return FileResponse(
            mp3_path,
            media_type="audio/mpeg",
            filename=os.path.basename(mp3_path)
        )

    except Exception as e:
        _cleanup_dir(tmpdir)
        raise HTTPException(status_code=400, detail=f"Error downloading audio: {e}")
