"""
Configuration and rubric settings for UKK AWS Cloud Engineer Grader.
Based on Soal UKK SMKN 1 Banyumas TA 2026/2027.
"""
from typing import Dict, Any

# AWS Settings
DEFAULT_REGION = "us-east-1"
DEFAULT_PROFILE = None

# Google Sheets Configuration
SPREADSHEET_ID = "1your_google_sheet_id_here"
SHEET_PESERTA = "PESERTA"
SHEET_HASIL = "HASIL"
SHEET_DETAIL = "DETAIL"
CREDENTIALS_FILE = "service_account.json"

# Architecture Expected Resources
EXPECTED_VPC = {
    "name": "mbg-vpc",
    "cidr": "10.20.0.0/16",
}

EXPECTED_SUBNETS = [
    {
        "name": "mbg-subnet-public-alb-1a",
        "cidr": "10.20.1.0/24",
        "az": "us-east-1a",
        "type": "public",
        "map_public_ip": True,
    },
    {
        "name": "mbg-subnet-public-alb-1b",
        "cidr": "10.20.2.0/24",
        "az": "us-east-1b",
        "type": "public",
        "map_public_ip": True,
    },
    {
        "name": "mbg-subnet-private-fe-1a",
        "cidr": "10.20.11.0/24",
        "az": "us-east-1a",
        "type": "private",
        "map_public_ip": False,
    },
    {
        "name": "mbg-subnet-private-fe-1b",
        "cidr": "10.20.12.0/24",
        "az": "us-east-1b",
        "type": "private",
        "map_public_ip": False,
    },
    {
        "name": "mbg-subnet-private-be",
        "cidr": "10.20.10.0/24",
        "az": "us-east-1a",
        "type": "private",
        "map_public_ip": False,
    },
    {
        "name": "mbg-subnet-db-1a",
        "cidr": "10.20.20.0/24",
        "az": "us-east-1a",
        "type": "db",
        "map_public_ip": False,
    },
    {
        "name": "mbg-subnet-db-1b",
        "cidr": "10.20.21.0/24",
        "az": "us-east-1b",
        "type": "db",
        "map_public_ip": False,
    },
]

EXPECTED_IGW = "mbg-igw"
EXPECTED_NAT = {
    "name": "mbg-natgw-1a",
    "subnet": "mbg-subnet-public-alb-1a",
}

EXPECTED_ROUTE_TABLES = {
    "public": {
        "name": "mbg-rt-public",
        "subnets": ["mbg-subnet-public-alb-1a", "mbg-subnet-public-alb-1b"],
        "target": "igw",
    },
    "private": {
        "name": "mbg-rt-private",
        "subnets": [
            "mbg-subnet-private-fe-1a",
            "mbg-subnet-private-fe-1b",
            "mbg-subnet-private-be",
        ],
        "target": "nat",
    },
}

EXPECTED_SECURITY_GROUPS = {
    "mbg-sg-alb": {"ports": [80]},
    "mbg-sg-fe": {"ports": [22, 80]},
    "mbg-sg-be": {"ports": [22, 80]},
    "mbg-sg-rds": {"ports": [3306]},
    "mbg-sg-efs": {"ports": [2049]},
}

EXPECTED_RDS = {
    "identifier": "mbg-rds-mysql",
    "engine": "mysql",
    "db_subnet_group": "mbg-db-subnet-group",
    "publicly_accessible": False,
    "az": "us-east-1a",
    "security_group": "mbg-sg-rds",
    "db_name": "mbg_db",
}

EXPECTED_SNS = {
    "topic_name": "mbg-sns-notifikasi",
}

EXPECTED_EFS = {
    "name": "mbg-efs-fe-session",
    "performance_mode": "generalPurpose",
    "throughput_mode": "bursting",
}

EXPECTED_EC2_BE = {
    "name": "mbg-ec2-be",
    "instance_type": "t3.micro",
    "subnet": "mbg-subnet-private-be",
    "public_ip": False,
    "iam_profile": "LabInstanceProfile",
    "security_group": "mbg-sg-be",
}

EXPECTED_LAUNCH_TEMPLATE = {
    "name": "mbg-lt-fe",
    "instance_type": "t3.micro",
    "key_name": "vockey",
    "security_group": "mbg-sg-fe",
    "iam_profile": "LabInstanceProfile",
}

EXPECTED_ASG = {
    "name": "mbg-asg-fe",
    "min_size": 2,
    "desired_capacity": 2,
    "max_size": 4,
    "launch_template": "mbg-lt-fe",
    "target_group": "mbg-tg-fe",
    "target_cpu": 60.0,
}

EXPECTED_TARGET_GROUP = {
    "name": "mbg-tg-fe",
    "port": 80,
    "protocol": "HTTP",
    "health_check_path": "/health.php",
    "min_healthy_targets": 2,
}

EXPECTED_ALB = {
    "name": "mbg-alb-fe",
    "scheme": "internet-facing",
    "security_group": "mbg-sg-alb",
}

# Required Tables in DB
REQUIRED_DB_TABLES = ["users", "sppg", "laporan", "aduan"]

# Scoring Weights (Configurable)
WEIGHT_INFRASTRUCTURE = 60.0
WEIGHT_FUNCTION = 40.0
PASSING_SCORE = 75.0
