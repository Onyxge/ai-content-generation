"""One ACE-Step 1.5 job, run inside ACE-Step's own environment by runner_acestep.py.

    python runner_acestep_job.py <ace-step dir> <job.json> <out.wav>

Prints one JSON line at the end: the sample rate and the length actually produced."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path


def keyscale(key: str | None) -> str:
    """'D minor' → 'D Minor', the form ACE-Step's examples use. No key means "" (ACE-Step picks
    one): ACE-Step calls .strip() on it, so None crashed run 3 (FAILURES.md F9)."""
    if not key:
        return ""
    parts = key.split()
    return " ".join([parts[0]] + [p.capitalize() for p in parts[1:]])


def main() -> int:
    ace_dir, spec, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    job = json.loads(spec.read_text(encoding="utf-8"))
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    dit = AceStepHandler()
    dit.initialize_service(project_root=str(ace_dir), config_path="acestep-v15-turbo", device="cuda")
    llm = LLMHandler()                                   # never initialised: DiT only
    params = GenerationParams(task_type="text2music", caption=job["caption"],
                              lyrics="[Instrumental]" if job.get("instrumental", True) else "",
                              instrumental=bool(job.get("instrumental", True)), duration=float(job["length_s"]),
                              bpm=job.get("bpm"), keyscale=keyscale(job.get("key_signature")), timesignature="4",
                              inference_steps=int(job["steps"]), shift=3.0, seed=int(job["seed"]), thinking=False)
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(job["seed"])], audio_format="wav")
    with tempfile.TemporaryDirectory() as tmp:
        result = generate_music(dit, llm, params, config, save_dir=tmp)
        if not result.success:
            raise SystemExit(f"generation failed: {getattr(result, 'error', result)}")
        audio = result.audios[0]
        shutil.copy(audio["path"], out)
    print(json.dumps({"sample_rate": audio.get("sample_rate"), "duration_s": job["length_s"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
