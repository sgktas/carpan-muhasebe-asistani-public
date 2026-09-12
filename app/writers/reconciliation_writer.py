from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.core.reconciliation_engine import ReconciliationEngine, ReconciliationResult


class ReconciliationReportWriter:
    HEADER_FILL = PatternFill(start_color="1F2B3A", end_color="1F2B3A", fill_type="solid")
    HEADER_FONT = Font(color="FFFFFF", bold=True)
    OK_FILL = PatternFill(start_color="DFF5E1", end_color="DFF5E1", fill_type="solid")
    WARN_FILL = PatternFill(start_color="FDEBEC", end_color="FDEBEC", fill_type="solid")

    def write(self, result: ReconciliationResult, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        workbook = Workbook()
        self._write_summary_sheet(workbook.active, result)
        self._write_correction_sheet(
            workbook.create_sheet("Nokta Atışı Düzeltme"),
            self._build_correction_rows(result),
        )

        workbook.save(output_path)
        return output_path

    def _write_summary_sheet(self, sheet, result: ReconciliationResult) -> None:
        sheet.title = "Özet"
        kalan_sayisi = len(result.sadece_bankada) + len(result.sadece_netposte)
        if result.mutabik and kalan_sayisi == 0:
            durum = "TAM MUTABIK"
        elif result.mutabik:
            durum = f"BAKİYE TUTUYOR — ama {kalan_sayisi} kayıt açıklanamadı, incelenmeli"
        else:
            if result.hareket_farki == 0 and result.devir_farki:
                durum = "MUTABIK DEĞİL — hareketler tutuyor, devreden bakiye farklı"
            else:
                durum = "MUTABIK DEĞİL — farkı inceleyin"

        rows = [
            ("Banka Devreden Bakiyesi", result.banka_devir_bakiyesi),
            ("Netsis Devreden Bakiyesi", result.netsis_devir_bakiyesi),
            ("Devreden Bakiye Farkı", result.devir_farki),
            ("Dönem Hareketleri Farkı", result.hareket_farki),
            ("Banka Bakiyesi (ay sonu)", result.banka_bakiyesi),
            ("Netsis Bakiyesi (ay sonu)", result.netsis_bakiyesi),
            ("Fark", result.fark),
            ("Eşleşen İşlem Sayısı", result.eslesen_sayisi),
            ("Bölünmüş Fiş Olarak Tanınan Grup Sayısı", result.bolunmus_grup_sayisi),
            ("Sadece Bankada Olan Sayısı", len(result.sadece_bankada)),
            ("Sadece Netsis'te Olan Sayısı", len(result.sadece_netposte)),
            ("Durum", durum),
        ]
        for row_index, (label, value) in enumerate(rows, start=1):
            sheet.cell(row=row_index, column=1, value=label).font = Font(bold=True)
            sheet.cell(row=row_index, column=2, value=value)
        for row_index in range(1, 8):
            sheet.cell(row=row_index, column=2).number_format = "#,##0.00"
        status_cell = sheet.cell(row=len(rows), column=2)
        status_cell.fill = self.OK_FILL if (result.mutabik and kalan_sayisi == 0) else self.WARN_FILL
        sheet.column_dimensions["A"].width = 42
        sheet.column_dimensions["B"].width = 52

    def _write_correction_sheet(self, sheet, rows: list[list]) -> None:
        headers = [
            "Düzeltme Türü", "Banka Tarihi", "Netsis Tarihi",
            "Banka Açıklaması", "Netsis Açıklaması", "Banka Tutarı",
            "Netsis Tutarı", "Fark", "Kaynak Satırlar", "Yapılacak Düzeltme",
        ]
        for col_index, header in enumerate(headers, start=1):
            cell = sheet.cell(row=1, column=col_index, value=header)
            cell.fill = self.HEADER_FILL
            cell.font = self.HEADER_FONT
            cell.alignment = Alignment(horizontal="center")
        for row_index, row in enumerate(rows, start=2):
            for col_index, value in enumerate(row, start=1):
                sheet.cell(row=row_index, column=col_index, value=value)
            for amount_column in (6, 7, 8):
                sheet.cell(row=row_index, column=amount_column).number_format = "#,##0.00"
            sheet.cell(row=row_index, column=10).alignment = Alignment(wrap_text=True, vertical="top")
        widths = [24, 18, 18, 52, 52, 18, 18, 18, 34, 72]
        for index, width in enumerate(widths, start=1):
            sheet.column_dimensions[sheet.cell(row=1, column=index).column_letter].width = width
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

    def _build_correction_rows(self, result: ReconciliationResult) -> list[list]:
        rows: list[list] = []
        if result.devir_farki:
            direction = "artırılmalı" if result.devir_farki > 0 else "azaltılmalı"
            rows.append([
                "DEVREDEN BAKİYE", None, None,
                "Dönem başı devreden bakiye", "Dönem başı devreden bakiye",
                result.banka_devir_bakiyesi, result.netsis_devir_bakiyesi,
                result.devir_farki, "Dönem başı",
                f"Netsis devreden bakiyesi {abs(result.devir_farki):,.2f} TL {direction}; "
                "önceki dönem kapanış kaydını kontrol edin.",
            ])

        bank_left = list(result.sadece_bankada)
        netsis_left = list(result.sadece_netposte)
        used_bank: set[int] = set()
        used_netsis: set[int] = set()

        for bank_record in bank_left:
            candidates = [
                record for record in netsis_left
                if id(record) not in used_netsis
                and record.tarih and bank_record.tarih
                and abs((record.tarih.date() - bank_record.tarih.date()).days) <= 1
                and ReconciliationEngine._descriptions_overlap(bank_record.aciklama, record.aciklama)
            ]
            has_shifted_date = any(
                record.tarih.date() != bank_record.tarih.date() for record in candidates
            )
            if not candidates or not has_shifted_date or not ReconciliationEngine._sums_reconcile(
                bank_record.tutar, [record.tutar for record in candidates]
            ):
                continue
            used_bank.add(id(bank_record))
            used_netsis.update(id(record) for record in candidates)
            rows.append(self._correction_row(
                "TARİH KAYMASI", [bank_record], candidates,
                "Tutar eksik değil. Netsis satırlarının işlem tarihini banka tarihine göre kontrol edin.",
            ))

        for bank_record in bank_left:
            if id(bank_record) in used_bank:
                continue
            candidates = [
                record for record in netsis_left
                if id(record) not in used_netsis
                and record.tarih and bank_record.tarih
                and record.tarih.date() == bank_record.tarih.date()
                and ReconciliationEngine._descriptions_overlap(bank_record.aciklama, record.aciklama)
            ]
            if not candidates:
                continue
            used_bank.add(id(bank_record))
            used_netsis.update(id(record) for record in candidates)
            difference = round(bank_record.tutar - sum(record.tutar for record in candidates), 2)
            direction = "artırın" if difference > 0 else "azaltın"
            rows.append(self._correction_row(
                "TUTAR FARKI", [bank_record], candidates,
                f"Netsis hareket toplamını {abs(difference):,.2f} TL {direction}; banka tutarını esas alın.",
            ))

        for record in bank_left:
            if id(record) not in used_bank:
                rows.append(self._correction_row(
                    "YALNIZ BANKADA", [record], [],
                    "Banka hareketi Netsis'te bulunamadı. Kaydın Netsis'e işlenip işlenmediğini kontrol edin.",
                ))
        for record in netsis_left:
            if id(record) not in used_netsis:
                rows.append(self._correction_row(
                    "YALNIZ NETSİS'TE", [], [record],
                    "Netsis hareketi banka ekstresinde bulunamadı. Tarih, tutar ve mükerrer kayıt durumunu kontrol edin.",
                ))

        if not rows:
            rows.append([
                "DÜZELTME YOK", None, None, "", "", 0.0, 0.0, 0.0, "",
                "Banka ve Netsis kayıtları tam mutabık; düzeltilecek kayıt bulunamadı.",
            ])
        return rows

    @staticmethod
    def _correction_row(kind: str, bank_records: list, netsis_records: list, action: str) -> list:
        bank_total = round(sum(record.tutar for record in bank_records), 2)
        netsis_total = round(sum(record.tutar for record in netsis_records), 2)
        bank_dates = ", ".join(sorted({record.tarih.strftime("%d.%m.%Y") for record in bank_records if record.tarih}))
        netsis_dates = ", ".join(sorted({record.tarih.strftime("%d.%m.%Y") for record in netsis_records if record.tarih}))
        bank_rows = ", ".join(str(record.kaynak_satir) for record in bank_records)
        netsis_rows = ", ".join(str(record.kaynak_satir) for record in netsis_records)
        return [
            kind, bank_dates, netsis_dates,
            " | ".join(record.aciklama for record in bank_records),
            " | ".join(record.aciklama for record in netsis_records),
            bank_total, netsis_total, round(bank_total - netsis_total, 2),
            f"Banka: {bank_rows or '-'} | Netsis: {netsis_rows or '-'}", action,
        ]
