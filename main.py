from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
import yt_dlp
import tempfile
import os

app = FastAPI()

@app.get("/extract")
def extract_audio(url: str = Query(...)):
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
                raise HTTPException(status_code=422, detail="No audio found")
            return JSONResponse({
                "title": info.get("title"),
                "duration": info.get("duration"),
                "audio_url": audio["url"],
                "ext": audio.get("ext", "m4a"),
                "source": info.get("webpage_url")
            })
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/audio")
def audio_file(url: str = Query(...)):
    """
    Descarga el audio en Railway (con yt-dlp) y lo devuelve como archivo.
    Esto evita el 403 en Make.
    """
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            outtmpl = os.path.join(tmpdir, "audio.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "noplaylist": True,
                "quiet": True,
                "outtmpl": outtmpl,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # yt-dlp escribe el fichero; lo localizamos
                requested = info.get("requested_downloads", [])
                if requested and requested[0].get("filepath"):
                    path = requested[0]["filepath"]
                else:
                    # fallback: buscar cualquier archivo en tmpdir
                    files = [f for f in os.listdir(tmpdir) if f.startswith("audio.")]
                    if not files:
                        raise HTTPException(status_code=500, detail="Audio file not found after download")
                    path = os.path.join(tmpdir, files[0])

            def iterfile():
                with open(path, "rb") as f:
                    yield from f

            filename = os.path.basename(path)
            return StreamingResponse(
                iterfile(),
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'}
            )

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error downloading audio: {e}")
