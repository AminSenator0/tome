import logging
import os
import warnings
from pathlib import Path

from tome.exceptions import ModelDownloadError

warnings.filterwarnings("ignore", message=".*resume_download.*")
warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*")
warnings.filterwarnings("ignore", message=".*HF_TOKEN.*")
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("transformers").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


def get_default_cache_dir() -> Path:
    if "HF_HOME" in os.environ:
        return Path(os.environ["HF_HOME"])
    if "TRANSFORMERS_CACHE" in os.environ:
        return Path(os.environ["TRANSFORMERS_CACHE"])
    base_dir = Path("models") / ".cache"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir.resolve()


def configure_proxy_environment() -> None:
    cache_dir = get_default_cache_dir()
    os.environ.setdefault("HF_HOME", str(cache_dir))
    os.environ.setdefault("TRANSFORMERS_CACHE", str(cache_dir))
    os.environ.setdefault("HF_HUB_DISABLE_IMPLICIT_TOKEN", "1")

    proxies = {
        "http": os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy"),
        "https": os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"),
        "all": os.environ.get("ALL_PROXY") or os.environ.get("all_proxy"),
    }
    for k, v in proxies.items():
        if v:
            os.environ[k.upper() + "_PROXY"] = v
            os.environ[k.lower() + "_proxy"] = v


def ensure_gliner_model(
    model_identifier: str,
    mirror_url: str = "https://hf-mirror.com",
    project_models_dir: Path = Path("models"),
):
    configure_proxy_environment()

    explicit_path = Path(model_identifier)
    if explicit_path.exists() and explicit_path.is_dir():
        from gliner import GLiNER

        logger.info("Loading GLiNER model from explicit path: %s", explicit_path)
        return GLiNER.from_pretrained(str(explicit_path), local_files_only=True)

    slug = model_identifier.split("/")[-1]
    
    # Candidate local directories to check before making any network request
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    candidate_paths: list[Path] = [
        project_models_dir / slug,
        project_models_dir / model_identifier,
        repo_root / "models" / slug,
        repo_root / "models" / model_identifier,
        Path.cwd() / "models" / slug,
        Path.cwd() / "models" / model_identifier,
    ]

    for candidate in candidate_paths:
        if candidate.exists() and candidate.is_dir():
            has_weights = (
                (candidate / "model.safetensors").is_file()
                or (candidate / "pytorch_model.bin").is_file()
                or (candidate / "config.json").is_file()
            )
            if has_weights:
                from gliner import GLiNER

                logger.info("Found local GLiNER model at %s (skipping download)", candidate)
                try:
                    return GLiNER.from_pretrained(str(candidate), local_files_only=True)
                except Exception as local_load_err:
                    logger.warning(
                        "Failed loading with local_files_only from %s: %s. Retrying without flag.",
                        candidate,
                        local_load_err,
                    )
                    try:
                        return GLiNER.from_pretrained(str(candidate))
                    except Exception:
                        pass

    from gliner import GLiNER

    try:
        model = GLiNER.from_pretrained(model_identifier, local_files_only=True)
        return model
    except Exception as exc:
        logger.debug("Local offline model lookup skipped: %s", exc)

    try:
        model = GLiNER.from_pretrained(model_identifier)
        try:
            candidate_local.mkdir(parents=True, exist_ok=True)
            model.save_pretrained(str(candidate_local))
        except Exception as exc:
            logger.debug("Failed caching model locally: %s", exc)
        return model
    except Exception:
        original_endpoint = os.environ.get("HF_ENDPOINT")
        try:
            os.environ["HF_ENDPOINT"] = mirror_url
            model = GLiNER.from_pretrained(model_identifier)
            try:
                candidate_local.mkdir(parents=True, exist_ok=True)
                model.save_pretrained(str(candidate_local))
            except Exception as exc:
                logger.debug("Failed caching model locally: %s", exc)
            return model
        except Exception as fallback_err:
            raise ModelDownloadError(
                f"Failed to load GLiNER model '{model_identifier}'. Error: {fallback_err}. "
                f"For offline use, place model in models/{slug} or pass -m /path/to/model."
            ) from fallback_err
        finally:
            if original_endpoint is not None:
                os.environ["HF_ENDPOINT"] = original_endpoint
            else:
                os.environ.pop("HF_ENDPOINT", None)
