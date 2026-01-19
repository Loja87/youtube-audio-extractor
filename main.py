from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
import yt_dlp
import tempfile
import os
import shutil

app = FastAPI()


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
            audio = next((f for f in formats if f.get("acodec") != "none" and f.get("url")), None)
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


def _cleanup_dir(path: str):
    try:
        shutil.rmtree(path, ignore_errors=True)
    except Exception:
        pass


@app.get("/audio")
def audio_file(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="YouTube Shorts or video URL")
):
    """
    Descarga el audio y devuelve un archivo real (NO streaming desde temp borrado).
    Se limpia el directorio temporal al terminar la respuesta.
    """
    tmpdir = tempfile.mkdtemp(prefix="ytdlp_")
    outtmpl = os.path.join(tmpdir, "audio.%(ext)s")

    try:
        ydl_opts = {
            "format": "bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "outtmpl": outtmpl,
            # Convierte a MP3 (requiere ffmpeg/ffprobe instalados)
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # Busca el mp3 generado
        mp3_path = None
        for f in os.listdir(tmpdir):
            if f.lower().endswith(".mp3"):
                mp3_path = os.path.join(tmpdir, f)
                break

        if not mp3_path:
            raise HTTPException(status_code=500, detail="MP3 not generated")

        if os.path.getsize(mp3_path) == 0:
            raise HTTPException(status_code=500, detail="Downloaded audio file is empty")

        # Limpieza al final (después de enviar el archivo)
        background_tasks.add_task(_cleanup_dir, tmpdir)

        return FileResponse(
            mp3_path,
            media_type="audio/mpeg",
            filename=os.path.basename(mp3_path),
        )

    except HTTPException:
        _cleanup_dir(tmpdir)
        raise
    except Exception as e:
        _cleanup_dir(tmpdir)
        raise HTTPException(status_code=400, detail=f"Error downloading audio: {e}")
