#!/usr/bin/env python3
"""
cek_infra.py - Script Pemeriksaan Infrastruktur AWS UKK Cloud Engineer SMKN 1 Banyumas
Memeriksa: VPC, 7 Subnet, IGW, NAT GW, Route Tables, 5 Security Groups, RDS MySQL,
S3 Bucket, SNS Topic, EC2 Backend, EFS, Launch Template, Target Group, ALB, dan ASG.
"""

import sys
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

# Warna terminal
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def get_tag(tags, key="Name"):
    if not tags:
        return None
    for t in tags:
        if t.get("Key") == key:
            return t.get("Value")
    return None


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
    print(f"{BOLD}{CYAN}   PEMERIKSAAN INFRASTRUKTUR AWS — UKK CLOUD ENGINEER {RESET}")
    print(f"{BOLD}{CYAN}   SMKN 1 Banyumas — Kasus Sistem MBG                 {RESET}")
    print(f"{BOLD}{CYAN}======================================================{RESET}\n")

    region = "us-east-1"
    try:
        session, account_id = get_aws_session(region)
        print(f"{GREEN}[✓] Terhubung ke AWS Account: {account_id} (Region: {region}){RESET}\n")
    except Exception as e:
        print(f"{RED}[FATAL] Gagal login ke AWS: {e}{RESET}")
        sys.exit(1)

    ec2 = session.client("ec2")
    rds = session.client("rds")
    s3 = session.client("s3")
    sns = session.client("sns")
    efs = session.client("efs")
    elbv2 = session.client("elbv2")
    asg = session.client("autoscaling")

    score = 0
    max_score = 15

    print(f"{BOLD}Daftar Pengecekan Infrastruktur:{RESET}")
    print("-" * 55)

    # 1. VPC
    try:
        vpcs = ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": ["mbg-vpc"]}]).get("Vpcs", [])
        if vpcs and vpcs[0].get("CidrBlock") == "10.20.0.0/16":
            print(f"  {GREEN}✓{RESET} VPC (mbg-vpc - 10.20.0.0/16)")
            score += 1
            vpc_id = vpcs[0]["VpcId"]
        else:
            print(f"  {RED}✗{RESET} VPC (mbg-vpc tidak ditemukan atau CIDR bukan 10.20.0.0/16)")
            vpc_id = None
    except Exception as e:
        print(f"  {RED}✗{RESET} VPC Error: {e}")
        vpc_id = None

    # 2. 7 Subnets
    expected_subnets = [
        ("mbg-subnet-public-alb-1a", "10.20.1.0/24", "us-east-1a"),
        ("mbg-subnet-public-alb-1b", "10.20.2.0/24", "us-east-1b"),
        ("mbg-subnet-private-fe-1a", "10.20.11.0/24", "us-east-1a"),
        ("mbg-subnet-private-fe-1b", "10.20.12.0/24", "us-east-1b"),
        ("mbg-subnet-private-be", "10.20.10.0/24", "us-east-1a"),
        ("mbg-subnet-db-1a", "10.20.20.0/24", "us-east-1a"),
        ("mbg-subnet-db-1b", "10.20.21.0/24", "us-east-1b"),
    ]
    try:
        subnets = ec2.describe_subnets().get("Subnets", [])
        sub_map = {get_tag(s.get("Tags")): s for s in subnets if get_tag(s.get("Tags"))}
        sub_valid = 0
        for name, cidr, az in expected_subnets:
            if name in sub_map and sub_map[name].get("CidrBlock") == cidr and sub_map[name].get("AvailabilityZone") == az:
                sub_valid += 1

        if sub_valid == 7:
            print(f"  {GREEN}✓{RESET} 7 Subnets (Semua nama, CIDR, dan AZ cocok)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} Subnets ({sub_valid}/7 Subnet valid)")
    except Exception as e:
        print(f"  {RED}✗{RESET} Subnets Error: {e}")

    # 3. Internet Gateway
    try:
        igws = ec2.describe_internet_gateways(Filters=[{"Name": "tag:Name", "Values": ["mbg-igw"]}]).get("InternetGateways", [])
        if igws:
            print(f"  {GREEN}✓{RESET} Internet Gateway (mbg-igw attached)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} Internet Gateway (mbg-igw tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} IGW Error: {e}")

    # 4. NAT Gateway
    try:
        nats = ec2.describe_nat_gateways(Filters=[{"Name": "tag:Name", "Values": ["mbg-natgw-1a"]}]).get("NatGateways", [])
        active_nats = [n for n in nats if n.get("State") in ["available", "pending"]]
        if active_nats:
            print(f"  {GREEN}✓{RESET} NAT Gateway (mbg-natgw-1a aktif dengan Elastic IP)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} NAT Gateway (mbg-natgw-1a tidak aktif)")
    except Exception as e:
        print(f"  {RED}✗{RESET} NAT Gateway Error: {e}")

    # 5. Route Tables
    try:
        rts = ec2.describe_route_tables().get("RouteTables", [])
        rt_map = {get_tag(r.get("Tags")): r for r in rts if get_tag(r.get("Tags"))}
        pub_ok = "mbg-rt-public" in rt_map
        priv_ok = "mbg-rt-private" in rt_map
        if pub_ok and priv_ok:
            print(f"  {GREEN}✓{RESET} Route Tables (mbg-rt-public & mbg-rt-private)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} Route Tables (mbg-rt-public: {pub_ok}, mbg-rt-private: {priv_ok})")
    except Exception as e:
        print(f"  {RED}✗{RESET} Route Tables Error: {e}")

    # 6. Security Groups
    expected_sgs = ["mbg-sg-alb", "mbg-sg-fe", "mbg-sg-be", "mbg-sg-rds", "mbg-sg-efs"]
    try:
        sgs = ec2.describe_security_groups().get("SecurityGroups", [])
        sg_names = [sg.get("GroupName") for sg in sgs]
        sg_valid = all(name in sg_names for name in expected_sgs)
        if sg_valid:
            print(f"  {GREEN}✓{RESET} 5 Security Groups (alb, fe, be, rds, efs lengkap)")
            score += 1
        else:
            missing_sg = [n for n in expected_sgs if n not in sg_names]
            print(f"  {RED}✗{RESET} Security Groups (Missing: {missing_sg})")
    except Exception as e:
        print(f"  {RED}✗{RESET} Security Groups Error: {e}")

    # 7. RDS MySQL
    try:
        dbs = rds.describe_db_instances().get("DBInstances", [])
        target_db = next((d for d in dbs if d.get("DBInstanceIdentifier") == "mbg-rds-mysql"), None)
        if target_db and target_db.get("DBInstanceStatus") == "available" and not target_db.get("PubliclyAccessible"):
            print(f"  {GREEN}✓{RESET} RDS MySQL (mbg-rds-mysql available & Private)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} RDS MySQL (mbg-rds-mysql tidak ditemukan / belum available / public)")
    except Exception as e:
        print(f"  {RED}✗{RESET} RDS Error: {e}")

    # 8. S3 Bucket
    try:
        buckets = s3.list_buckets().get("Buckets", [])
        mbg_buckets = [b["Name"] for b in buckets if b["Name"].startswith("mbg-uploads-")]
        if mbg_buckets:
            print(f"  {GREEN}✓{RESET} S3 Bucket ({mbg_buckets[0]})")
            score += 1
        else:
            print(f"  {RED}✗{RESET} S3 Bucket (mbg-uploads-* tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} S3 Error: {e}")

    # 9. SNS Topic
    try:
        topics = sns.list_topics().get("Topics", [])
        target_topic = next((t["TopicArn"] for t in topics if "mbg-sns-notifikasi" in t["TopicArn"]), None)
        if target_topic:
            print(f"  {GREEN}✓{RESET} SNS Topic (mbg-sns-notifikasi)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} SNS Topic (mbg-sns-notifikasi tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} SNS Error: {e}")

    # 10. EFS File System
    try:
        efss = efs.describe_file_systems().get("FileSystems", [])
        target_efs = next((f for f in efss if f.get("Name") == "mbg-efs-fe-session" or get_tag(f.get("Tags")) == "mbg-efs-fe-session"), None)
        if target_efs and target_efs.get("LifeCycleState") == "available":
            print(f"  {GREEN}✓{RESET} EFS File System (mbg-efs-fe-session available)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} EFS (mbg-efs-fe-session tidak ditemukan / belum ready)")
    except Exception as e:
        print(f"  {RED}✗{RESET} EFS Error: {e}")

    # 11. EC2 Back End
    try:
        instances = ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": ["mbg-ec2-be"]}]).get("Reservations", [])
        be_list = [i for r in instances for i in r.get("Instances", []) if i.get("State", {}).get("Name") != "terminated"]
        if be_list and be_list[0].get("State", {}).get("Name") == "running" and not be_list[0].get("PublicIpAddress"):
            print(f"  {GREEN}✓{RESET} EC2 Backend (mbg-ec2-be running di Private Subnet)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} EC2 Backend (mbg-ec2-be tidak ditemukan / bukan running / ada Public IP)")
    except Exception as e:
        print(f"  {RED}✗{RESET} EC2 Backend Error: {e}")

    # 12. Launch Template
    try:
        lts = ec2.describe_launch_templates(LaunchTemplateNames=["mbg-lt-fe"]).get("LaunchTemplates", [])
        if lts:
            print(f"  {GREEN}✓{RESET} Launch Template (mbg-lt-fe)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} Launch Template (mbg-lt-fe tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} Launch Template Error: {e}")

    # 13. Target Group
    try:
        tgs = elbv2.describe_target_groups(Names=["mbg-tg-fe"]).get("TargetGroups", [])
        if tgs:
            print(f"  {GREEN}✓{RESET} Target Group (mbg-tg-fe - HTTP:80)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} Target Group (mbg-tg-fe tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} Target Group Error: {e}")

    # 14. Application Load Balancer
    try:
        albs = elbv2.describe_load_balancers(Names=["mbg-alb-fe"]).get("LoadBalancers", [])
        if albs:
            alb_dns = albs[0].get("DNSName")
            print(f"  {GREEN}✓{RESET} ALB (mbg-alb-fe - DNS: {alb_dns})")
            score += 1
        else:
            print(f"  {RED}✗{RESET} ALB (mbg-alb-fe tidak ditemukan)")
    except Exception as e:
        print(f"  {RED}✗{RESET} ALB Error: {e}")

    # 15. Auto Scaling Group
    try:
        asgs = asg.describe_auto_scaling_groups(AutoScalingGroupNames=["mbg-asg-fe"]).get("AutoScalingGroups", [])
        if asgs and asgs[0].get("MinSize") == 2 and asgs[0].get("MaxSize") == 4:
            print(f"  {GREEN}✓{RESET} Auto Scaling Group (mbg-asg-fe - Min:2, Max:4)")
            score += 1
        else:
            print(f"  {RED}✗{RESET} ASG (mbg-asg-fe tidak ditemukan atau kapasitas tidak sesuai)")
    except Exception as e:
        print(f"  {RED}✗{RESET} ASG Error: {e}")

    # Summary
    percentage = (score / max_score) * 100
    print("-" * 55)
    print(f"{BOLD}SKOR INFRASTRUKTUR:{RESET} {score}/{max_score} ({percentage:.1f}%)")
    if percentage >= 75:
        print(f"Status Penilaian   : {GREEN}{BOLD}PASS (LULUS INFRASTRUKTUR){RESET}")
    else:
        print(f"Status Penilaian   : {RED}{BOLD}FAIL (BELUM LENGKAP){RESET}")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
