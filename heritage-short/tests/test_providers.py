"""Real provider adapters, offline: errors map to the engine's classes, audio comes out as WAV,
and Cloudflare requests carry the fields the docs ask for. No network, no keys."""
import base64
import io
import json
import wave

import pytest
from google.genai import errors
from PIL import Image

from pipeline.engine.retry import BadRequestError, DailyQuotaError, SafetyBlockError, TransientError
from pipeline.providers import cloudflare, gemini


def api_error(code, quota_id=None, extra=None):
    details = [{"@type": "type.googleapis.com/google.rpc.QuotaFailure",
                "violations": [{"quotaId": quota_id, "quotaValue": "250"}]}] if quota_id else []
    if extra:
        details.append(extra)
    body = {"error": {"code": code, "status": "RESOURCE_EXHAUSTED" if code == 429 else "X",
                      "message": "m", "details": details}}
    return errors.ClientError(code, body) if code < 500 else errors.ServerError(code, body)


def test_gemini_daily_cap_is_a_quota_not_a_retry():
    e = gemini.map_error(api_error(429, "GenerateRequestsPerDayPerProjectPerModel-FreeTier"))
    assert isinstance(e, DailyQuotaError) and e.cap == 250 and "PerDay" in str(e)


def test_gemini_per_minute_limit_is_retried_after_its_delay():
    e = gemini.map_error(api_error(429, "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
                                   {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "17s"}))
    assert isinstance(e, TransientError) and e.retry_after == 17.0


@pytest.mark.parametrize("code, cls", [(503, TransientError), (500, TransientError), (400, BadRequestError)])
def test_gemini_other_errors(code, cls):
    assert isinstance(gemini.map_error(api_error(code)), cls)


def pcm(seconds=0.1, rate=24000):
    return b"\x00\x00" * int(seconds * rate)


def test_raw_pcm_is_wrapped_and_wav_is_kept(tmp_path):
    out = tmp_path / "a.wav"
    gemini.write_wav(pcm(), "audio/L16;codec=pcm;rate=24000", out)
    with wave.open(str(out)) as w:
        assert (w.getframerate(), w.getnchannels(), w.getsampwidth()) == (24000, 1, 2)
    riff = out.read_bytes()
    gemini.write_wav(riff, "audio/wav", tmp_path / "b.wav")
    assert (tmp_path / "b.wav").read_bytes() == riff                 # never wrapped twice


def test_structured_output_is_validated_beyond_what_gemini_enforces():
    schema = {"type": "object", "properties": {"id": {"type": "string", "pattern": "^s[0-9]{2}$"}},
              "required": ["id"]}
    assert gemini.schema_problems({"id": "s04"}, schema) == []
    assert gemini.schema_problems({"id": "shot four"}, schema)


class FakeModels:
    def __init__(self, response):
        self.response, self.calls = response, []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class FakeClient:
    def __init__(self, response):
        self.models = FakeModels(response)


class Obj:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_speech_sends_only_spoken_words_as_text_and_style_as_metadata(tmp_path):
    blob = Obj(data=pcm(), mime_type="audio/L16;rate=24000")
    resp = Obj(candidates=[Obj(content=Obj(parts=[Obj(inline_data=blob)]), finish_reason="STOP")],
               prompt_feedback=None)
    speech = gemini.GeminiSpeech()
    speech._c = FakeClient(resp)
    info = speech.speak(text="ሰላም።", lang="am", voice={"model": "gemini-3.8-flash-tts", "voice": "Kore",
                                                       "style": "warm, unhurried"}, out=tmp_path / "x.wav")
    call = speech._c.models.calls[0]
    part = call["contents"][0].parts[0]
    assert part.text == "ሰላም።" and part.speech_metadata.style == "warm, unhurried"
    assert call["config"].speech_config.voice_config.voice == "Kore"
    assert call["config"].speech_config.language_code is None        # Amharic isn't an allowed code
    assert info["model"] == "gemini-3.8-flash-tts"
    assert wave.open(str(tmp_path / "x.wav")).getnframes() > 0


def test_blocked_text_call_is_a_safety_block():
    resp = Obj(prompt_feedback=Obj(block_reason="SAFETY"), candidates=[], text="")
    text = gemini.GeminiText("gemini-3.8-flash")
    text._c = FakeClient(resp)
    with pytest.raises(SafetyBlockError):
        text.generate_json(prompt="x", schema={"type": "object"})


# ---------- Cloudflare ----------

class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self.headers = {"content-type": "application/json"}
        self.text = json.dumps(payload)
        self._payload = payload
        self.content = self.text.encode()

    def json(self):
        return self._payload


