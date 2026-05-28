import pytest
from pathlib import Path


# -----------------------------
# XML Dataset Loader Utility
# -----------------------------
class XMLDatasetLoader:
    """Loads XML test data from /tests/data folder."""

    DATA_DIR = Path(__file__).parent / "data"

    @staticmethod
    def load(filename: str) -> str:
        file_path = XMLDatasetLoader.DATA_DIR / filename
        return file_path.read_text(encoding="utf-8").strip()


# -----------------------------
# Pytest Fixture
# -----------------------------
@pytest.fixture
def xml_loader():
    return XMLDatasetLoader