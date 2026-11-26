"""Cloudflare Workers AI adapter for FLUX images (unit U3): reference sheets and keyframes.

FLUX.2 klein takes multipart form data, even for a text-only call, width and height from 256
to 1920, a seed, and up to four reference images (input_image_0..3), each under 512x512; we
downscale references to fit before sending. FLUX.1 schnell, the fallback, takes JSON with
only a prompt and steps. Both answer {"result": {"image": <base64>}}. Keys come from .env
and are never logged. Docs checked 2026-11-25."""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path

from PIL import Image

from ..engine.retry import BadRequestError, DailyQuotaError, ProviderError, SafetyBlockError, TransientError
from ..env import need

API = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
TIMEOUT_S = 120


class CloudflareImage:
    name = "cloudflare"

    def __init__(self, model: str, reference_max: int = 504):
        self.model = model
        self.reference_max = reference_max

    def _post(self, **kwargs):
        import requests

        keys = need("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN")
        url = API.format(account=keys["CLOUDFLARE_ACCOUNT_ID"], model=self.model)
        try:
            return requests.post(url, headers={"Authorization": f"Bearer {keys['CLOUDFLARE_API_TOKEN']}"},
                                 timeout=TIMEOUT_S, **kwargs)
        except requests.Timeout as e:
            raise TransientError("Cloudflare timed out") from e
        except requests.ConnectionError as e:
            raise TransientError("Cloudflare connection failed") from e

    def generate(self, *, prompt: str, seed: int, size, refs: list[Path], out: Path) -> dict:
        w, h = size
        if "flux-2" in self.model:
            fields = {"prompt": prompt, "seed": str(seed), "width": str(w), "height": str(h)}
            files = [(f"input_image_{i}", (f"ref{i}.png", self._shrink(p), "image/png")) for i, p in enumerate(refs[:4])]
            multipart = [(k, (None, v)) for k, v in fields.items()] + files
            resp = self._post(files=multipart)
        else:
            if refs:
                raise BadRequestError(f"{self.model} takes no reference images")
            # schnell's schema takes only prompt and steps (no seed, no size), so a schnell image
            # can't be reproduced exactly; the log says so.
            resp = self._post(json={"prompt": prompt, "steps": 4})
        image = _image_bytes(resp)
        Image.open(io.BytesIO(image)).convert("RGB").save(out, format="PNG")
        params = {"refs": len(refs), "width": w, "height": h}
        if "flux-2" not in self.model:
            params.update(seed_ignored=True, size_ignored=True)
        return {"model": self.model, "params": params}

    def _shrink(self, path: Path) -> bytes:
        img = Image.open(path).convert("RGB")
        img.thumbnail((self.reference_max, self.reference_max))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def _image_bytes(resp) -> bytes:
    body = resp.text if "json" in resp.headers.get("content-type", "") else ""
    if resp.status_code != 200:
        raise classify(resp.status_code, body or resp.text[:500])
    if resp.headers.get("content-type", "").startswith("image/"):
        return resp.content
    data = resp.json()
    if not data.get("success", True):
        raise classify(resp.status_code, body)
    result = data.get("result", data)
    encoded = result.get("image") if isinstance(result, dict) else None
    if not encoded:
        raise BadRequestError(f"Cloudflare returned no image: {body[:300]}")
    return base64.b64decode(encoded)


def classify(status: int, body: str) -> ProviderError:
    """Error 3036 (the 10,000-neuron daily free allocation, reset 00:00 UTC) is a daily quota;
    3040 (out of capacity) and other 429s are worth retrying."""
    text = body or ""
    if re.search(r'"code"\s*:\s*3036\b', text) or re.search(r"daily free allocation", text, re.IGNORECASE):
        return DailyQuotaError(f"Cloudflare daily allowance used up: {text[:200]}", cap=10000)
    if status == 429:
        return TransientError("Cloudflare rate limit")
    if status >= 500:
        return TransientError(f"Cloudflare {status}")
    if re.search(r"nsfw|safety|flagged", text, re.IGNORECASE):
        return SafetyBlockError(f"Cloudflare blocked the prompt: {text[:200]}")
    if status in (400, 404, 413, 422):
        return BadRequestError(f"Cloudflare {status}: {text[:300]}")
    return ProviderError(f"Cloudflare {status}: {text[:300]}")
