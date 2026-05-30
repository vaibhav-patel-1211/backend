"""
POST /image - turn a text prompt into a Christian-themed picture.

The image_generator does the heavy lifting (safety check, prompt polish, Gemini
call, saving the file). If anything goes wrong it returns an "error" key rather
than raising, so we translate that into a 400 here.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import image_generator

router = APIRouter()


class ImageRequest(BaseModel):
    prompt: str


@router.post("/image")
def create_image(req: ImageRequest):
    """Generate one image and return its URL (plus a base64 copy)."""
    result = image_generator.generate_image(req.prompt)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {
        "image_url": result["image_url"],
        "image_base64": result["image_base64"],
        "prompt": result["prompt"],
    }
