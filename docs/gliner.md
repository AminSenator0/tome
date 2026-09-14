# GLiNER Models Setup & Local Caching Guide

Tome utilizes **GLiNER** (Generalist and Lightweight Model for Named Entity Recognition) for local, zero-shot entity extraction across customizable literary taxonomies without requiring external API calls.

---

## 1. Supported Models

Tome supports standard GLiNER models available on Hugging Face:

| Model Identifier | Parameter Count | VRAM / RAM | Recommended Usage |
|---|---|---|---|
| **`urchade/gliner_medium-v2.1`** (Default) | ~160M | ~1.2 GB | Optimal balance of accuracy, boundary detection, and CPU speed. |
| **`urchade/gliner_small-v2.1`** | ~80M | ~600 MB | Low-resource VPS instances or rapid draft screening. |
| **`urchade/gliner_large-v2.1`** | ~340M | ~2.5 GB | Maximum entity recall on complex historical or foreign texts. |
| **`urchade/gliner_multi-v2.1`** | ~200M | ~1.5 GB | Multi-lingual zero-shot entity recognition. |

---

## 2. Pre-Downloading & Local Caching

By default, when you first run `tome run` or `tome extract`, the model weights are downloaded from Hugging Face and cached locally.

To pre-download a model in advance (e.g. during server provisioning or Docker build):

```bash
tome setup-model -m urchade/gliner_medium-v2.1
```

Weights are stored in your user cache directory:
- Linux: `~/.cache/huggingface/hub/models--urchade--gliner_medium-v2.1`
- macOS: `~/Library/Caches/huggingface/hub/`
- Windows: `%USERPROFILE%\.cache\huggingface\hub\`

---

## 3. Running in Air-Gapped & Offline Environments

If deploying Tome on an internal network or air-gapped server without internet access:

1. Download the model repository on an internet-connected machine:
   ```bash
   git clone https://huggingface.co/urchade/gliner_medium-v2.1 /path/to/local/gliner_medium
   ```
2. Transfer the directory to the target server.
3. Configure Tome to load the local path directly in `tome.json`:
   ```json
   {
     "default_model": "/path/to/local/gliner_medium"
   }
   ```
   Or pass via the CLI:
   ```bash
   tome extract output/Book/chapters -m /path/to/local/gliner_medium
   ```
4. Set Hugging Face offline environment variables to prevent network probes:
   ```bash
   export HF_HUB_OFFLINE=1
   export TRANSFORMERS_OFFLINE=1
   ```

---

## 4. Hardware Optimization & Memory Management

- **CPU Inference**: Tome runs GLiNER efficiently on standard multi-core CPUs using ONNX/PyTorch optimizations.
- **Batch Sizing (`-b, --batch-size`)**:
  - Default: `16` (suitable for 4 GB to 8 GB RAM machines).
  - High-Memory Machines: Increase to `32` or `64` for faster throughput.
  - Low-Spec VPS (1 GB - 2 GB RAM): Set to `4` or `8` and enable `--fast` mode to filter dialogue blocks and minimize memory footprint.
- **Sliding Window Chunking**: Tome divides manuscript chapters into overlapping word windows (`chunk_size_words=280`, `chunk_overlap_words=20`) to prevent out-of-memory errors on long chapters while maintaining cross-boundary entity integrity.

---

## 5. Skipping GLiNER (`-n, --no-gliner`)

If you prefer not to load local PyTorch weights or are operating on a minimal memory host, you can disable local entity extraction entirely:

```bash
tome run book.pdf -n
# or
tome translate output/Book/chapters -n
```

When GLiNER is disabled, Tome automatically switches to LLM inline extraction, discovering entities directly during the translation pass.
