from pathlib import Path

from app.core.manim_input_classifier import ManimInputClassifier


def test_classify_uses_manim_headers_and_report_file_names(monkeypatch, tmp_path):
    files = [
        tmp_path / "bolge.xlsx",
        tmp_path / "03_TAHSILAT_RAPORU.xlsx",
        tmp_path / "01_MUSTERI_LISTESI.xlsx",
    ]
    headers = {
        "bolge.xlsx": ["Banka", "Dekont Durumu"],
        "03_TAHSILAT_RAPORU.xlsx": ["Müşteri Kodu", "Tutar"],
        "01_MUSTERI_LISTESI.xlsx": ["Cari Kodu", "Ünvan"],
    }
    classifier = ManimInputClassifier()
    monkeypatch.setattr(classifier, "_headers", lambda path: headers[path.name])

    result = classifier.classify([Path(path) for path in files])

    assert result.manim_files == [files[0]]
    assert result.tahsilat_file == files[1]
    assert result.customer_file == files[2]


def test_classify_preserves_multiple_manim_files(monkeypatch, tmp_path):
    files = [tmp_path / "AYDIN MANIM.xlsx", tmp_path / "ANTALYA MANIM.xlsx"]
    classifier = ManimInputClassifier()
    monkeypatch.setattr(classifier, "_headers", lambda _path: [])

    result = classifier.classify(files)

    assert result.manim_files == files
