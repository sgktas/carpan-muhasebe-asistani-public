from pathlib import Path

from app.writers.netsis_writer import NetsisWriter


def test_requirements_installs_pywin32_only_on_windows():
    requirements = (Path(__file__).resolve().parents[1] / "requirements.txt").read_text(
        encoding="utf-8"
    )
    assert 'pywin32; sys_platform == "win32"' in requirements


def test_powershell_fallback_uses_local_number_formats_and_oa_dates():
    script = NetsisWriter._powershell_script()
    assert 'NumberFormatLocal = "gg.aa.yyyy"' in script
    assert 'NumberFormatLocal = "#.##0,00"' in script
    assert ").ToOADate()" in script
    # Biçimlendirme hatası tüm aktarımı durdurmamalı; artık sütun aralığı
    # profildeki string_columns listesinden dinamik hesaplanıyor (sabit "F"
    # değil), ama aynı "hata yutulur, devam eder" davranışı korunuyor.
    assert 'NumberFormat = "@"' in script
    assert "function ExcelColumnLetter" in script
    assert "$stringColumns" in script


def test_python_com_path_uses_local_formats_and_value2_serials():
    source = (Path(__file__).resolve().parents[1] / "app" / "writers" / "netsis_writer.py").read_text(encoding="utf-8")
    assert 'NumberFormatLocal = "gg.aa.yyyy"' in source
    assert 'NumberFormatLocal = "#.##0,00"' in source
    assert 'Value2 = tuple(' in source
    assert '_record_values_for_excel_value2' in source
