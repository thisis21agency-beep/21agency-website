import base64
import os
from typing import List, Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

app = FastAPI(title="PatternMatch AI")
app.mount("/static", StaticFiles(directory="static"), name="static")

class PatternPiece(BaseModel):
    name: str
    purpose: str

class GarmentAnalysis(BaseModel):
    garment_type: Literal[
        "dress", "corset_dress", "blouse", "shirt", "skirt",
        "trouser", "jumpsuit", "jacket", "bubu", "kaftan",
        "senator", "other"
    ]
    silhouette: str
    neckline: str
    sleeve: str
    waistline: str
    length: str
    construction_features: List[str]
    likely_base_pattern: str
    pattern_pieces: List[PatternPiece]
    pattern_modifications: List[str]
    measurements_needed: List[str]
    fabric_notes: List[str]
    difficulty: Literal["beginner", "intermediate", "advanced"]
    confidence: int = Field(ge=0, le=100)
    caution: str

SYSTEM_PROMPT = """You are a professional garment pattern-cutting assistant for tailors and fashion designers.

Study the uploaded garment reference image carefully. Reverse-engineer a practical pattern concept that can help a tailor recreate the visible garment.

Infer only what can reasonably be seen. Where a detail cannot be confirmed, state the most likely option conservatively.

Focus on:
- garment category and silhouette
- neckline, sleeves, waist placement and length
- visible panel lines, princess seams, darts, gathers, pleats, flare, drape and layering
- likely base block
- pattern pieces the tailor should prepare
- pattern modifications needed to recreate the design
- measurements still required from the client
- construction and fabric considerations

Do not claim the image alone creates a production-ready made-to-measure pattern.
The output is a tailor-friendly pattern concept that must be fitted and tested with a toile."""

@app.get("/")
def home():
    return FileResponse("static/index.html")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/analyse", response_model=GarmentAnalysis)
async def analyse_image(file: UploadFile = File(...)):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    data = await file.read()
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image is too large. Keep it under 12 MB.")

    data_url = "data:" + file.content_type + ";base64," + base64.b64encode(data).decode("utf-8")

    client = OpenAI(api_key=api_key)

    try:
        response = client.responses.parse(
            model=os.getenv("OPENAI_VISION_MODEL", "gpt-5.6-luna"),
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "input_text", "text": "Analyse this fashion reference and return the most useful pattern-cutting concept for a tailor."},
                    {"type": "input_image", "image_url": data_url, "detail": "high"},
                ]},
            ],
            text_format=GarmentAnalysis,
        )
        if not response.output_parsed:
            raise RuntimeError("No structured analysis was returned.")
        return response.output_parsed
    except Exception as exc:
        raise HTTPException(status_code=502, detail="AI analysis failed: " + str(exc)) from exc
