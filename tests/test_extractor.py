from unittest.mock import MagicMock, patch

from tome.core.extractor import chunk_text, extract_entities


def test_chunk_text():
    words = "Word " * 1000
    chunks = chunk_text(words, chunk_size=300, overlap=50)
    assert len(chunks) >= 3


def test_extract_entities_mocked():
    mock_model = MagicMock()
    mock_model.batch_predict_entities.return_value = [[{"text": "Xaden Riorson", "label": "character", "score": 0.95}]]
    with patch("tome.core.extractor.ensure_gliner_model", return_value=mock_model):
        results = extract_entities(
            text="Sample sentence with Xaden Riorson.",
            model_identifier="dummy-model",
            taxonomy={"People & Characters": ["character"]},
            batch_size=2,
        )
        assert len(results) == 1
        assert results[0]["text"] == "Xaden Riorson"
        assert results[0]["category"] == "People & Characters"


def test_chunk_text_edge_cases():
    assert chunk_text("", chunk_size=300, overlap=50) == []

    short = "Only three words"
    chunks = chunk_text(short, chunk_size=300, overlap=50)
    assert len(chunks) == 1
    assert chunks[0] == short


def test_extract_entities_empty_and_threshold_filtering():
    assert extract_entities("", model_identifier="dummy", taxonomy={}) == []

    mock_model = MagicMock()
    mock_model.batch_predict_entities.return_value = [
        [
            {"text": "High Confidence", "label": "character", "score": 0.9},
            {"text": "Low Confidence", "label": "character", "score": 0.3},
        ]
    ]
    with patch("tome.core.extractor.ensure_gliner_model", return_value=mock_model):
        results = extract_entities(
            text="High Confidence and Low Confidence were walking.",
            model_identifier="dummy-model",
            taxonomy={"People": ["character"]},
            batch_size=1,
            threshold=0.6,
        )
        assert len(results) == 1
        assert results[0]["text"] == "High Confidence"


def test_get_inference_device(monkeypatch):
    import torch

    from tome.core.extractor import get_inference_device

    # Force CPU
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    if hasattr(torch.backends, "mps"):
        monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)
    dev = get_inference_device()
    assert dev.type == "cpu"

    # Simulate MPS available
    if hasattr(torch.backends, "mps"):
        monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)
        monkeypatch.setattr(torch, "zeros", lambda *args, **kwargs: None)
        dev = get_inference_device()
        assert dev.type == "mps"
