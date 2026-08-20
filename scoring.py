"""
Scoring Engine (scoring.py) for UKK AWS Cloud Engineer Grader.
Calculates granular component scores, weights, totals, and summary records.
"""
from typing import Dict, Any, List, Tuple
from datetime import datetime

from config import (
    WEIGHT_INFRASTRUCTURE,
    WEIGHT_FUNCTION,
    PASSING_SCORE,
)


class ScoringEngine:
    def __init__(
        self,
        weight_infra: float = WEIGHT_INFRASTRUCTURE,
        weight_fungsi: float = WEIGHT_FUNCTION,
        passing_score: float = PASSING_SCORE,
    ):
        self.weight_infra = weight_infra
        self.weight_fungsi = weight_fungsi
        self.passing_score = passing_score

    def calculate_scores(
        self,
        nama: str,
        nis: str,
        evidence_list: List[Dict[str, Any]],
        start_time: datetime,
        end_time: datetime,
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Calculate total and granular scores from evidence list.
        Returns:
            summary_dict (for HASIL sheet)
            detail_records (for DETAIL sheet)
        """
        infra_score_earned = 0.0
        infra_max = 0.0

        fungsi_score_earned = 0.0
        fungsi_max = 0.0

        pass_cnt = 0
        fail_cnt = 0
        warn_cnt = 0
        error_cnt = 0

        # Component trackers: {Component_Name: (earned, max)}
        comp_scores: Dict[str, List[float]] = {
            "VPC": [0.0, 0.0],
            "SUBNET": [0.0, 0.0],
            "IGW": [0.0, 0.0],
            "NAT": [0.0, 0.0],
            "ROUTE": [0.0, 0.0],
            "SECURITY_GROUP": [0.0, 0.0],
            "RDS": [0.0, 0.0],
            "S3": [0.0, 0.0],
            "SNS": [0.0, 0.0],
            "EC2_BE": [0.0, 0.0],
            "EFS": [0.0, 0.0],
            "LAUNCH_TEMPLATE": [0.0, 0.0],
            "ASG": [0.0, 0.0],
            "TARGET_GROUP": [0.0, 0.0],
            "ALB": [0.0, 0.0],
            "HEALTH_CHECK": [0.0, 0.0],
            "DATABASE": [0.0, 0.0],
            "S3_UPLOAD": [0.0, 0.0],
            "SNS_NOTIFICATION": [0.0, 0.0],
            "EFS_SESSION": [0.0, 0.0],
            "ASG_RECOVERY": [0.0, 0.0],
        }

        detail_records = []
        timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        for item in evidence_list:
            cat = item.get("category")
            score = float(item.get("score", 0.0))
            m_score = float(item.get("max_score", 0.0))
            status = item.get("status", "FAIL")

            if status == "PASS":
                pass_cnt += 1
            elif status == "FAIL":
                fail_cnt += 1
            elif status == "WARN":
                warn_cnt += 1
            elif status == "ERROR":
                error_cnt += 1

            if cat == "Infrastructure":
                infra_score_earned += score
                infra_max += m_score
            else:
                fungsi_score_earned += score
                fungsi_max += m_score

            # Map to component column
            chk_id = item.get("check_id", "")
            for comp_key in comp_scores.keys():
                if comp_key in chk_id or comp_key in item.get("component", "").upper():
                    comp_scores[comp_key][0] += score
                    comp_scores[comp_key][1] += m_score
                    break

            # Build detail record
            detail_records.append({
                "Timestamp": timestamp_str,
                "Nama": nama,
                "NIS": nis,
                "Check_ID": item.get("check_id"),
                "Kategori": item.get("category"),
                "Komponen": item.get("component"),
                "Requirement": item.get("requirement"),
                "Expected": item.get("expected"),
                "Actual": item.get("actual"),
                "Score": score,
                "Max_Score": m_score,
                "Status": status,
                "Error_Code": item.get("error_code", ""),
                "Error_Message": item.get("error_message", ""),
                "Evidence": item.get("evidence", ""),
            })

        # Calculate Scaled Scores
        norm_infra = (infra_score_earned / infra_max * self.weight_infra) if infra_max > 0 else 0.0
        norm_fungsi = (fungsi_score_earned / fungsi_max * self.weight_fungsi) if fungsi_max > 0 else 0.0
        total_score = round(norm_infra + norm_fungsi, 1)

        final_status = "PASS" if total_score >= self.passing_score else "FAIL"

        duration_sec = (end_time - start_time).total_seconds()
        duration_str = f"{int(duration_sec // 60)}m {int(duration_sec % 60)}s"

        def fmt_comp(comp_k: str) -> str:
            earned, max_s = comp_scores[comp_k]
            return f"{int(earned)}/{int(max_s)}" if max_s > 0 else "-"

        summary_dict = {
            "Timestamp": timestamp_str,
            "Nama": nama,
            "NIS": nis,
            "VPC": fmt_comp("VPC"),
            "SUBNET": fmt_comp("SUBNET"),
            "IGW": fmt_comp("IGW"),
            "NAT": fmt_comp("NAT"),
            "ROUTE": fmt_comp("ROUTE"),
            "SECURITY_GROUP": fmt_comp("SECURITY_GROUP"),
            "RDS": fmt_comp("RDS"),
            "S3": fmt_comp("S3"),
            "SNS": fmt_comp("SNS"),
            "EC2_BE": fmt_comp("EC2_BE"),
            "EFS": fmt_comp("EFS"),
            "LAUNCH_TEMPLATE": fmt_comp("LAUNCH_TEMPLATE"),
            "ASG": fmt_comp("ASG"),
            "TARGET_GROUP": fmt_comp("TARGET_GROUP"),
            "ALB": fmt_comp("ALB"),
            "HEALTH_CHECK": fmt_comp("HEALTH_CHECK"),
            "DATABASE": fmt_comp("DATABASE"),
            "S3_UPLOAD": fmt_comp("S3_UPLOAD"),
            "SNS_NOTIFICATION": fmt_comp("SNS_NOTIFICATION"),
            "ASG_RECOVERY": fmt_comp("ASG_RECOVERY"),
            "EFS_SESSION": fmt_comp("EFS_SESSION"),
            "INFRA_SCORE": round(norm_infra, 1),
            "FUNGSI_SCORE": round(norm_fungsi, 1),
            "TOTAL_SCORE": total_score,
            "STATUS": final_status,
            "TOTAL_CHECK": len(evidence_list),
            "PASS": pass_cnt,
            "FAIL": fail_cnt,
            "WARN": warn_cnt,
            "ERROR": error_cnt,
            "WAKTU_MULAI": start_time.strftime("%H:%M:%S"),
            "WAKTU_SELESAI": end_time.strftime("%H:%M:%S"),
            "DURASI": duration_str,
        }

        return summary_dict, detail_records
