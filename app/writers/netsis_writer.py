from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Iterable

import xlwt

from app.core.output_profile import OutputProfile, OutputProfileStore
from app.core.output_contract import validate_netsis_output
from app.models.records import NetsisRecord
from app.writers.xls_utils import ensure_writable, make_styles, save_xls, write_cell, xls_path


class ExcelAutomationUnavailable(RuntimeError):
    """Python tarafındaki Excel COM köprüsü kullanılamadığında yükseltilir."""


def _default_profile() -> OutputProfile:
    config_dir = Path(__file__).resolve().parents[2] / "config"
    return OutputProfileStore(config_dir).get("netsis")


def _default_template_path(profile: OutputProfile) -> Path:
    # PyInstaller uygulamasında kaynak dosyaların konumu yerine `_MEIPASS`
    # altındaki paket klasörü kullanılmalıdır. Aksi durumda şablon bulunamaz
    # ve Netsis'in kabul etmediği genel xlwt çıktısına düşülebiliyordu.
    configured_path = Path(profile.template_file)
    if configured_path.is_absolute():
        return configured_path

    roots: list[Path] = []
    if getattr(sys, "frozen", False):
        bundled_root = getattr(sys, "_MEIPASS", None)
        if bundled_root:
            roots.append(Path(bundled_root))
    roots.append(Path(__file__).resolve().parents[2])

    local_enabled = os.environ.get("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG") != "1"
    for project_root in roots:
        local_template = project_root / "templates" / "local" / profile.template_file
        if local_enabled and local_template.is_file():
            return local_template
        packaged_template = project_root / "templates" / profile.template_file
        if packaged_template.is_file():
            return packaged_template

    # Hata mesajında doğru beklenen konumu göstermek için mevcut davranışın
    # yolunu döndür; Windows paketinde bu durum ayrıca açıkça ele alınır.
    return roots[0] / "templates" / profile.template_file


