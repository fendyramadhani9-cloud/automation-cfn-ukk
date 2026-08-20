"""
UKK AWS Cloud Engineer Automated Grader V1 - Main Entrypoint
SMKN 1 Banyumas — Program MBG Deployment
"""
import sys
import argparse
from datetime import datetime
from typing import List, Dict, Any

from config import DEFAULT_REGION, DEFAULT_PROFILE, SPREADSHEET_ID
from aws_session import AWSSessionManager
from cek_infra import InfrastructureChecker
from cek_fungsi import FunctionalChecker
from scoring import ScoringEngine
from sheets import GoogleSheetsManager
from utils.output import (
    print_banner,
    print_participant_header,
    print_component_result,
    print_participant_summary,
    print_batch_summary,
    save_local_backup,
)


def parse_arguments():
    parser = argparse.ArgumentParser(description="UKK AWS Cloud Engineer Automated Grader V1")
    parser.add_argument("--profile", default=DEFAULT_PROFILE, help="AWS Profile name")
    parser.add_argument("--region", default=DEFAULT_REGION, help="AWS Region (default: us-east-1)")
    parser.add_argument("--participant", default=None, help="Grade a specific participant by name")
    parser.add_argument("--force", action="store_true", help="Re-evaluate participants even if already DONE")
    parser.add_argument("--destructive-test", action="store_true", help="Enable destructive tests (ASG auto-healing termination)")
    parser.add_argument("--spreadsheet-id", default=SPREADSHEET_ID, help="Google Spreadsheet ID")
    return parser.parse_args()


def main():
    args = parse_arguments()
    print_banner()

    # 1. Connect to Google Sheets
    sheets = GoogleSheetsManager(spreadsheet_id=args.spreadsheet_id)
    sheets.connect()

    # 2. Load Participants from Spreadsheet
    participants = sheets.get_participants()
    if not participants:
        print("[INFO] Tidak ada data peserta yang ditemukan.")
        return

    # Filter participant if specified
    if args.participant:
        participants = [p for p in participants if args.participant.lower() in p.get("Nama", "").lower()]
        if not participants:
            print(f"[INFO] Peserta '{args.participant}' tidak ditemukan.")
            return

    total_participants = len(participants)
    print(f"[INFO] Memproses {total_participants} peserta dari Spreadsheet...\n")

    scoring_engine = ScoringEngine()

    batch_passed = 0
    batch_failed = 0
    batch_errors = 0
    all_summaries: List[Dict[str, Any]] = []
    all_details: List[Dict[str, Any]] = []

    # 3. Batch Processing Loop
    for idx, p in enumerate(participants, start=1):
        nama = p.get("Nama", "Peserta")
        nis = str(p.get("NIS", ""))
        status_pemeriksaan = p.get("Status Pemeriksaan", "WAITING")
        row_idx = p.get("row_index", 2)

        # Resume Mechanism: Skip DONE unless --force
        if status_pemeriksaan == "DONE" and not args.force:
            print(f"[{idx}/{total_participants}] {nama} (NIS: {nis}) -> Sudah DINILAI (SKIP)")
            continue

        # Authenticate using this specific participant's credentials from Spreadsheet
        aws = AWSSessionManager(
            aws_access_key_id=p.get("aws_access_key_id"),
            aws_secret_access_key=p.get("aws_secret_access_key"),
            aws_session_token=p.get("aws_session_token"),
            profile_name=args.profile,
            region_name=args.region,
        )
        auth_result = aws.initialize()

        if not auth_result["success"]:
            batch_errors += 1
            print_participant_header(idx, total_participants, nama, nis, "AUTH_FAILED", args.region)
            print(f"[ERROR] Credential AWS tidak valid untuk {nama}: {auth_result['error']}\n")
            sheets.update_participant_status(row_idx, "ERROR")
            continue

        account_id = auth_result["account_id"]
        print_participant_header(idx, total_participants, nama, nis, account_id, args.region)
        sheets.update_participant_status(row_idx, "RUNNING")
        start_time = datetime.now()

        try:
            # Step A: Infrastructure Check
            print("Pemeriksaan Infrastruktur:")
            infra_checker = InfrastructureChecker(aws)
            infra_evidence = infra_checker.run_all_checks(nis=nis)

            # Print quick progress for infra components
            for item in infra_evidence:
                comp = item.get("component")
                passed = item.get("status") == "PASS"
                note = item.get("error_code") if not passed else ""
                print_component_result("Infrastructure", comp, passed, note)

            # Step B: Functional Check
            print("\nPemeriksaan Fungsi:")
            fungsi_checker = FunctionalChecker(
                aws_session=aws,
                infra_context=infra_checker.context,
                destructive_mode=args.destructive_test,
            )
            fungsi_evidence = fungsi_checker.run_all_checks()

            for item in fungsi_evidence:
                comp = item.get("component")
                passed = item.get("status") == "PASS"
                note = item.get("error_code") if not passed else ""
                print_component_result("Function", comp, passed, note)

            # Step C: Scoring & Summary
            all_evidence = infra_evidence + fungsi_evidence
            end_time = datetime.now()

            summary, details = scoring_engine.calculate_scores(
                nama=nama,
                nis=nis,
                evidence_list=all_evidence,
                start_time=start_time,
                end_time=end_time,
            )

            all_summaries.append(summary)
            all_details.extend(details)

            # Print Summary for Participant
            print_participant_summary(
                score_infra=summary["INFRA_SCORE"],
                score_fungsi=summary["FUNGSI_SCORE"],
                total_score=summary["TOTAL_SCORE"],
                pass_cnt=summary["PASS"],
                fail_cnt=summary["FAIL"],
                warn_cnt=summary["WARN"],
                err_cnt=summary["ERROR"],
                status=summary["STATUS"],
            )

            if summary["STATUS"] == "PASS":
                batch_passed += 1
            else:
                batch_failed += 1

            # Step D: Upload to Google Sheets
            sheets.update_hasil(summary)
            sheets.append_details(details)
            sheets.update_participant_status(row_idx, "DONE")

        except Exception as e:
            batch_errors += 1
            print(f"[ERROR] Terjadi kesalahan saat memeriksa {nama}: {e}")
            sheets.update_participant_status(row_idx, "ERROR")

    # 5. Save Local Backup Files
    save_local_backup(all_summaries, all_details)

    # 6. Final Batch Summary
    print_batch_summary(
        total=total_participants,
        passed=batch_passed,
        failed=batch_failed,
        errors=batch_errors,
    )


if __name__ == "__main__":
    main()
