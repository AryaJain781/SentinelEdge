"""Phase 0 smoke tests: confirm the scaffolding and pinned environment work."""

import importlib

import joblib
import numpy
import pandas
import pytest
import sklearn

import src

PACKAGES = [
    "src.detectors",
    "src.explainer",
    "src.pipeline",
    "src.ui",
    "src.utils",
]


def test_package_version_is_set() -> None:
    assert src.__version__ == "0.1.0"


@pytest.mark.parametrize("module_name", PACKAGES)
def test_subpackage_imports(module_name: str) -> None:
    assert importlib.import_module(module_name) is not None


def test_pinned_ml_versions_match_requirements() -> None:
    assert sklearn.__version__ == "1.4.2"
    assert numpy.__version__ == "1.26.4"
    assert pandas.__version__ == "2.2.2"
    assert joblib.__version__ == "1.3.2"


def test_numpy_basic_math_works() -> None:
    assert int(numpy.array([1, 2, 3]).sum()) == 6
