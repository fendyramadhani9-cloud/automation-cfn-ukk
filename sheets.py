"""
Google Spreadsheet integration (sheets.py).
Reads participants, updates summary rows, and appends detail evidence.
Includes local fallback mode if service account is not provided.
"""
import os
from typing import List, Dict, Any, Optional

from config import (
    SPREADSHEET_ID,
    SHEET_PESERTA,
    SHEET_HASIL,
    SHEET_DETAIL,
    CREDENTIALS_FILE,
)


class GoogleSheetsManager:
    def __init__(self, spreadsheet_id: str = SPREADSHEET_ID, creds_file: str = CREDENTIALS_FILE):
        self.spreadsheet_id = spreadsheet_id
        self.creds_file = creds_file
        self.client = None
        self.spreadsheet = None
        self.is_connected = False

    def connect(self) -> bool:
        """Authenticate and open Google Spreadsheet."""
        if not os.path.exists(self.creds_file):
            print(f"[Sheets] '{self.creds_file}' tidak ditemukan. Menggunakan mode Lokal.")
            return False

        try:
            import gspread
            self.client = gspread.service_account(filename=self.creds_file)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.is_connected = True
            print(f"[Sheets] Terhubung ke Google Spreadsheet: {self.spreadsheet.title}")
            return True
        except Exception as e:
            print(f"[Sheets] Gagal menghubungkan Google Sheet: {e}. Menggunakan mode Lokal.")
            return False

    def get_participants(self) -> List[Dict[str, Any]]:
        """Read all rows from PESERTA sheet."""
        if not self.is_connected:
            # Fallback default participant for standalone testing
            return [
                {
                    "row_index": 2,
                    "Timestamp": "2026-08-20 08:00:00",
                    "Nama": "Fendy Ramadhani",
                    "NIS": "15671",
                    "Status Pemeriksaan": "WAITING",
                }
            ]

        try:
            sheet = self.spreadsheet.worksheet(SHEET_PESERTA)
            records = sheet.get_all_records()
            for idx, r in enumerate(records, start=2):
                r["row_index"] = idx
            return records
        except Exception as e:
            print(f"[Sheets] Error reading PESERTA sheet: {e}")
            return []

    def update_participant_status(self, row_index: int, status: str):
        """Update status column in PESERTA sheet (WAITING / RUNNING / DONE / ERROR)."""
        if not self.is_connected:
            return
        try:
            sheet = self.spreadsheet.worksheet(SHEET_PESERTA)
            sheet.update_cell(row_index, 4, status)
        except Exception as e:
            print(f"[Sheets] Error updating participant status: {e}")

    def update_hasil(self, summary_dict: Dict[str, Any]):
        """Write or update summary row in HASIL sheet."""
        if not self.is_connected:
            return

        try:
            sheet = self.spreadsheet.worksheet(SHEET_HASIL)
            headers = list(summary_dict.keys())
            
            # If sheet is empty, write headers
            existing = sheet.get_all_values()
            if not existing:
                sheet.append_row(headers)

            row_values = list(summary_dict.values())
            sheet.append_row(row_values)
        except Exception as e:
            print(f"[Sheets] Error appending to HASIL sheet: {e}")

    def append_details(self, detail_records: List[Dict[str, Any]]):
        """Append granular check evidence rows to DETAIL sheet."""
        if not self.is_connected or not detail_records:
            return

        try:
            sheet = self.spreadsheet.worksheet(SHEET_DETAIL)
            headers = list(detail_records[0].keys())

            existing = sheet.get_all_values()
            if not existing:
                sheet.append_row(headers)

            rows_to_append = [list(rec.values()) for rec in detail_records]
            sheet.append_rows(rows_to_append)
        except Exception as e:
            print(f"[Sheets] Error appending to DETAIL sheet: {e}")
