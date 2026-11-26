"""Wan 2.2 TI2V-5B image-to-video, the GPU runner's `i2v` backend, written for a Kaggle T4.

Checked 2026-11-26 (docs/build-log.md, Entry 12):
- Diffusers' WanImageToVideoPipeline, not the official repo: the repo's attention asserts on
  FlashAttention 2, which Turing GPUs don't have, and its size check rejects 480p. Diffusers
  uses PyTorch SDPA and takes any size that is a multiple of 32.
- fp16 for the transformer, because a T4 emulates bf16 (about 11x slower than fp16), with the
  VAE in fp32 as the diffusers docs recommend. On a bf16-capable GPU (Ampere or newer) we use bf16.
- Group offloading, not model CPU offload. The first Kaggle run (FAILURES.md F7) showed why.
  Model offload moves whole components and only evicts one when the next in its fixed order
  starts. So the 11 GB umT5 text encoder was still on the GPU when the VAE came on to encode the
  first frame: 14.28 of 14.56 GB used, out of memory before a single step. Group offloading
  keeps each model's weights in CPU memory and streams a few blocks at a time onto the GPU.
  The transformer's transfers overlap with compute on a CUDA stream. Tiled VAE decode for long clips.
- The download is about 34 GB, so point HF_HOME at scratch space, not /kaggle/working, or set
  WAN_MODEL to a local copy. Set PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True (the notebook
  does) to avoid fragmentation.
- The negative prompt is Wan's own default (wan/configs/shared_config.py), in Chinese as shipped.

Everything that changes the clip (prompt, seed, size, frames, fps, steps) comes from the job,
and so is part of its cache key. Nothing here is set from the environment except where the
weights are."""
from __future__ import annotations

import os
from pathlib import Path

MODEL = os.environ.get("WAN_MODEL", "Wan-AI/Wan2.2-TI2V-5B-Diffusers")
GUIDANCE = 5.0
NEGATIVE = ("色调艳丽，过曝，静态，细节模糊不清，字幕，风格，作品，画作，画面，静止，整体发灰，最差质量，低质量，JPEG压缩残留，"
            "丑陋的，残缺的，多余的手指，画得不好的手部，画得不好的脸部，畸形的，毁容的，形态畸形的肢体，手指融合，"
            "静止不动的画面，杂乱的背景，三条腿，背景人很多，倒着走")


def fit(image, width: int, height: int):
    """Scale to cover, then centre-crop: the keyframe's subject is composed in the middle."""
    from PIL import Image

    scale = max(width / image.width, height / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left, top = (resized.width - width) // 2, (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


class Wan:
    """The memory plan, from two failed Kaggle runs (FAILURES.md F7, F8):

    1. Load the pipeline on the CPU, about 24 GB of the T4 box's 29 GB of host RAM.
    2. Encode every job's prompt once, with the 11 GB text encoder alone on the GPU. Then
       drop it from GPU and host memory: the prompts are all it was needed for.
    3. Keep the fp32 VAE resident on the GPU (2.8 GB), and stream the transformer from pinned
       host memory one block at a time (group offloading on a CUDA stream).
    4. Pin the pipeline's execution device to that GPU, since its weights now live on the CPU."""

    name = "wan"

    def __init__(self, gpu: int, jobs: list[dict]):
        import gc

        import torch
        from diffusers import AutoencoderKLWan, WanImageToVideoPipeline

        if not torch.cuda.is_available():
            raise RuntimeError("no CUDA GPU: Wan needs one (on Kaggle, Settings → Accelerator → GPU T4 x2)")
        self.torch, self.device = torch, torch.device(f"cuda:{gpu}")
        major, minor = torch.cuda.get_device_capability(gpu)
        self.dtype = torch.bfloat16 if major >= 8 else torch.float16
        self.precision = f"{'bf16' if major >= 8 else 'fp16'} transformer, fp32 VAE (sm_{major}{minor})"
        vae = AutoencoderKLWan.from_pretrained(MODEL, subfolder="vae", torch_dtype=torch.float32)
        pipe = WanImageToVideoPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=self.dtype)

        # 2. every prompt, once; then the text encoder goes
        pipe.text_encoder.to(self.device)
        self.embeds = {}
        with torch.no_grad():
            for job in jobs:
                pos, neg = pipe.encode_prompt(prompt=job["prompt"], negative_prompt=NEGATIVE,
                                              do_classifier_free_guidance=True, device=self.device)
                self.embeds[job["prompt"]] = (pos.to("cpu"), neg.to("cpu"))
        pipe.text_encoder.to("cpu")
        try:
            pipe.register_modules(text_encoder=None)
        except Exception:                            # noqa: BLE001 - older diffusers: plain attribute
            pipe.text_encoder = None
        gc.collect()
        torch.cuda.empty_cache()

        # 3. VAE resident, transformer streamed
        pipe.vae.to(self.device)
        pipe.vae.enable_tiling()
        self.offload = self._stream_transformer(pipe)

        # 4. inputs on the GPU even though the transformer's weights live on the CPU
        device = self.device
        pipe.__class__ = type("WanOnGpu", (pipe.__class__,), {"_execution_device": property(lambda _s: device)})
        self.pipe = pipe

    def _stream_transformer(self, pipe) -> str:
        cpu = self.torch.device("cpu")
        for kwargs in ({"use_stream": True, "low_cpu_mem_usage": True}, {"use_stream": True}, {"use_stream": False}):
            try:
                pipe.transformer.enable_group_offload(onload_device=self.device, offload_device=cpu,
                                                      offload_type="block_level", num_blocks_per_group=1, **kwargs)
                return f"group offload, transformer 1 block at a time ({', '.join(f'{k}={v}' for k, v in kwargs.items())})"
            except TypeError:                        # an older diffusers without that keyword
                continue
        raise RuntimeError("this diffusers has no group offloading; Wan won't fit a 15 GB GPU without it")

    def run(self, job: dict, root: Path, out: Path) -> dict:
        from diffusers.utils import export_to_video
        from PIL import Image

        width, height = job["size"]
        if width % 32 or height % 32:
            raise ValueError(f"size {width}x{height}: Wan 2.2 5B needs multiples of 32")
        if (job["frames"] - 1) % 4:
            raise ValueError(f"{job['frames']} frames: Wan needs 4n+1")
        pos, neg = self.embeds[job["prompt"]]
        image = fit(Image.open(root / job["image"]).convert("RGB"), width, height)
        with self.torch.no_grad():
            result = self.pipe(image=image, prompt_embeds=pos.to(self.device), negative_prompt_embeds=neg.to(self.device),
                               height=height, width=width, num_frames=job["frames"], guidance_scale=GUIDANCE,
                               num_inference_steps=job["steps"],
                               generator=self.torch.Generator("cpu").manual_seed(int(job["seed"])))
        export_to_video(result.frames[0], str(out), fps=job["fps"])
        return {"model": f"Wan2.2-TI2V-5B (diffusers, {MODEL.rsplit('/', 1)[-1]})", "steps": job["steps"],
                "size": [width, height], "frames": job["frames"], "guidance": GUIDANCE, "offload": self.offload}
