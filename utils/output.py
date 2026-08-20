"""
Terminal formatting and local evidence logging utility.
"""
import os
import json
import csv
from datetime import datetime
from typing import Any, Dict, List

try:
    from colorama import init, Fore, Style
    init(autoreset=True)
    GREEN = Fore.GREEN
    RED = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN = Fore.CYAN
    MAGENTA = Fore.MAGENTA
    BOLD = Style.BRIGHT
    RESET = Style.RESET_ALL
except ImportError:
    GREEN = ""
    RED = ""
    YELLOW = ""
    CYAN = ""
    MAGENTA = ""
    BOLD = ""
    RESET = ""


def print_banner():
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}   UKK AWS CLOUD ENGINEER AUTOMATED GRADER V1        {RESET}")
    print(f"{BOLD}{CYAN}   SMKN 1 Banyumas — Program MBG Deployment           {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")


def print_participant_header(index: int, total: int, nama: str, nis: str, account_id: str, region: str):
    print(f"{BOLD}{MAGENTA}[{index}/{total}] {nama} (NIS: {nis}){RESET}")
    print(f"AWS Account : {account_id}")
    print(f"Region      : {region}\n")


def print_component_result(category: str, component: str, passed: bool, note: str = ""):
    icon = f"{GREEN}✓{RESET}" if passed else f"{RED}✗{RESET}"
    extra = f" ({YELLOW}{note}{RESET})" if note else ""
    print(f"  {icon} {component}{extra}")


def print_participant_summary(score_infra: float, score_fungsi: float, total_score: float, pass_cnt: int, fail_cnt: int, warn_cnt: int, err_cnt: int, status: str):
    color = GREEN if status == "PASS" else RED
    print(f"\n{BOLD}Nilai Akhir:{RESET}")
    print(f"  Infrastructure : {score_infra:.1f}")
    print(f"  Function       : {score_fungsi:.1f}")
    print(f"  Total Score    : {BOLD}{total_score:.1f} / 100{RESET}")
    print(f"  Checks         : {GREEN}{pass_cnt} PASS{RESET}, {RED}{fail_cnt} FAIL{RESET}, {YELLOW}{warn_cnt} WARN{RESET}, {MAGENTA}{err_cnt} ERROR{RESET}")
    print(f"  Status         : {BOLD}{color}{status}{RESET}\n")
    print("-" * 54)


def print_batch_summary(total: int, passed: int, failed: int, errors: int):
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}                   BATCH COMPLETE                     {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}")
    print(f"Processed  : {total}")
    print(f"PASS       : {GREEN}{passed}{RESET}")
    print(f"FAIL       : {RED}{failed}{RESET}")
    print(f"ERROR      : {MAGENTA}{errors}{RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")


def save_local_backup(all_summaries: List[Dict[str, Any]], all_details: List[Dict[str, Any]]):
    """Save local backup to results/ directory in JSON and CSV format."""
    os.makedirs("results", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save Summary CSV
    if all_summaries:
        csv_file = os.path.join("results", f"results_{timestamp}.csv")
        keys = list(all_summaries[0].keys())
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(all_summaries)
        print(f"Backup CSV disimpan ke: {csv_file}")

    # Save Detail JSON
    if all_details:
        json_file = os.path.join("results", f"details_{timestamp}.json")
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(all_details, f, indent=2, ensure_ascii=False)
        print(f"Backup Detail JSON disimpan ke: {json_file}")
