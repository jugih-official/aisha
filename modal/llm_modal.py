"""
GPU backend for `ai-code`: an open-weights LLM on a Modal GPU, exposed as an
OpenAI-compatible server. `ai-code` talks to it over plain HTTP.

Deploy:   modal deploy llm_modal.py          (install.sh does this for you)
Dev/test: modal serve llm_modal.py           (ephemeral, auto-reloads)

Once deployed, vLLM serves an OpenAI-compatible API at:
    https://<workspace>--ai-code-llm-serve.modal.run/v1

Switch GPU/model without editing the file via env vars at deploy time:
    LLM_GPU=A10 LLM_MODEL_NAME=Qwen/Qwen2.5-7B-Instruct modal deploy llm_modal.py
    LLM_GPU=A100-80GB:2 modal deploy llm_modal.py        # 2 GPUs, tensor-parallel

Rough GPU sizing (bf16 needs ~2GB/1B params, plus KV-cache headroom):
    7-8B   -> A10 (24GB) or L4
    14B    -> L40S / A100-40GB
    32B    -> L40S with an AWQ/GPTQ 4-bit checkpoint (the default), or A100-80GB
    70B    -> A100-80GB / H100 (often quantized, or :2 for two GPUs)
"""

import os

import modal

# --- Configuration -----------------------------------------------------------

# Default is the strongest model that fits an L40S (48GB): Qwen2.5-32B
# AWQ-quantized (4-bit). Weights are ~19GB, leaving ample room for the KV
# cache, and it beats a 14B run at full precision. Any vLLM-supported HF model
# works; for gated models (e.g. Llama) add a secret with HF_TOKEN.
MODEL_NAME = os.environ.get("LLM_MODEL_NAME", "Qwen/Qwen2.5-32B-Instruct-AWQ")

# Modal GPU identifier. Valid: T4, L4, A10, L40S, A100-40GB, A100-80GB,
# RTX-PRO-6000, H100, H200, B200. Append ":n" for n GPUs (tensor parallelism).
GPU = os.environ.get("LLM_GPU", "L40S")

# Cap the context window so the KV cache fits alongside the weights.
MAX_MODEL_LEN = int(os.environ.get("LLM_MAX_MODEL_LEN", "16384"))

VLLM_PORT = 8000
# How long the GPU container stays warm after the last request before it scales
# to zero (and stops costing money). The next request then pays a cold start.
SCALEDOWN_WINDOW = 2 * 60  # seconds
# Concurrent requests one GPU container handles before Modal adds a replica.
MAX_CONCURRENT = 32

# --- Image -------------------------------------------------------------------

vllm_image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "vllm==0.21.0",
        "huggingface_hub[hf_transfer]",
    )
    # hf_transfer speeds up the (one-time) model download. Disable the
    # FlashInfer sampler: it JIT-compiles a CUDA kernel at runtime and needs
    # nvcc, which isn't in the slim image — the native sampler works fine.
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "VLLM_USE_FLASHINFER_SAMPLER": "0",
        }
    )
)

app = modal.App("ai-code-llm")

# Persist downloaded weights and vLLM's compile cache across cold starts so
# only the very first run pays the full download cost.
hf_cache = modal.Volume.from_name("ai-code-hf-cache", create_if_missing=True)
vllm_cache = modal.Volume.from_name("ai-code-vllm-cache", create_if_missing=True)

# Modal web endpoints are public, so the server is gated with a bearer token.
# install.sh creates this secret (key VLLM_API_KEY) and stores the same token
# locally so ai-code can authenticate.
api_key_secret = modal.Secret.from_name("ai-code-llm-key")


@app.function(
    image=vllm_image,
    gpu=GPU,
    volumes={
        "/root/.cache/huggingface": hf_cache,
        "/root/.cache/vllm": vllm_cache,
    },
    secrets=[api_key_secret],
    scaledown_window=SCALEDOWN_WINDOW,
    timeout=10 * 60,
)
@modal.concurrent(max_inputs=MAX_CONCURRENT)
@modal.web_server(port=VLLM_PORT, startup_timeout=10 * 60)
def serve():
    import subprocess

    # If GPU is like "A100-80GB:2", run vLLM with matching tensor parallelism.
    tensor_parallel = int(GPU.split(":")[1]) if ":" in GPU else 1

    cmd = [
        "vllm",
        "serve",
        MODEL_NAME,
        "--host",
        "0.0.0.0",
        "--port",
        str(VLLM_PORT),
        "--api-key",
        os.environ["VLLM_API_KEY"],
        "--max-model-len",
        str(MAX_MODEL_LEN),
        "--tensor-parallel-size",
        str(tensor_parallel),
        # Names clients can use in the "model" field of requests:
        "--served-model-name",
        MODEL_NAME,
        "default",
    ]
    # vLLM auto-detects quantization, but be explicit for AWQ/GPTQ checkpoints
    # so it uses the fast Marlin kernels on Ada GPUs like the L40S.
    lower = MODEL_NAME.lower()
    if "awq" in lower:
        cmd += ["--quantization", "awq_marlin"]
    elif "gptq" in lower:
        cmd += ["--quantization", "gptq_marlin"]

    print("Launching:", " ".join(cmd))
    subprocess.Popen(cmd)
