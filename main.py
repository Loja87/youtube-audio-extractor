from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import yt_dlp

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

            audio = next(
                (f for f in formats if f.get("acodec") != "none" and f.get("url")),
                None
            )

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