class NetsisWriter:
    """Muhasebe programına (varsayılan: Netsis) aktarım kaydını Excel 97-2003
    biçiminde yazar.

    Sütun başlıkları, sırası ve her sütuna hangi verinin gideceği artık kodda
    sabit değil; ``config/output_profiles/`` altındaki bir ``OutputProfile``
    tarafından tanımlanıyor. Varsayılan profil ("netsis"), önceki sabit kodlu
    davranışla birebir aynı 27 sütunu üretir. Başka bir muhasebe programı için
    yeni bir profil dosyası (+ o programın şablon Excel dosyası) eklemek,
    Python kodunu değiştirmeden yeterlidir.

    Windows üretim ortamında öncelik ``pywin32`` üzerinden Microsoft Excel
    COM motorudur. ``pywin32`` kurulu değilse uygulama artık işlemi durdurmaz;
    Windows'un yerleşik PowerShell COM köprüsüne otomatik geçer. Her iki yol da
    doğrulanmış şablonu Microsoft Excel'e açtırıp ``xlExcel8`` (FileFormat=56)
    olarak kaydeder.

    Linux/macOS test ortamlarında gerçek BIFF8 çıktısı için ``xlwt`` yedeği
    kullanılır.
    """

    XL_EXCEL_8 = 56
    # Geriye dönük uyumluluk: eski kod/testler `NetsisWriter.HEADERS`'a sınıf
    # düzeyinde erişiyordu. Varsayılan ("netsis") profilin başlıklarını temsil
    # eder; farklı bir profille çalışan bir örnek `self.profile.headers()`
    # kullanır (yazma mantığının kendisi zaten bunu yapıyor).
    HEADERS = _default_profile().headers()

    def __init__(self, template_path: str | Path | None = None, profile: OutputProfile | None = None):
        self.profile = profile or _default_profile()
        self.template_path = Path(template_path) if template_path else _default_template_path(self.profile)
        self._excel = None
        self._pythoncom = None

    def write(self, records: list[NetsisRecord], output_path: str | Path) -> Path:
        records = sorted(records, key=self._sort_key)
        if (
            os.name == "nt"
            and os.environ.get("MUHASEBE_ASISTANI_DISABLE_LOCAL_CONFIG") != "1"
            and not self.template_path.is_file()
        ):
            raise FileNotFoundError(
                f"'{self.profile.name}' için paket içi Netsis şablonu bulunamadı: "
                f"{self.template_path}. Genel Excel çıktısı üretilmedi."
            )
        if os.name == "nt" and self.template_path.is_file():
            try:
                written_path = self._write_with_microsoft_excel(records, output_path)
            except ExcelAutomationUnavailable:
                # pywin32 yoksa veya Python COM köprüsü başlatılamıyorsa,
                # Windows'un yerleşik PowerShell COM yoluna otomatik geç.
                written_path = self._write_with_powershell_excel(records, output_path)
        else:
            # Public kaynak paketi gerçek şirket şablonu içermez. Yerel şablon
            # bulunmadığında aynı 27 sütunlu BIFF8 dosyası güvenli biçimde koddan
            # üretilir.
            written_path = self._write_with_xlwt(records, output_path)

        validate_netsis_output(
            written_path,
            self.profile,
            records,
            self.template_path if self.template_path.is_file() else None,
        )
        return written_path

    def close(self) -> None:
        if self._excel is not None:
            try:
                self._excel.Quit()
            except Exception:
                pass
            self._excel = None
        if self._pythoncom is not None:
            try:
                self._pythoncom.CoUninitialize()
            except Exception:
                pass
            self._pythoncom = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    @staticmethod
    def _sort_key(record: NetsisRecord):
        value = record.islem_tarihi
        if isinstance(value, datetime):
            return value
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        return datetime.max

    def _validate_template(self) -> Path:
        if not self.template_path or not self.template_path.is_file():
            raise FileNotFoundError(
                f"'{self.profile.name}' şablonu bulunamadı. Beklenen dosya: "
                f"{self.template_path or self.profile.template_file}"
            )
        return self.template_path.resolve()

    def _prepare_output_path(self, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        if self.profile.output_extension == ".xls":
            output_path = xls_path(output_path)
        else:
            output_path = output_path.with_suffix(self.profile.output_extension)
        output_path = output_path.resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            output_path.unlink()
        return output_path

    @staticmethod
    def _contiguous_ranges(indexes: list[int]) -> list[tuple[int, int]]:
        """Ardışık sütun indekslerini (başlangıç, bitiş) aralıklarına birleştirir."""
        if not indexes:
            return []
        ordered = sorted(indexes)
        ranges: list[tuple[int, int]] = []
        start = prev = ordered[0]
        for index in ordered[1:]:
            if index == prev + 1:
                prev = index
                continue
            ranges.append((start, prev))
            start = prev = index
        ranges.append((start, prev))
        return ranges

    @staticmethod
    def _excel_column_letter(index0based: int) -> str:
        """0 tabanlı sütun indeksini Excel harfine çevirir (0->A, 26->AA, ...)."""
        index = index0based + 1
        letters = ""
        while index > 0:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        return letters

    def _force_text_column_indexes(self) -> list[int]:
        """Metin biçimi uygulanacak sütunları döndürür.

        Onaylı toplu Netsis şablonunda ``Banka Hes.Kodu(*)`` hücreleri
        metin (``@``) değil, şablonun kendi ``0.00`` biçimindedir. Bu
        sütuna profil ayarından yanlışlıkla ``force_text`` verilse bile
        şablon biçimini bozma; Netsis metin biçimli BM kodlarını geçersiz
        banka kodu olarak işaretleyebiliyor.
        """
        indexes = self.profile.column_index(force_text=True)
        if self.profile.profile_id != "netsis_toplu":
            return indexes
        return [
            index
            for index in indexes
            if self.profile.columns[index].field != "banka_hesap_kodu"
        ]

    def _write_with_microsoft_excel(
        self,
        records: list[NetsisRecord],
        output_path: str | Path,
    ) -> Path:
        source_template = self._validate_template()
        # Excel bazı eski BIFF8 dosyalarını SaveCopyAs/Close(false) akışında
        # dahi bileşik dosya düzeyinde değiştirebiliyor. Onaylı kaynak şablonu
        # Excel'e hiç açtırma; bütün işlemleri geçici birebir kopyada yap.
        with tempfile.TemporaryDirectory(prefix="carpan_netsis_template_") as temp_dir:
            working_template = Path(temp_dir) / source_template.name
            shutil.copy2(source_template, working_template)
            return self._write_with_microsoft_excel_working_copy(
                records, output_path, working_template
            )

    def _write_with_microsoft_excel_working_copy(
        self,
        records: list[NetsisRecord],
        output_path: str | Path,
        template_path: Path,
    ) -> Path:
        output_path = self._prepare_output_path(output_path)
        headers = self.profile.headers()
        last_column_letter = self._excel_column_letter(len(headers) - 1)

        excel = self._get_excel_application()
        workbook = None
        worksheet = None
        try:
            workbook = excel.Workbooks.Open(
                str(template_path),
                UpdateLinks=0,
                ReadOnly=False,
                IgnoreReadOnlyRecommended=True,
            )
            workbook.CheckCompatibility = False
            worksheet = workbook.Worksheets(1)

            actual_headers = list(worksheet.Range(f"A1:{last_column_letter}1").Value[0])
            actual_headers = ["" if value is None else str(value) for value in actual_headers]
            if actual_headers != headers:
                raise ValueError(
                    f"Paket içindeki '{self.profile.name}' şablon başlıkları "
                    f"beklenen {len(headers)} sütunla uyuşmuyor."
                )

            used_rows = int(worksheet.UsedRange.Rows.Count)
            clear_last_row = max(used_rows, len(records) + 1, 15)
            worksheet.Range(f"A2:{last_column_letter}{clear_last_row}").ClearContents()

            if records:
                last_row = len(records) + 1
                if len(records) > 1:
                    # Orijinal örnek satırın yazı, kenarlık ve sayı biçimini
                    # yeni satırlara da taşı; yalnız biçimleri kopyala.
                    worksheet.Range(f"A2:{last_column_letter}2").Copy()
                    worksheet.Range(f"A3:{last_column_letter}{last_row}").PasteSpecial(Paste=-4122)
                    excel.CutCopyMode = False
                # Cari kodu Excel tarafından sayıya çevrilmemeli. Excel COM
                # biçim dizeleri kurulu Office diline bağlı olduğundan önce
                # Türkçe yerel biçim, ardından invariant biçim denenir. Biçim
                # ataması veri üretimini tek başına durdurmaz.
                text_column_formats: dict[int, object] = {}
                for index in self._force_text_column_indexes():
                    try:
                        text_column_formats[index] = worksheet.Cells(2, index + 1).NumberFormat
                    except Exception:
                        pass
                for start, end in self._contiguous_ranges(self._force_text_column_indexes()):
                    range_str = f"{self._excel_column_letter(start)}2:{self._excel_column_letter(end)}{last_row}"
                    try:
                        worksheet.Range(range_str).NumberFormat = "@"
                    except Exception:
                        pass
                for start, end in self._contiguous_ranges(self.profile.column_index(style="date")):
                    range_str = f"{self._excel_column_letter(start)}2:{self._excel_column_letter(end)}{last_row}"
                    try:
                        worksheet.Range(range_str).NumberFormatLocal = "gg.aa.yyyy"
                    except Exception:
                        try:
                            worksheet.Range(range_str).NumberFormat = "m/d/yy"
                        except Exception:
                            pass
                for start, end in self._contiguous_ranges(self.profile.column_index(style="amount")):
                    range_str = f"{self._excel_column_letter(start)}2:{self._excel_column_letter(end)}{last_row}"
                    try:
                        worksheet.Range(range_str).NumberFormatLocal = "#.##0,00"
                    except Exception:
                        try:
                            worksheet.Range(range_str).NumberFormat = "#,##0.00"
                        except Exception:
                            pass
                self._write_excel_values(
                    worksheet,
                    [self._record_values_for_excel_value2(record) for record in records],
                    template_path,
                    last_column_letter,
                    cell_by_cell=self.profile.profile_id == "netsis_virman_toplu",
                )
                # Metin hücrelerini yazarken geçici olarak "@" kullanmak
                # baştaki sıfırları ve uzun kodları korur. Ardından onaylı
                # şablonun hücre görünümünü geri yükle; veri türü metin kalır.
                for index, original_format in text_column_formats.items():
                    letter = self._excel_column_letter(index)
                    try:
                        worksheet.Range(f"{letter}2:{letter}{last_row}").NumberFormat = original_format
                    except Exception:
                        pass

            self._save_workbook_as_netsis(workbook, template_path, output_path)
            workbook.Close(SaveChanges=False)
            workbook = None
        except ExcelAutomationUnavailable:
            raise
        except Exception as error:
            if workbook is not None:
                try:
                    workbook.Close(SaveChanges=False)
                except Exception:
                    pass
            raise RuntimeError(
                f"'{self.profile.name}' uyumlu Excel dosyası Microsoft Excel ile "
                f"kaydedilemedi: {error}"
            ) from error
        finally:
            worksheet = None

        if not output_path.is_file():
            raise OSError(f"Excel çıktısı oluşturulamadı: {output_path}")
        return ensure_writable(output_path)

    @staticmethod
    def _write_excel_values(
        worksheet,
        rows: list[tuple],
        template_path: Path,
        last_column_letter: str,
        cell_by_cell: bool = False,
    ) -> None:
        """Verileri şablonun türüne göre Excel'e yazar.

        Netsis'in verdiği eski BIFF8 şablonunda ``Range.Value2`` ile bütün
        matrisi tek seferde atamak, Windows ACE/OLEDB sürücüsünün dosyayı
        ``External table is not in the expected format`` diyerek reddettiği
        bir SST akışı üretebiliyor. Aynı dosyaya hücre hücre yazmak ise
        Netsis'in kabul ettiği yapıyı koruyor. Diğer XLSX profillerinde hızlı
        toplu yazma yolu sürer; virman şablonunda baştaki sıfırları korumak
        için hücre hücre yazılır.
        """
        # Onaylı XLSX virman şablonunda Plas.Kodu gibi metin olarak saklanan
        # ancak sayısal görünüme sahip hücreler bulunuyor. Tüm matrisi tek
        # Range.Value2 çağrısıyla yazmak Excel'in "00" değerini 0 sayısına
        # dönüştürmesine yol açıyor. Her iki biçimde de hücre hücre yazarak
        # şablondaki veri türünü ve Netsis'in beklediği dosya yapısını koru.
        if template_path.suffix.lower() == ".xls" or cell_by_cell:
            for row_index, values in enumerate(rows, start=2):
                for column_index, value in enumerate(values, start=1):
                    worksheet.Cells(row_index, column_index).Value2 = value
            return

        last_row = len(rows) + 1
        worksheet.Range(f"A2:{last_column_letter}{last_row}").Value2 = tuple(rows)

    def _save_workbook_as_netsis(self, workbook, template_path: Path, output_path: Path) -> None:
        """Netsis'in verdiği BIFF8 şablonundaki dosya yapısını korur.

        Orijinal şablon zaten ``.xls`` ise ``SaveAs(..., FileFormat=56)``
        Excel'in bazı eski tablo akışlarını yeniden oluşturmasına yol
        açabiliyor. Ephesus bu dosyayı "External table" hatasıyla
        reddedebildiği için, aynı BIFF8 dosyasından doğrudan bir kopya alırız.
        Şablon ile istenen çıktı uzantısı aynıysa yine doğrudan kopya alınır;
        yalnız farklı uzantı isteyen profiller BIFF8'e dönüştürülür.
        """
        if self.profile.output_extension == template_path.suffix.lower():
            workbook.SaveCopyAs(str(output_path))
            return

        # xlExcel8 = Microsoft Excel 97-2003 BIFF8.
        workbook.SaveAs(
            str(output_path),
            FileFormat=self.XL_EXCEL_8,
            ConflictResolution=2,
            Local=True,
        )

    # Eski test ve entegrasyon çağrıları için geriye dönük ad.
    def _save_workbook_as_netsis_xls(self, workbook, template_path: Path, output_path: Path) -> None:
        self._save_workbook_as_netsis(workbook, template_path, output_path)

    def _get_excel_application(self):
        if self._excel is not None:
            return self._excel
        try:
            import pythoncom
            import win32com.client
        except ImportError as error:
            raise ExcelAutomationUnavailable(
                "pywin32 paketi bulunamadı; PowerShell Excel köprüsüne geçiliyor."
            ) from error

        try:
            pythoncom.CoInitialize()
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            excel.DisplayAlerts = False
            excel.EnableEvents = False
            excel.ScreenUpdating = False
        except Exception as error:
            try:
                pythoncom.CoUninitialize()
            except Exception:
                pass
            raise ExcelAutomationUnavailable(
                "Python Excel COM köprüsü başlatılamadı; PowerShell Excel köprüsüne geçiliyor."
            ) from error

        self._pythoncom = pythoncom
        self._excel = excel
        return excel

    def _write_with_powershell_excel(
        self,
        records: list[NetsisRecord],
        output_path: str | Path,
    ) -> Path:
        """Harici Python paketi gerektirmeden Excel COM ile gerçek BIFF8 üretir."""
        template_path = self._validate_template()
        output_path = self._prepare_output_path(output_path)

        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if not powershell:
            raise RuntimeError(
                "Microsoft Excel çıktısı için ne pywin32 ne de Windows PowerShell "
                "bulunabildi. Windows PowerShell ve Microsoft Excel kurulu olmalıdır."
            )

        date_columns = self.profile.column_index(style="date")
        amount_columns = self.profile.column_index(style="amount")
        double_columns = self.profile.column_index(style="integer")
        string_columns = sorted(set(
            self._force_text_column_indexes()
            + [
                i for i, column in enumerate(self.profile.columns)
                if column.source_kind == "const" and isinstance(column.value, str)
            ]
        ))

        payload = {
            "headers": self.profile.headers(),
            "output_extension": self.profile.output_extension,
            "date_columns": date_columns,
            "amount_columns": amount_columns,
            "string_columns": string_columns,
            "double_columns": double_columns,
            "cell_by_cell": self.profile.profile_id == "netsis_virman_toplu",
            # Her satırı nesne içine almak PowerShell'in tek satırlı diziyi
            # düzleştirmesini engeller.
            "rows": [
                {"values": self._powershell_record_values(record)}
                for record in records
            ],
        }

        with tempfile.TemporaryDirectory(prefix="carpan_netsis_") as temp_dir:
            temp_dir_path = Path(temp_dir)
            working_template_path = temp_dir_path / template_path.name
            shutil.copy2(template_path, working_template_path)
            data_path = temp_dir_path / "netsis_data.json"
            script_path = temp_dir_path / "save_netsis_excel.ps1"
            data_path.write_text(
                json.dumps(payload, ensure_ascii=False),
                encoding="utf-8-sig",
            )
            script_path.write_text(self._powershell_script(), encoding="utf-8-sig")

            command = [
                powershell,
                "-NoLogo",
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script_path),
                "-TemplatePath",
                str(working_template_path),
                "-OutputPath",
                str(output_path),
                "-DataPath",
                str(data_path),
            ]
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                errors="replace",
                creationflags=creationflags,
                check=False,
            )

            if completed.returncode != 0:
                details = (completed.stderr or completed.stdout or "Bilinmeyen hata").strip()
                raise RuntimeError(
                    f"'{self.profile.name}' uyumlu Excel dosyası PowerShell üzerinden "
                    f"Microsoft Excel ile kaydedilemedi: {details}"
                )

        if not output_path.is_file():
            raise OSError(f"Excel çıktısı oluşturulamadı: {output_path}")
        return ensure_writable(output_path)

    def _record_values_for_excel_value2(self, record: NetsisRecord) -> tuple:
        """Excel Value2 için tarihleri OLE Automation seri değerine çevirir."""
        values = list(self._record_values(record))
        for index in self.profile.column_index(style="date"):
            value = values[index]
            if isinstance(value, datetime):
                # Excel'in 1899-12-30 epoch'una göre OLE Automation tarihi.
                epoch = datetime(1899, 12, 30)
                values[index] = (value - epoch).total_seconds() / 86_400
        return tuple(values)

    def _powershell_record_values(self, record: NetsisRecord) -> list:
        values = list(self._record_values(record))
        for index in self.profile.column_index(style="date"):
            value = values[index]
            values[index] = value.strftime("%Y-%m-%d") if isinstance(value, datetime) else None
        return values

    @staticmethod
    def _powershell_script() -> str:
        return r'''param(
    [Parameter(Mandatory = $true)][string]$TemplatePath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(Mandatory = $true)][string]$DataPath
)

$ErrorActionPreference = "Stop"
$excel = $null
$workbook = $null
$worksheet = $null

function ExcelColumnLetter([int]$Index0Based) {
    $index = $Index0Based + 1
    $letters = ""
    while ($index -gt 0) {
        $remainder = ($index - 1) % 26
        $letters = [char](65 + $remainder) + $letters
        $index = [Math]::Floor(($index - 1) / 26)
    }
    return $letters
}

try {
    $payload = Get-Content -LiteralPath $DataPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $columnCount = $payload.headers.Count
    $dateColumns = @($payload.date_columns)
    $amountColumns = @($payload.amount_columns)
    $stringColumns = @($payload.string_columns)
    $doubleColumns = @($payload.double_columns)

    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.ScreenUpdating = $false

    $workbook = $excel.Workbooks.Open($TemplatePath, 0, $false)
    $workbook.CheckCompatibility = $false
    $worksheet = $workbook.Worksheets.Item(1)

    for ($column = 0; $column -lt $columnCount; $column++) {
        $actual = [string]$worksheet.Cells.Item(1, $column + 1).Value2
        $expected = [string]$payload.headers[$column]
        if ($actual -ne $expected) {
            throw "Sablon basligi uyusmuyor. Sutun $($column + 1): '$actual' / '$expected'"
        }
    }

    $rows = @($payload.rows)
    $usedRows = [int]$worksheet.UsedRange.Rows.Count
    $clearLastRow = [Math]::Max([Math]::Max($usedRows, $rows.Count + 1), 15)
    $lastColumnLetter = ExcelColumnLetter ($columnCount - 1)
    $worksheet.Range("A2:$lastColumnLetter$clearLastRow").ClearContents()

    if ($rows.Count -gt 0) {
        $lastRow = $rows.Count + 1
        if ($rows.Count -gt 1) {
            $worksheet.Range("A2:$lastColumnLetter" + "2").Copy()
            $worksheet.Range("A3:$lastColumnLetter$lastRow").PasteSpecial(-4122)
            $excel.CutCopyMode = $false
        }
        # Excel'in NumberFormat özelliği yerel dile bağlıdır. Türkçe Excel,
        # İngilizce "m/d/yy" biçimini COMException ile reddedebildiği için
        # önce yerel biçimler denenir. Biçimlendirme başarısız olsa bile veri
        # yazımı ve dosya kaydı durdurulmaz.
        $stringColumnFormats = @{}
        foreach ($column in $stringColumns) {
            $letter = ExcelColumnLetter $column
            try { $stringColumnFormats[[int]$column] = $worksheet.Cells.Item(2, $column + 1).NumberFormat } catch {}
            try { $worksheet.Range("$letter" + "2:$letter$lastRow").NumberFormat = "@" } catch {}
        }
        foreach ($column in $dateColumns) {
            $letter = ExcelColumnLetter $column
            try {
                $worksheet.Range("$letter" + "2:$letter$lastRow").NumberFormatLocal = "gg.aa.yyyy"
            }
            catch {
                try { $worksheet.Range("$letter" + "2:$letter$lastRow").NumberFormat = "m/d/yy" } catch {}
            }
        }
        foreach ($column in $amountColumns) {
            $letter = ExcelColumnLetter $column
            try {
                $worksheet.Range("$letter" + "2:$letter$lastRow").NumberFormatLocal = "#.##0,00"
            }
            catch {
                try { $worksheet.Range("$letter" + "2:$letter$lastRow").NumberFormat = "#,##0.00" } catch {}
            }
        }

        $matrix = [System.Array]::CreateInstance([object], [int[]]@($rows.Count, $columnCount))
        for ($rowIndex = 0; $rowIndex -lt $rows.Count; $rowIndex++) {
            $rowValues = @($rows[$rowIndex].values)
            for ($column = 0; $column -lt $columnCount; $column++) {
                $value = $rowValues[$column]
                if ($null -ne $value) {
                    if ($dateColumns -contains $column) {
                        $value = [datetime]::ParseExact(
                            [string]$value,
                            "yyyy-MM-dd",
                            [Globalization.CultureInfo]::InvariantCulture
                        ).ToOADate()
                    }
                    elseif ($stringColumns -contains $column) {
                        $value = [string]$value
                    }
                    elseif ($doubleColumns -contains $column) {
                        $value = [double]$value
                    }
                }
                $matrix.SetValue($value, $rowIndex, $column)
            }
        }
        if ([IO.Path]::GetExtension($TemplatePath) -ieq ".xls" -or [bool]$payload.cell_by_cell) {
            for ($rowIndex = 0; $rowIndex -lt $rows.Count; $rowIndex++) {
                for ($column = 0; $column -lt $columnCount; $column++) {
                    $worksheet.Cells.Item($rowIndex + 2, $column + 1).Value2 = $matrix.GetValue($rowIndex, $column)
                }
            }
        }
        else {
            $worksheet.Range("A2:$lastColumnLetter$lastRow").Value2 = $matrix
        }
        foreach ($column in $stringColumns) {
            if ($stringColumnFormats.ContainsKey([int]$column)) {
                $letter = ExcelColumnLetter $column
                try {
                    $worksheet.Range("$letter" + "2:$letter$lastRow").NumberFormat = $stringColumnFormats[[int]$column]
                }
                catch {}
            }
        }
    }

    # Şablon ve hedef biçimi aynıysa orijinal dosya yapısını koru.
    if ([IO.Path]::GetExtension($TemplatePath) -ieq [string]$payload.output_extension) {
        $workbook.SaveCopyAs($OutputPath)
    }
    else {
        $workbook.SaveAs($OutputPath, 56)
    }
    $workbook.Close($false)
    $workbook = $null
}
finally {
    if ($workbook -ne $null) {
        try { $workbook.Close($false) } catch {}
    }
    if ($excel -ne $null) {
        try { $excel.Quit() } catch {}
    }
    if ($worksheet -ne $null) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($worksheet)
    }
    if ($workbook -ne $null) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($workbook)
    }
    if ($excel -ne $null) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($excel)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
'''

    def _write_with_xlwt(self, records: list[NetsisRecord], output_path: str | Path) -> Path:
        if self.profile.output_extension != ".xls":
            raise RuntimeError(
                f"'{self.profile.name}' çıktısı {self.profile.output_extension} biçimindeki "
                "onaylı şablon ve Microsoft Excel olmadan üretilemez."
            )
        workbook = xlwt.Workbook(encoding="utf-8", style_compression=2)
        worksheet = workbook.add_sheet("Sheet1")
        styles = make_styles()
        worksheet.panes_frozen = True
        worksheet.horz_split_pos = 1

        headers = self.profile.headers()
        widths = self.profile.widths()
        for col_index, (header, width) in enumerate(zip(headers, widths)):
            worksheet.write(0, col_index, header, styles["header"])
            worksheet.col(col_index).width = min(width * 256, 65_535)

        for row_index, record in enumerate(records, start=1):
            self._write_xlwt_row(worksheet, row_index, record, styles)

        return save_xls(workbook, output_path)

    def _record_values(self, record: NetsisRecord) -> tuple:
        tarih = self._date_at_midnight(record.islem_tarihi)
        values: list = []
        for column in self.profile.columns:
            if column.source_kind == "const":
                values.append(column.value)
                continue
            # source_kind == "field"
            if column.style == "date":
                values.append(tarih)
            elif column.field == "cari_kodu":
                values.append(str(record.cari_kodu))
            elif column.field == "tutar":
                values.append(float(record.tutar))
            else:
                values.append(getattr(record, column.field))
        return tuple(values)

    def _write_xlwt_row(self, ws, row: int, record: NetsisRecord, styles) -> None:
        values = self._record_values(record)
        for col_index, (value, column) in enumerate(zip(values, self.profile.columns)):
            write_cell(ws, row, col_index, value, styles, column.style)

    @staticmethod
    def _date_at_midnight(value):
        if isinstance(value, datetime):
            return datetime(value.year, value.month, value.day)
        if isinstance(value, date):
            return datetime(value.year, value.month, value.day)
        return None
