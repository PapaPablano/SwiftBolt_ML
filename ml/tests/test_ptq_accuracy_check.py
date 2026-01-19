import numpy as np

from src.scripts.ptq_accuracy_check import load_calibration, quantize_inputs


def test_quantize_inputs_roundtrip_shape():
    X = np.array([[1.0, -2.0], [3.0, 4.0]], dtype=np.float32)
    min_vals = X.min(axis=0)
    max_vals = X.max(axis=0)
    quantized = quantize_inputs(X, min_vals, max_vals)
    assert quantized.shape == X.shape


def test_load_calibration_fallback(tmp_path):
    X = np.array([[1.0, -2.0], [3.0, 4.0]], dtype=np.float32)
    min_vals, max_vals = load_calibration(tmp_path / "missing.npz", X)
    assert np.allclose(min_vals, X.min(axis=0))
    assert np.allclose(max_vals, X.max(axis=0))