def png_b64(size=(8, 8)):
    buf = io.BytesIO()
    Image.new("RGB", size, (200, 100, 50)).save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def test_klein_is_multipart_with_shrunk_references(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acct")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "token")
    ref = tmp_path / "ref.png"
    Image.new("RGB", (1024, 1024)).save(ref)
    sent = {}

    def fake_post(self, **kwargs):
        sent.update(kwargs)
        return FakeResponse(200, {"success": True, "result": {"image": png_b64()}})

    monkeypatch.setattr(cloudflare.CloudflareImage, "_post", fake_post)
    img = cloudflare.CloudflareImage("@cf/black-forest-labs/flux-2-klein-4b")
    img.generate(prompt="a radio", seed=42, size=(720, 1280), refs=[ref], out=tmp_path / "k.png")
    fields = dict(sent["files"])
    assert fields["prompt"] == (None, "a radio") and fields["seed"] == (None, "42")
    assert fields["width"] == (None, "720") and fields["height"] == (None, "1280")
    name, data, mime = fields["input_image_0"]
    assert max(Image.open(io.BytesIO(data)).size) < 512
    assert Image.open(tmp_path / "k.png").format == "PNG"


@pytest.mark.parametrize("status, payload, cls", [
    (429, {"success": False, "errors": [{"code": 3036, "message": "You have used up your daily free allocation of 10,000 neurons"}]}, DailyQuotaError),
    (429, {"success": False, "errors": [{"code": 3040, "message": "out of capacity"}]}, TransientError),
    (500, {"success": False, "errors": [{"code": 1000, "message": "internal"}]}, TransientError),
    (400, {"success": False, "errors": [{"code": 5006, "message": "bad input"}]}, BadRequestError),
])
def test_cloudflare_errors(status, payload, cls):
    with pytest.raises(cls):
        cloudflare._image_bytes(FakeResponse(status, payload))


# ---------- Addis AI ----------

from pipeline.providers import SpeechRouter, addis  # noqa: E402


class AddisResponse(FakeResponse):
    def __init__(self, status, payload, retry_after=None):
        super().__init__(status, payload)
        if retry_after:
            self.headers["Retry-After"] = retry_after


def wav_bytes(rate=44100):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * (rate // 10))
    return buf.getvalue()


def test_addis_posts_the_documented_body_and_fetches_the_signed_url(tmp_path, monkeypatch):
    import requests

    monkeypatch.setenv("ADDIS_AI_API_KEY", "k")
    sent = {}

    def post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, body=json, headers=headers)
        return AddisResponse(200, {"data": {"audio_url": "https://cdn.example/clip.wav", "duration_seconds": 0.1,
                                            "id": "clip1", "output_format": "wav_44100"},
                                   "usage": {"credits_used": 0.01, "currency": "ETB"}})

    def get(url, timeout=None, **kw):
        assert "headers" not in kw                                     # the key never goes to the signed URL
        r = AddisResponse(200, {})
        r.content = wav_bytes()
        return r

    monkeypatch.setattr(requests, "post", post)
    monkeypatch.setattr(requests, "get", get)
    info = addis.AddisSpeech().speak(text="ሰላም።", lang="am", voice={"model": "addis-voices-2", "voice": "am-dawit"},
                                     out=tmp_path / "a.wav", request_id="hs-1")
    assert sent["url"].endswith("/api/v1/voice/generations") and sent["headers"]["x-api-key"] == "k"
    assert sent["body"] | {} == {"text": "ሰላም።", "voice_id": "am-dawit", "language": "am", "output_format": "wav_44100",
                                 "voice_settings": {"speed": 1.0}, "stream": False, "client_request_id": "hs-1"}
    assert info["provider"] == "addis" and info["cost"]["currency"] == "ETB"
    assert wave.open(str(tmp_path / "a.wav")).getframerate() == 44100


@pytest.mark.parametrize("status, payload, cls", [
    (402, {"status": "error", "error": {"code": "balance_too_low", "message": "top up"}}, DailyQuotaError),
    (429, {"status": "error", "error": {"code": "LANGUAGE_CAPACITY_REACHED"}}, TransientError),
    (409, {"status": "error", "error": {"code": "GENERATION_IN_PROGRESS"}}, TransientError),
    (401, {"status": "error", "error": {"code": "invalid_api_key"}}, BadRequestError),
])
def test_addis_errors(status, payload, cls):
    assert isinstance(addis.classify(status, json.dumps(payload), "3"), cls)


def test_addis_wont_speak_english(tmp_path):
    with pytest.raises(BadRequestError, match="doesn't speak 'en'"):
        addis.AddisSpeech().speak(text="hi", lang="en", voice={"voice": "am-hamen"}, out=tmp_path / "x.wav")


def test_router_sends_addis_voices_to_addis_and_others_to_gemini(tmp_path):
    calls = []

    class Fake:
        def __init__(self, name):
            self.name = name

        def speak(self, **kw):
            calls.append((self.name, kw.get("request_id")))
            return {"provider": self.name}

    router = SpeechRouter(Fake("gemini"), Fake("addis"))
    router.speak(text="x", lang="am", voice={"model": "addis-voices-2", "voice": "am-dawit"}, out=tmp_path / "a")
    router.speak(text="x", lang="am", voice={"model": "addis-voices-2", "voice": "am-dawit"}, out=tmp_path / "a")
    router.speak(text="x", lang="en", voice={"model": "gemini-3.8-flash-tts", "voice": "Kore"}, out=tmp_path / "b")
    assert [c[0] for c in calls] == ["addis", "addis", "gemini"]
    assert calls[0][1] == calls[1][1] and calls[0][1].startswith("hs-")    # same line, same idempotency key


def test_addis_201_with_inline_audio_as_production_answers(tmp_path, monkeypatch):
    """Production answers 201 Created with the WAV inline in data.audio (FAILURES.md F4)."""
    import requests

    monkeypatch.setenv("ADDIS_AI_API_KEY", "k")
    inline = "data:audio/wav;base64," + base64.b64encode(wav_bytes()).decode()
    monkeypatch.setattr(requests, "post", lambda *a, **k: AddisResponse(
        201, {"data": {"id": "c", "voice_id": "am-hamen", "output_format": "wav_44100", "audio": inline}}))
    monkeypatch.setattr(requests, "get", lambda *a, **k: pytest.fail("inline audio needs no download"))
    addis.AddisSpeech().speak(text="ሰላም", lang="am", voice={"model": "addis-voices-2", "voice": "am-hamen"},
                              out=tmp_path / "a.wav")
    assert wave.open(str(tmp_path / "a.wav")).getframerate() == 44100
