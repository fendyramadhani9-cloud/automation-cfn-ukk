"""
Google Spreadsheet integration (sheets.py).
Reads participants, updates summary rows, and appends detail evidence.
Includes local fallback mode if service account is not provided.
"""
import os
from typing import List, Dict, Any, Optional

try:
    import gspread
except ImportError:
    gspread = None

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
        if gspread is None:
            print("[Sheets] Module 'gspread' belum terinstall (jalankan: pip install -r requirements.txt). Menggunakan mode Lokal.")
            return False

        if not os.path.exists(self.creds_file):
            print(f"[Sheets] '{self.creds_file}' tidak ditemukan. Menggunakan mode Lokal.")
            return False

        try:
            self.client = gspread.service_account(filename=self.creds_file)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            self.is_connected = True
            print(f"[Sheets] Terhubung ke Google Spreadsheet: {self.spreadsheet.title}")
            return True
        except Exception as e:
            print(f"[Sheets] Gagal menghubungkan Google Sheet: {e}. Menggunakan mode Lokal.")
            return False

    def get_participants(self) -> List[Dict[str, Any]]:
        """Read all rows from PESERTA sheet and parse credentials."""
        if not self.is_connected:
            # Fallback default participant for standalone testing
            return [
                {
                    "row_index": 2,
                    "Timestamp": "2026-08-20 08:00:00",
                    "Nama": "Fendy Ramadhani",
                    "NIS": "15671",
                    "Status Pemeriksaan": "WAITING",
                    "aws_access_key_id": None,
                    "aws_secret_access_key": None,
                    "aws_session_token": None,
                }
            ]

        try:
            sheet = self.spreadsheet.worksheet(SHEET_PESERTA)
            records = sheet.get_all_records()
            participants = []

            for idx, r in enumerate(records, start=2):
                r["row_index"] = idx
                
                # Extract Credentials flexibly
                access_key = None
                secret_key = None
                session_token = None

                # 1. Check direct separate columns
                for k, v in r.items():
                    key_lower = k.lower().replace(" ", "_").replace("-", "_")
                    val_str = str(v).strip()
                    if "access_key" in key_lower and "secret" not in key_lower:
                        access_key = val_str
                    elif "secret" in key_lower:
                        secret_key = val_str
                    elif "session_token" in key_lower or "token" in key_lower:
                        session_token = val_str

                # 2. Check if student pasted entire AWS Details block in one field
                for k, v in r.items():
                    val_str = str(v)
                    if "aws_access_key_id" in val_str:
                        for line in val_str.splitlines():
                            line = line.strip()
                            if line.startswith("aws_access_key_id"):
                                access_key = line.split("=", 1)[-1].strip()
                            elif line.startswith("aws_secret_access_key"):
                                secret_key = line.split("=", 1)[-1].strip()
                            elif line.startswith("aws_session_token"):
                                session_token = line.split("=", 1)[-1].strip()

                r["aws_access_key_id"] = access_key
                r["aws_secret_access_key"] = secret_key
                r["aws_session_token"] = session_token
                participants.append(r)

            return participants
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
