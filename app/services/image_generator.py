"""
Make Christian-themed images with NVIDIA FLUX.

The flow is: refuse anything unsafe, polish the prompt so the result looks
reverent, call NVIDIA's FLUX model, save the PNG, and hand back a URL.
"""
import base64
import os
import uuid

import requests

from app.config import settings
from app.prompts import IMAGE_PROMPT_TEMPLATE
from app.services import guardrails

_STATIC_URL_PREFIX = "/static/images"
_NVIDIA_IMAGE_URL = "https://ai.api.nvidia.com/v1/genai/black-forest-labs/flux.2-klein-4b"


def enhance_prompt(prompt: str) -> str:
    return IMAGE_PROMPT_TEMPLATE.format(subject=prompt.strip())


def _save_png(image_bytes: bytes) -> str:
    os.makedirs(settings.IMAGE_DIR, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.png"
    with open(os.path.join(settings.IMAGE_DIR, filename), "wb") as f:
        f.write(image_bytes)
    return f"{_STATIC_URL_PREFIX}/{filename}"


def generate_image(prompt: str) -> dict:
    safe, reason = guardrails.is_image_safe(prompt)
    if not safe:
        return {"error": f"Image request rejected: {reason}"}
    if not settings.NVIDIA_API_KEY:
        return {"error": "NVIDIA_API_KEY is not configured."}

    enhanced = enhance_prompt(prompt)

    try:
        response = requests.post(
            _NVIDIA_IMAGE_URL,
            headers={
                "Authorization": f"Bearer {settings.NVIDIA_API_KEY}",
                "Accept": "application/json",
            },
            json={
                "prompt": enhanced,
                "width": 1024,
                "height": 1024,
                "seed": 0,
                "steps": 4,
            },
        )
        response.raise_for_status()
        data = response.json()

        # The API returns base64-encoded image in the response
        image_b64 = data.get("image") or data.get("artifacts", [{}])[0].get("base64", "")
        if not image_b64:
            return {"error": "No image was returned by the model."}

        image_bytes = base64.b64decode(image_b64)

        return {
            "image_url": _save_png(image_bytes),
            "image_base64": f"data:image/png;base64,{image_b64}",
            "prompt": enhanced,
        }
    except Exception as e:
        return {"error": f"Image generation failed: {e}"}
