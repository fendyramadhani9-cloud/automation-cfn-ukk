#!/usr/bin/env python3
"""
cek_fungsi.py - Script Pengujian Fungsi Aplikasi UKK Cloud Engineer SMKN 1 Banyumas
Memeriksa: Health Check Frontend ALB, Health Check Backend, S3 Upload Test, dan SNS Publish Test.
"""

import sys
import time
import requests
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Warna terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_aws_session(region="us-east-1"):
    try:
        session = boto3.Session(region_name=region)
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return session, identity["Account"]
    except (NoCredentialsError, ClientError):
        print(f"{YELLOW}[!] AWS Credentials tidak ditemukan di environment.{RESET}")
        print("Silakan masukkan credential AWS Academy Anda:")
        acc_key = input("AWS Access Key ID     : ").strip()
        sec_key = input("AWS Secret Access Key : ").strip()
        tok = input("AWS Session Token     : ").strip()

        session = boto3.Session(
            aws_access_key_id=acc_key,
            aws_secret_access_key=sec_key,
            aws_session_token=tok,
            region_name=region,
        )
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return session, identity["Account"]


def main():
    print(f"\n{BOLD}{CYAN}======================================================{RESET}")
    print(f"{BOLD}{CYAN}   PENGUJIAN FUNGSI APLIKASI — UKK CLOUD ENGINEER     {RESET}")
    print(f"{BOLD}{CYAN}   SMKN 1 Banyumas — Kasus Sistem MBG                 {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")

    region = "us-east-1"
    try:
        session, account_id = get_aws_session(region)
        print(f"{GREEN}[✓] Terhubung ke AWS Account: {account_id}{RESET}\n")
    except Exception as e:
        print(f"{RED}[FATAL] Gagal login ke AWS: {e}{RESET}")
        sys.exit(1)

    elbv2 = session.client("elbv2")
    s3 = session.client("s3")
    sns = session.client("sns")

    score = 0
    max_score = 4

    print(f"{BOLD}Daftar Pengujian Fungsi:{RESET}")
    print("-" * 55)

    # 1. Discover ALB DNS & Test Frontend Health
    alb_dns = None
    try:
        albs = elbv2.describe_load_balancers(Names=["mbg-alb-fe"]).get("LoadBalancers", [])
        if albs:
            alb_dns = albs[0].get("DNSName")
    except Exception:
        pass

    if alb_dns:
        try:
            url = f"http://{alb_dns}/"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                print(f"  {GREEN}✓{RESET} Frontend ALB (HTTP 200 OK di http://{alb_dns}/)")
                score += 1
            else:
                print(f"  {RED}✗{RESET} Frontend ALB (HTTP {resp.status_code} di http://{alb_dns}/)")
        except Exception as e:
            print(f"  {RED}✗{RESET} Frontend ALB Error: {e}")
    else:
        print(f"  {RED}✗{RESET} Frontend ALB (mbg-alb-fe tidak ditemukan)")

    # 2. Health Endpoint
    if alb_dns:
        try:
            url_h = f"http://{alb_dns}/health.php"
            resp_h = requests.get(url_h, timeout=10)
            if resp_h.status_code == 200:
                print(f"  {GREEN}✓{RESET} Health Check Endpoint (/health.php -> 200 OK)")
                score += 1
            else:
                print(f"  {YELLOW}⚠{RESET} Health Check Endpoint (/health.php -> HTTP {resp_h.status_code})")
        except Exception as e:
            print(f"  {RED}✗{RESET} Health Check Endpoint Error: {e}")
    else:
        print(f"  {RED}✗{RESET} Health Check Endpoint (ALB DNS tidak tersedia)")

    # 3. S3 Storage Function Test
    try:
        buckets = s3.list_buckets().get("Buckets", [])
        mbg_buckets = [b["Name"] for b in buckets if b["Name"].startswith("mbg-uploads-")]
        if mbg_buckets:
            bucket_name = mbg_buckets[0]
            test_key = f"aduan/test_grader_{int(time.time())}.txt"
            s3.put_object(Bucket=bucket_name, Key=test_key, Body=b"Test MBG S3")
            s3.delete_object(Bucket=bucket_name, Key=test_key)
            print(f"  {GREEN}✓{RESET} S3 Storage Function (Upload & Delete di {bucket_name})")
            score += 1
        else:
            print(f"  {RED}✗{RESET} S3 Storage Function (Bucket mbg-uploads-* tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} S3 Storage Function Error: {e}")

    # 4. SNS Notification Publish Test
    try:
        topics = sns.list_topics().get("Topics", [])
        target_topic = next((t["TopicArn"] for t in topics if "mbg-sns-notifikasi" in t["TopicArn"]), None)
        if target_topic:
            res = sns.publish(
                TopicArn=target_topic,
                Subject="[MBG Grader] Uji Coba Notifikasi",
                Message="Aduan baru uji coba dari Grader.",
            )
            print(f"  {GREEN}✓{RESET} SNS Notification Function (Publish Message ID: {res.get('MessageId')})")
            score += 1
        else:
            print(f"  {RED}✗{RESET} SNS Notification Function (Topic mbg-sns-notifikasi tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} SNS Notification Function Error: {e}")

    # Summary
    percentage = (score / max_score) * 100
    print("-" * 55)
    print(f"{BOLD}SKOR FUNGSI APLIKASI:{RESET} {score}/{max_score} ({percentage:.1f}%)")
    if percentage >= 75:
        print(f"Status Penilaian     : {GREEN}{BOLD}PASS (LULUS FUNGSI){RESET}")
    else:
        print(f"Status Penilaian     : {RED}{BOLD}FAIL (BELUM LENGKAP){RESET}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
