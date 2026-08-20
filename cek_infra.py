"""
Infrastructure Grader (cek_infra.py) for UKK AWS Cloud Engineer.
Performs comprehensive and auditable validation against all requirements in Soal UKK.
"""
from typing import Dict, Any, List, Optional
from botocore.exceptions import ClientError

from utils.validators import get_tag, make_result, compare_equal
from config import (
    EXPECTED_VPC,
    EXPECTED_SUBNETS,
    EXPECTED_IGW,
    EXPECTED_NAT,
    EXPECTED_ROUTE_TABLES,
    EXPECTED_SECURITY_GROUPS,
    EXPECTED_RDS,
    EXPECTED_SNS,
    EXPECTED_EFS,
    EXPECTED_EC2_BE,
    EXPECTED_LAUNCH_TEMPLATE,
    EXPECTED_ASG,
    EXPECTED_TARGET_GROUP,
    EXPECTED_ALB,
)


class InfrastructureChecker:
    def __init__(self, aws_session):
        self.session = aws_session
        self.ec2 = aws_session.get_client("ec2")
        self.rds = aws_session.get_client("rds")
        self.s3 = aws_session.get_client("s3")
        self.sns = aws_session.get_client("sns")
        self.efs = aws_session.get_client("efs")
        self.elbv2 = aws_session.get_client("elbv2")
        self.asg = aws_session.get_client("autoscaling")
        self.context: Dict[str, Any] = {}

    def run_all_checks(self, nis: str = "") -> List[Dict[str, Any]]:
        """Run all infrastructure checks sequentially and return granular evidence list."""
        results: List[Dict[str, Any]] = []

        results.extend(self.check_vpc())
        results.extend(self.check_subnets())
        results.extend(self.check_igw())
        results.extend(self.check_nat_gateway())
        results.extend(self.check_route_tables())
        results.extend(self.check_security_groups())
        results.extend(self.check_rds())
        results.extend(self.check_s3(nis))
        results.extend(self.check_sns())
        results.extend(self.check_efs())
        results.extend(self.check_ec2_backend())
        results.extend(self.check_launch_template())
        results.extend(self.check_target_group())
        results.extend(self.check_alb())
        results.extend(self.check_asg())

        return results

    # =========================================================================
    # 1. VPC Check
    # =========================================================================
    def check_vpc(self) -> List[Dict[str, Any]]:
        results = []
        try:
            vpcs = self.ec2.describe_vpcs(Filters=[{"Name": "tag:Name", "Values": [EXPECTED_VPC["name"]]}]).get("Vpcs", [])
            if not vpcs:
                results.append(make_result(
                    check_id="INF-VPC-001",
                    category="Infrastructure",
                    component="VPC",
                    requirement="VPC mbg-vpc exists",
                    expected=EXPECTED_VPC["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=2.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message=f"VPC with Name tag '{EXPECTED_VPC['name']}' not found",
                ))
                return results

            vpc = vpcs[0]
            self.context["vpc_id"] = vpc["VpcId"]

            # Name Check
            results.append(make_result(
                check_id="INF-VPC-001",
                category="Infrastructure",
                component="VPC Name",
                requirement="VPC Name is mbg-vpc",
                expected=EXPECTED_VPC["name"],
                actual=EXPECTED_VPC["name"],
                score=1.0,
                max_score=1.0,
                status="PASS",
                evidence=f"VPC ID: {vpc['VpcId']}",
            ))

            # CIDR Check
            results.append(compare_equal(
                check_id="INF-VPC-002",
                category="Infrastructure",
                component="VPC CIDR",
                requirement="VPC CIDR is 10.20.0.0/16",
                expected=EXPECTED_VPC["cidr"],
                actual=vpc.get("CidrBlock"),
                max_score=1.0,
                err_code_mismatch="CIDR_MISMATCH",
                err_msg_mismatch=f"VPC CIDR is {vpc.get('CidrBlock')}, expected {EXPECTED_VPC['cidr']}",
            ))

        except ClientError as e:
            results.append(make_result(
                check_id="INF-VPC-ERR",
                category="Infrastructure",
                component="VPC",
                requirement="Describe VPC",
                expected="VPC metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 2. Subnets Check (7 Subnets)
    # =========================================================================
    def check_subnets(self) -> List[Dict[str, Any]]:
        results = []
        try:
            vpc_id = self.context.get("vpc_id")
            subnets_resp = self.ec2.describe_subnets(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]) if vpc_id else self.ec2.describe_subnets()
            all_subnets = subnets_resp.get("Subnets", [])
            subnet_map = {get_tag(s.get("Tags")): s for s in all_subnets if get_tag(s.get("Tags"))}

            self.context["subnets"] = subnet_map

            for idx, exp in enumerate(EXPECTED_SUBNETS, start=1):
                name = exp["name"]
                chk_prefix = f"INF-SUBNET-{idx:03d}"
                if name not in subnet_map:
                    results.append(make_result(
                        check_id=chk_prefix,
                        category="Infrastructure",
                        component=f"Subnet {name}",
                        requirement=f"Subnet {name} exists with CIDR {exp['cidr']} in {exp['az']}",
                        expected=f"{name} ({exp['cidr']}, {exp['az']})",
                        actual="Not Found",
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="RESOURCE_NOT_FOUND",
                        error_message=f"Subnet {name} was not found",
                    ))
                    continue

                sub = subnet_map[name]
                actual_cidr = sub.get("CidrBlock")
                actual_az = sub.get("AvailabilityZone")
                actual_public_ip = sub.get("MapPublicIpOnLaunch", False)

                if actual_cidr == exp["cidr"] and actual_az == exp["az"]:
                    results.append(make_result(
                        check_id=chk_prefix,
                        category="Infrastructure",
                        component=f"Subnet {name}",
                        requirement=f"Subnet {name} configuration",
                        expected=f"{exp['cidr']}, {exp['az']}, PublicIP={exp['map_public_ip']}",
                        actual=f"{actual_cidr}, {actual_az}, PublicIP={actual_public_ip}",
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                        evidence=f"Subnet ID: {sub['SubnetId']}",
                    ))
                else:
                    results.append(make_result(
                        check_id=chk_prefix,
                        category="Infrastructure",
                        component=f"Subnet {name}",
                        requirement=f"Subnet {name} configuration",
                        expected=f"{exp['cidr']}, {exp['az']}",
                        actual=f"{actual_cidr}, {actual_az}",
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="CONFIGURATION_MISMATCH",
                        error_message=f"CIDR or AZ mismatch on {name}",
                    ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-SUBNET-ERR",
                category="Infrastructure",
                component="Subnet",
                requirement="Describe Subnets",
                expected="Subnets metadata",
                actual=str(e),
                score=0.0,
                max_score=7.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 3. Internet Gateway Check
    # =========================================================================
    def check_igw(self) -> List[Dict[str, Any]]:
        results = []
        try:
            igws = self.ec2.describe_internet_gateways(Filters=[{"Name": "tag:Name", "Values": [EXPECTED_IGW]}]).get("InternetGateways", [])
            if not igws:
                results.append(make_result(
                    check_id="INF-IGW-001",
                    category="Infrastructure",
                    component="Internet Gateway",
                    requirement="IGW mbg-igw exists and attached to mbg-vpc",
                    expected=EXPECTED_IGW,
                    actual="Not Found",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="Internet Gateway mbg-igw not found",
                ))
                return results

            igw = igws[0]
            attachments = [att.get("VpcId") for att in igw.get("Attachments", []) if att.get("State") == "available"]
            vpc_id = self.context.get("vpc_id")

            if vpc_id and vpc_id in attachments:
                results.append(make_result(
                    check_id="INF-IGW-001",
                    category="Infrastructure",
                    component="Internet Gateway",
                    requirement="IGW mbg-igw attached to VPC",
                    expected=f"Attached to {vpc_id}",
                    actual=f"Attached to {attachments}",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=f"IGW ID: {igw['InternetGatewayId']}",
                ))
            else:
                results.append(make_result(
                    check_id="INF-IGW-001",
                    category="Infrastructure",
                    component="Internet Gateway",
                    requirement="IGW mbg-igw attached to VPC",
                    expected=f"Attached to {vpc_id}",
                    actual=f"Attached to {attachments}",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message=f"IGW not attached to mbg-vpc",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-IGW-ERR",
                category="Infrastructure",
                component="Internet Gateway",
                requirement="Describe IGW",
                expected="IGW metadata",
                actual=str(e),
                score=0.0,
                max_score=1.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 4. NAT Gateway Check
    # =========================================================================
    def check_nat_gateway(self) -> List[Dict[str, Any]]:
        results = []
        try:
            nats = self.ec2.describe_nat_gateways(Filters=[{"Name": "tag:Name", "Values": [EXPECTED_NAT["name"]]}]).get("NatGateways", [])
            active_nats = [n for n in nats if n.get("State") in ["available", "pending"]]

            if not active_nats:
                results.append(make_result(
                    check_id="INF-NAT-001",
                    category="Infrastructure",
                    component="NAT Gateway",
                    requirement="NAT Gateway mbg-natgw-1a in public subnet",
                    expected=EXPECTED_NAT["name"],
                    actual="Not Found / Deleted",
                    score=0.0,
                    max_score=2.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="NAT Gateway mbg-natgw-1a not found or not active",
                ))
                return results

            nat = active_nats[0]
            nat_subnet_id = nat.get("SubnetId")
            expected_subnet_obj = self.context.get("subnets", {}).get(EXPECTED_NAT["subnet"])
            expected_subnet_id = expected_subnet_obj.get("SubnetId") if expected_subnet_obj else None

            # Subnet Placement Check
            if expected_subnet_id and nat_subnet_id == expected_subnet_id:
                results.append(make_result(
                    check_id="INF-NAT-001",
                    category="Infrastructure",
                    component="NAT Gateway Subnet",
                    requirement="NAT Gateway in mbg-subnet-public-alb-1a",
                    expected=EXPECTED_NAT["subnet"],
                    actual=EXPECTED_NAT["subnet"],
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=f"NAT ID: {nat['NatGatewayId']}, Subnet: {nat_subnet_id}",
                ))
            else:
                results.append(make_result(
                    check_id="INF-NAT-001",
                    category="Infrastructure",
                    component="NAT Gateway Subnet",
                    requirement="NAT Gateway in mbg-subnet-public-alb-1a",
                    expected=EXPECTED_NAT["subnet"],
                    actual=str(nat_subnet_id),
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message="NAT Gateway is not in the expected public subnet",
                ))

            # Elastic IP Check
            has_eip = any(addr.get("AllocationId") for addr in nat.get("NatGatewayAddresses", []))
            if has_eip:
                results.append(make_result(
                    check_id="INF-NAT-002",
                    category="Infrastructure",
                    component="NAT Gateway EIP",
                    requirement="NAT Gateway has Elastic IP",
                    expected="Elastic IP Attached",
                    actual="Elastic IP Attached",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=str(nat.get("NatGatewayAddresses")),
                ))
            else:
                results.append(make_result(
                    check_id="INF-NAT-002",
                    category="Infrastructure",
                    component="NAT Gateway EIP",
                    requirement="NAT Gateway has Elastic IP",
                    expected="Elastic IP Attached",
                    actual="No Elastic IP",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message="NAT Gateway has no Elastic IP associated",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-NAT-ERR",
                category="Infrastructure",
                component="NAT Gateway",
                requirement="Describe NAT Gateways",
                expected="NAT Gateway metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 5. Route Tables Check (Public & Private)
    # =========================================================================
    def check_route_tables(self) -> List[Dict[str, Any]]:
        results = []
        try:
            vpc_id = self.context.get("vpc_id")
            rts = self.ec2.describe_route_tables(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]) if vpc_id else self.ec2.describe_route_tables()
            rt_list = rts.get("RouteTables", [])
            rt_map = {get_tag(r.get("Tags")): r for r in rt_list if get_tag(r.get("Tags"))}

            # Check Public Route Table
            pub_rt = rt_map.get("mbg-rt-public")
            if pub_rt:
                has_igw_route = any(
                    route.get("DestinationCidrBlock") == "0.0.0.0/0" and route.get("GatewayId", "").startswith("igw-")
                    for route in pub_rt.get("Routes", [])
                )
                if has_igw_route:
                    results.append(make_result(
                        check_id="INF-RT-001",
                        category="Infrastructure",
                        component="Public Route Table",
                        requirement="mbg-rt-public has default route 0.0.0.0/0 -> IGW",
                        expected="0.0.0.0/0 -> mbg-igw",
                        actual="0.0.0.0/0 -> IGW found",
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                        evidence=f"Route Table ID: {pub_rt['RouteTableId']}",
                    ))
                else:
                    results.append(make_result(
                        check_id="INF-RT-001",
                        category="Infrastructure",
                        component="Public Route Table",
                        requirement="mbg-rt-public default route",
                        expected="0.0.0.0/0 -> IGW",
                        actual="No IGW route found",
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="ROUTE_TARGET_WRONG",
                        error_message="mbg-rt-public does not route 0.0.0.0/0 to IGW",
                    ))
            else:
                results.append(make_result(
                    check_id="INF-RT-001",
                    category="Infrastructure",
                    component="Public Route Table",
                    requirement="mbg-rt-public exists",
                    expected="mbg-rt-public",
                    actual="Not Found",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="Route table mbg-rt-public not found",
                ))

            # Check Private Route Table
            priv_rt = rt_map.get("mbg-rt-private")
            if priv_rt:
                has_nat_route = any(
                    route.get("DestinationCidrBlock") == "0.0.0.0/0" and route.get("NatGatewayId")
                    for route in priv_rt.get("Routes", [])
                )
                if has_nat_route:
                    results.append(make_result(
                        check_id="INF-RT-002",
                        category="Infrastructure",
                        component="Private Route Table",
                        requirement="mbg-rt-private has default route 0.0.0.0/0 -> NAT GW",
                        expected="0.0.0.0/0 -> NAT GW",
                        actual="0.0.0.0/0 -> NAT GW found",
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                        evidence=f"Route Table ID: {priv_rt['RouteTableId']}",
                    ))
                else:
                    results.append(make_result(
                        check_id="INF-RT-002",
                        category="Infrastructure",
                        component="Private Route Table",
                        requirement="mbg-rt-private default route",
                        expected="0.0.0.0/0 -> NAT GW",
                        actual="No NAT route found",
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="ROUTE_TARGET_WRONG",
                        error_message="mbg-rt-private does not route 0.0.0.0/0 to NAT Gateway",
                    ))
            else:
                results.append(make_result(
                    check_id="INF-RT-002",
                    category="Infrastructure",
                    component="Private Route Table",
                    requirement="mbg-rt-private exists",
                    expected="mbg-rt-private",
                    actual="Not Found",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="Route table mbg-rt-private not found",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-RT-ERR",
                category="Infrastructure",
                component="Route Table",
                requirement="Describe Route Tables",
                expected="Route Table metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 6. Security Groups Check (5 SGs)
    # =========================================================================
    def check_security_groups(self) -> List[Dict[str, Any]]:
        results = []
        try:
            vpc_id = self.context.get("vpc_id")
            sgs_resp = self.ec2.describe_security_groups(Filters=[{"Name": "vpc-id", "Values": [vpc_id]}]) if vpc_id else self.ec2.describe_security_groups()
            sgs = sgs_resp.get("SecurityGroups", [])
            sg_map = {sg.get("GroupName"): sg for sg in sgs}

            for idx, (sg_name, exp_rules) in enumerate(EXPECTED_SECURITY_GROUPS.items(), start=1):
                chk_id = f"INF-SG-{idx:03d}"
                if sg_name not in sg_map:
                    results.append(make_result(
                        check_id=chk_id,
                        category="Infrastructure",
                        component=f"Security Group {sg_name}",
                        requirement=f"{sg_name} exists with inbound ports {exp_rules['ports']}",
                        expected=f"{sg_name} ({exp_rules['ports']})",
                        actual="Not Found",
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="RESOURCE_NOT_FOUND",
                        error_message=f"Security Group {sg_name} not found",
                    ))
                    continue

                sg = sg_map[sg_name]
                inbound_ports = []
                for perm in sg.get("IpPermissions", []):
                    from_p = perm.get("FromPort")
                    to_p = perm.get("ToPort")
                    if from_p is not None:
                        inbound_ports.append(from_p)

                has_all_ports = all(p in inbound_ports for p in exp_rules["ports"])
                if has_all_ports:
                    results.append(make_result(
                        check_id=chk_id,
                        category="Infrastructure",
                        component=f"Security Group {sg_name}",
                        requirement=f"Inbound ports {exp_rules['ports']}",
                        expected=str(exp_rules["ports"]),
                        actual=str(inbound_ports),
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                        evidence=f"SG ID: {sg['GroupId']}",
                    ))
                else:
                    results.append(make_result(
                        check_id=chk_id,
                        category="Infrastructure",
                        component=f"Security Group {sg_name}",
                        requirement=f"Inbound ports {exp_rules['ports']}",
                        expected=str(exp_rules["ports"]),
                        actual=str(inbound_ports),
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="SECURITY_GROUP_RULE_MISSING",
                        error_message=f"Missing required ports in {sg_name}",
                    ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-SG-ERR",
                category="Infrastructure",
                component="Security Groups",
                requirement="Describe Security Groups",
                expected="Security Group metadata",
                actual=str(e),
                score=0.0,
                max_score=5.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 7. RDS MySQL Check
    # =========================================================================
    def check_rds(self) -> List[Dict[str, Any]]:
        results = []
        try:
            dbs = self.rds.describe_db_instances().get("DBInstances", [])
            target_db = next((d for d in dbs if d.get("DBInstanceIdentifier") == EXPECTED_RDS["identifier"]), None)

            if not target_db:
                results.append(make_result(
                    check_id="INF-RDS-001",
                    category="Infrastructure",
                    component="RDS MySQL",
                    requirement=f"RDS instance {EXPECTED_RDS['identifier']} exists",
                    expected=EXPECTED_RDS["identifier"],
                    actual="Not Found",
                    score=0.0,
                    max_score=3.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="RDS MySQL instance not found",
                ))
                return results

            self.context["rds_endpoint"] = target_db.get("Endpoint", {}).get("Address")

            # Status Check
            db_status = target_db.get("DBInstanceStatus")
            results.append(make_result(
                check_id="INF-RDS-001",
                category="Infrastructure",
                component="RDS Status",
                requirement="RDS instance is available",
                expected="available",
                actual=str(db_status),
                score=1.0 if db_status == "available" else 0.0,
                max_score=1.0,
                status="PASS" if db_status == "available" else "FAIL",
                evidence=f"Endpoint: {self.context.get('rds_endpoint')}",
            ))

            # Public Access Check
            public_access = target_db.get("PubliclyAccessible", True)
            if not public_access:
                results.append(make_result(
                    check_id="INF-RDS-002",
                    category="Infrastructure",
                    component="RDS Public Access",
                    requirement="PubliclyAccessible is false",
                    expected="False",
                    actual="False",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                ))
            else:
                results.append(make_result(
                    check_id="INF-RDS-002",
                    category="Infrastructure",
                    component="RDS Public Access",
                    requirement="PubliclyAccessible is false",
                    expected="False",
                    actual="True",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="RDS_PUBLIC_ACCESS",
                    error_message="RDS is publicly accessible (Security Violation)",
                ))

            # DB Subnet Group Check
            subnet_grp = target_db.get("DBSubnetGroup", {}).get("DBSubnetGroupName")
            results.append(compare_equal(
                check_id="INF-RDS-003",
                category="Infrastructure",
                component="RDS Subnet Group",
                requirement="DB Subnet Group is mbg-db-subnet-group",
                expected=EXPECTED_RDS["db_subnet_group"],
                actual=subnet_grp,
                max_score=1.0,
                err_code_mismatch="CONFIGURATION_MISMATCH",
                err_msg_mismatch="Subnet group mismatch",
            ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-RDS-ERR",
                category="Infrastructure",
                component="RDS",
                requirement="Describe RDS",
                expected="RDS metadata",
                actual=str(e),
                score=0.0,
                max_score=3.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 8. S3 Bucket Check
    # =========================================================================
    def check_s3(self, nis: str = "") -> List[Dict[str, Any]]:
        results = []
        try:
            buckets = self.s3.list_buckets().get("Buckets", [])
            target_buckets = [b["Name"] for b in buckets if b["Name"].startswith("mbg-uploads-")]

            if not target_buckets:
                results.append(make_result(
                    check_id="INF-S3-001",
                    category="Infrastructure",
                    component="S3 Bucket",
                    requirement="Bucket mbg-uploads-* exists",
                    expected="mbg-uploads-*",
                    actual="Not Found",
                    score=0.0,
                    max_score=3.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="S3 bucket starting with mbg-uploads- not found",
                ))
                return results

            # Select bucket matching NIS if multiple
            bucket_name = target_buckets[0]
            if nis:
                for b in target_buckets:
                    if nis in b:
                        bucket_name = b
                        break

            self.context["s3_bucket"] = bucket_name

            results.append(make_result(
                check_id="INF-S3-001",
                category="Infrastructure",
                component="S3 Bucket",
                requirement="Bucket mbg-uploads-* exists",
                expected="mbg-uploads-*",
                actual=bucket_name,
                score=1.0,
                max_score=1.0,
                status="PASS",
                evidence=f"Bucket Name: {bucket_name}",
            ))

            # Block Public Access Check
            try:
                pab = self.s3.get_public_access_block(Bucket=bucket_name).get("PublicAccessBlockConfiguration", {})
                all_blocked = all([
                    pab.get("BlockPublicAcls"),
                    pab.get("IgnorePublicAcls"),
                    pab.get("BlockPublicPolicy"),
                    pab.get("RestrictPublicBuckets"),
                ])
                if all_blocked:
                    results.append(make_result(
                        check_id="INF-S3-002",
                        category="Infrastructure",
                        component="S3 Public Access Block",
                        requirement="All Block Public Access enabled",
                        expected="All True",
                        actual="All True",
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                    ))
                else:
                    results.append(make_result(
                        check_id="INF-S3-002",
                        category="Infrastructure",
                        component="S3 Public Access Block",
                        requirement="All Block Public Access enabled",
                        expected="All True",
                        actual=str(pab),
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="S3_PUBLIC_ACCESS_ENABLED",
                        error_message="Block public access is not fully enabled",
                    ))
            except ClientError:
                results.append(make_result(
                    check_id="INF-S3-002",
                    category="Infrastructure",
                    component="S3 Public Access Block",
                    requirement="Block public access configuration",
                    expected="Enabled",
                    actual="Not Configured",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="S3_PUBLIC_ACCESS_ENABLED",
                    error_message="Public Access Block configuration not found",
                ))

            # Folder Prefixes Check (aduan/ and laporan/)
            try:
                objects = self.s3.list_objects_v2(Bucket=bucket_name).get("Contents", [])
                keys = [obj["Key"] for obj in objects]
                has_aduan = any(k.startswith("aduan") for k in keys)
                has_laporan = any(k.startswith("laporan") for k in keys)

                if has_aduan and has_laporan:
                    results.append(make_result(
                        check_id="INF-S3-003",
                        category="Infrastructure",
                        component="S3 Folder Structure",
                        requirement="Prefixes aduan/ and laporan/ exist",
                        expected="aduan/ and laporan/",
                        actual="Both Found",
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                        evidence=f"Keys: {keys[:5]}",
                    ))
                else:
                    results.append(make_result(
                        check_id="INF-S3-003",
                        category="Infrastructure",
                        component="S3 Folder Structure",
                        requirement="Prefixes aduan/ and laporan/ exist",
                        expected="aduan/ and laporan/",
                        actual=f"aduan={has_aduan}, laporan={has_laporan}",
                        score=0.0,
                        max_score=1.0,
                        status="WARN",
                        error_code="CONFIGURATION_MISMATCH",
                        error_message="Folder prefixes aduan/ or laporan/ missing in S3",
                    ))
            except Exception as e:
                results.append(make_result(
                    check_id="INF-S3-003",
                    category="Infrastructure",
                    component="S3 Folders",
                    requirement="List objects",
                    expected="Objects list",
                    actual=str(e),
                    score=0.0,
                    max_score=1.0,
                    status="WARN",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-S3-ERR",
                category="Infrastructure",
                component="S3",
                requirement="Check S3 Bucket",
                expected="Bucket metadata",
                actual=str(e),
                score=0.0,
                max_score=3.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 9. SNS Topic & Subscription Check
    # =========================================================================
    def check_sns(self) -> List[Dict[str, Any]]:
        results = []
        try:
            topics = self.sns.list_topics().get("Topics", [])
            target_topic = next((t["TopicArn"] for t in topics if EXPECTED_SNS["topic_name"] in t["TopicArn"]), None)

            if not target_topic:
                results.append(make_result(
                    check_id="INF-SNS-001",
                    category="Infrastructure",
                    component="SNS Topic",
                    requirement=f"Topic {EXPECTED_SNS['topic_name']} exists",
                    expected=EXPECTED_SNS["topic_name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=2.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="SNS topic mbg-sns-notifikasi not found",
                ))
                return results

            self.context["sns_topic_arn"] = target_topic

            results.append(make_result(
                check_id="INF-SNS-001",
                category="Infrastructure",
                component="SNS Topic",
                requirement="SNS topic exists",
                expected=EXPECTED_SNS["topic_name"],
                actual=target_topic,
                score=1.0,
                max_score=1.0,
                status="PASS",
                evidence=f"ARN: {target_topic}",
            ))

            # Subscription Check
            subs = self.sns.list_subscriptions_by_topic(TopicArn=target_topic).get("Subscriptions", [])
            confirmed_sub = next((s for s in subs if s.get("Protocol") == "email" and s.get("SubscriptionArn") != "PendingConfirmation"), None)

            if confirmed_sub:
                results.append(make_result(
                    check_id="INF-SNS-002",
                    category="Infrastructure",
                    component="SNS Subscription",
                    requirement="Email subscription is Confirmed",
                    expected="Confirmed",
                    actual="Confirmed",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=f"Sub ARN: {confirmed_sub['SubscriptionArn']}, Endpoint: {confirmed_sub['Endpoint']}",
                ))
            else:
                has_pending = any(s.get("SubscriptionArn") == "PendingConfirmation" for s in subs)
                results.append(make_result(
                    check_id="INF-SNS-002",
                    category="Infrastructure",
                    component="SNS Subscription",
                    requirement="Email subscription is Confirmed",
                    expected="Confirmed",
                    actual="PendingConfirmation" if has_pending else "No Email Sub",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="SNS_PENDING_CONFIRMATION" if has_pending else "RESOURCE_NOT_FOUND",
                    error_message="Email subscription not confirmed by recipient yet",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-SNS-ERR",
                category="Infrastructure",
                component="SNS",
                requirement="Describe SNS",
                expected="SNS metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 10. EFS Check
    # =========================================================================
    def check_efs(self) -> List[Dict[str, Any]]:
        results = []
        try:
            filesystems = self.efs.describe_file_systems().get("FileSystems", [])
            target_efs = next((fs for fs in filesystems if fs.get("Name") == EXPECTED_EFS["name"] or get_tag(fs.get("Tags")) == EXPECTED_EFS["name"]), None)

            if not target_efs:
                results.append(make_result(
                    check_id="INF-EFS-001",
                    category="Infrastructure",
                    component="EFS File System",
                    requirement="EFS mbg-efs-fe-session exists",
                    expected=EXPECTED_EFS["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=2.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="EFS File System mbg-efs-fe-session not found",
                ))
                return results

            fs_id = target_efs["FileSystemId"]
            self.context["efs_id"] = fs_id

            # LifeCycle State Check
            results.append(make_result(
                check_id="INF-EFS-001",
                category="Infrastructure",
                component="EFS State",
                requirement="EFS state is available",
                expected="available",
                actual=target_efs.get("LifeCycleState"),
                score=1.0 if target_efs.get("LifeCycleState") == "available" else 0.0,
                max_score=1.0,
                status="PASS" if target_efs.get("LifeCycleState") == "available" else "FAIL",
                evidence=f"EFS ID: {fs_id}",
            ))

            # Mount Targets Check (in 2 private subnets)
            mount_targets = self.efs.describe_mount_targets(FileSystemId=fs_id).get("MountTargets", [])
            available_mts = [mt for mt in mount_targets if mt.get("LifeCycleState") == "available"]

            if len(available_mts) >= 2:
                results.append(make_result(
                    check_id="INF-EFS-002",
                    category="Infrastructure",
                    component="EFS Mount Targets",
                    requirement="At least 2 available Mount Targets",
                    expected=">= 2 Mount Targets",
                    actual=f"{len(available_mts)} Mount Targets",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=str([mt["SubnetId"] for mt in available_mts]),
                ))
            else:
                results.append(make_result(
                    check_id="INF-EFS-002",
                    category="Infrastructure",
                    component="EFS Mount Targets",
                    requirement="At least 2 available Mount Targets in private FE subnets",
                    expected=">= 2 Mount Targets",
                    actual=f"{len(available_mts)} Mount Targets",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="EFS_MOUNT_TARGET_MISSING",
                    error_message=f"Found {len(available_mts)} mount targets, expected 2",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-EFS-ERR",
                category="Infrastructure",
                component="EFS",
                requirement="Describe EFS",
                expected="EFS metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 11. EC2 Back End Check
    # =========================================================================
    def check_ec2_backend(self) -> List[Dict[str, Any]]:
        results = []
        try:
            instances = self.ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": [EXPECTED_EC2_BE["name"]]}]).get("Reservations", [])
            all_be = [inst for res in instances for inst in res.get("Instances", []) if inst.get("State", {}).get("Name") != "terminated"]

            if not all_be:
                results.append(make_result(
                    check_id="INF-EC2-001",
                    category="Infrastructure",
                    component="EC2 Backend",
                    requirement="EC2 mbg-ec2-be exists in private subnet",
                    expected=EXPECTED_EC2_BE["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=3.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="EC2 instance mbg-ec2-be not found",
                ))
                return results

            be_inst = all_be[0]
            self.context["be_private_ip"] = be_inst.get("PrivateIpAddress")

            # State & Type Check
            is_running = be_inst.get("State", {}).get("Name") == "running"
            is_t3_micro = be_inst.get("InstanceType") == EXPECTED_EC2_BE["instance_type"]
            results.append(make_result(
                check_id="INF-EC2-001",
                category="Infrastructure",
                component="EC2 BE State & Type",
                requirement="Instance running & t3.micro",
                expected="running, t3.micro",
                actual=f"{be_inst.get('State', {}).get('Name')}, {be_inst.get('InstanceType')}",
                score=1.0 if (is_running and is_t3_micro) else 0.0,
                max_score=1.0,
                status="PASS" if (is_running and is_t3_micro) else "FAIL",
                evidence=f"Instance ID: {be_inst['InstanceId']}, Private IP: {be_inst.get('PrivateIpAddress')}",
            ))

            # No Public IP Check
            has_public_ip = bool(be_inst.get("PublicIpAddress"))
            if not has_public_ip:
                results.append(make_result(
                    check_id="INF-EC2-002",
                    category="Infrastructure",
                    component="EC2 BE Public IP",
                    requirement="No Public IP assigned",
                    expected="No Public IP",
                    actual="No Public IP",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                ))
            else:
                results.append(make_result(
                    check_id="INF-EC2-002",
                    category="Infrastructure",
                    component="EC2 BE Public IP",
                    requirement="No Public IP assigned (Private subnet rule)",
                    expected="No Public IP",
                    actual=f"Public IP: {be_inst.get('PublicIpAddress')}",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="EC2_PUBLIC_IP",
                    error_message="EC2 Backend has a public IP attached",
                ))

            # IAM Instance Profile Check
            iam_arn = be_inst.get("IamInstanceProfile", {}).get("Arn", "")
            if EXPECTED_EC2_BE["iam_profile"] in iam_arn:
                results.append(make_result(
                    check_id="INF-EC2-003",
                    category="Infrastructure",
                    component="EC2 BE IAM Profile",
                    requirement="LabInstanceProfile attached",
                    expected=EXPECTED_EC2_BE["iam_profile"],
                    actual=EXPECTED_EC2_BE["iam_profile"],
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=iam_arn,
                ))
            else:
                results.append(make_result(
                    check_id="INF-EC2-003",
                    category="Infrastructure",
                    component="EC2 BE IAM Profile",
                    requirement="LabInstanceProfile attached",
                    expected=EXPECTED_EC2_BE["iam_profile"],
                    actual=iam_arn or "None",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message="EC2 Backend does not have LabInstanceProfile",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-EC2-ERR",
                category="Infrastructure",
                component="EC2 Backend",
                requirement="Describe Instances",
                expected="Instance metadata",
                actual=str(e),
                score=0.0,
                max_score=3.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 12. Launch Template Check
    # =========================================================================
    def check_launch_template(self) -> List[Dict[str, Any]]:
        results = []
        try:
            lts = self.ec2.describe_launch_templates(LaunchTemplateNames=[EXPECTED_LAUNCH_TEMPLATE["name"]]).get("LaunchTemplates", [])
            if not lts:
                results.append(make_result(
                    check_id="INF-LT-001",
                    category="Infrastructure",
                    component="Launch Template",
                    requirement=f"Launch Template {EXPECTED_LAUNCH_TEMPLATE['name']} exists",
                    expected=EXPECTED_LAUNCH_TEMPLATE["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=2.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="Launch template mbg-lt-fe not found",
                ))
                return results

            lt = lts[0]
            lt_id = lt["LaunchTemplateId"]
            versions = self.ec2.describe_launch_template_versions(LaunchTemplateId=lt_id).get("LaunchTemplateVersions", [])
            latest_v = versions[-1]
            data = latest_v.get("LaunchTemplateData", {})

            # Instance Type Check
            inst_type = data.get("InstanceType")
            results.append(compare_equal(
                check_id="INF-LT-001",
                category="Infrastructure",
                component="Launch Template Instance Type",
                requirement="Instance type is t3.micro",
                expected=EXPECTED_LAUNCH_TEMPLATE["instance_type"],
                actual=inst_type,
                max_score=1.0,
                err_code_mismatch="CONFIGURATION_MISMATCH",
                err_msg_mismatch="Launch template instance type mismatch",
                evidence=f"LT ID: {lt_id}",
            ))

            # IAM Profile Check
            iam = data.get("IamInstanceProfile", {}).get("Name") or data.get("IamInstanceProfile", {}).get("Arn", "")
            if EXPECTED_LAUNCH_TEMPLATE["iam_profile"] in str(iam):
                results.append(make_result(
                    check_id="INF-LT-002",
                    category="Infrastructure",
                    component="Launch Template IAM",
                    requirement="LabInstanceProfile configured",
                    expected=EXPECTED_LAUNCH_TEMPLATE["iam_profile"],
                    actual=str(iam),
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                ))
            else:
                results.append(make_result(
                    check_id="INF-LT-002",
                    category="Infrastructure",
                    component="Launch Template IAM",
                    requirement="LabInstanceProfile configured",
                    expected=EXPECTED_LAUNCH_TEMPLATE["iam_profile"],
                    actual=str(iam),
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message="Launch template missing LabInstanceProfile",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-LT-ERR",
                category="Infrastructure",
                component="Launch Template",
                requirement="Describe Launch Templates",
                expected="Launch Template metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 13. Target Group Check
    # =========================================================================
    def check_target_group(self) -> List[Dict[str, Any]]:
        results = []
        try:
            tgs = self.elbv2.describe_target_groups(Names=[EXPECTED_TARGET_GROUP["name"]]).get("TargetGroups", [])
            if not tgs:
                results.append(make_result(
                    check_id="INF-TG-001",
                    category="Infrastructure",
                    component="Target Group",
                    requirement="Target Group mbg-tg-fe exists",
                    expected=EXPECTED_TARGET_GROUP["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=2.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="Target Group mbg-tg-fe not found",
                ))
                return results

            tg = tgs[0]
            tg_arn = tg["TargetGroupArn"]
            self.context["tg_arn"] = tg_arn

            # Config Check
            hp = tg.get("HealthCheckPath")
            port = tg.get("Port")
            results.append(make_result(
                check_id="INF-TG-001",
                category="Infrastructure",
                component="Target Group Config",
                requirement="Health Check path /health.php, Port 80",
                expected="/health.php, 80",
                actual=f"{hp}, {port}",
                score=1.0 if (hp == "/health.php" and port == 80) else 0.0,
                max_score=1.0,
                status="PASS" if (hp == "/health.php" and port == 80) else "FAIL",
                evidence=f"TG ARN: {tg_arn}",
            ))

            # Health Target Check
            health_resp = self.elbv2.describe_target_health(TargetGroupArn=tg_arn).get("TargetHealthDescriptions", [])
            healthy_targets = [t for t in health_resp if t.get("TargetHealth", {}).get("State") == "healthy"]

            if len(healthy_targets) >= EXPECTED_TARGET_GROUP["min_healthy_targets"]:
                results.append(make_result(
                    check_id="INF-TG-002",
                    category="Infrastructure",
                    component="Target Group Health",
                    requirement=">= 2 healthy targets in Target Group",
                    expected=">= 2 healthy targets",
                    actual=f"{len(healthy_targets)} healthy targets",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=f"Targets: {[t['Target']['Id'] for t in healthy_targets]}",
                ))
            else:
                results.append(make_result(
                    check_id="INF-TG-002",
                    category="Infrastructure",
                    component="Target Group Health",
                    requirement=">= 2 healthy targets in Target Group",
                    expected=">= 2 healthy targets",
                    actual=f"{len(healthy_targets)} healthy targets (Total registered: {len(health_resp)})",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="TARGET_UNHEALTHY",
                    error_message=f"Only {len(healthy_targets)} of {len(health_resp)} targets are healthy",
                    evidence=str([f"{t['Target']['Id']}:{t['TargetHealth']['State']}" for t in health_resp]),
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-TG-ERR",
                category="Infrastructure",
                component="Target Group",
                requirement="Describe Target Group",
                expected="Target Group metadata",
                actual=str(e),
                score=0.0,
                max_score=2.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 14. Application Load Balancer (ALB) Check
    # =========================================================================
    def check_alb(self) -> List[Dict[str, Any]]:
        results = []
        try:
            albs = self.elbv2.describe_load_balancers(Names=[EXPECTED_ALB["name"]]).get("LoadBalancers", [])
            if not albs:
                results.append(make_result(
                    check_id="INF-ALB-001",
                    category="Infrastructure",
                    component="Application Load Balancer",
                    requirement="ALB mbg-alb-fe exists",
                    expected=EXPECTED_ALB["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=3.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="ALB mbg-alb-fe not found",
                ))
                return results

            alb = albs[0]
            alb_arn = alb["LoadBalancerArn"]
            dns_name = alb.get("DNSName")
            self.context["alb_dns_name"] = dns_name

            # Scheme Check
            results.append(make_result(
                check_id="INF-ALB-001",
                category="Infrastructure",
                component="ALB Scheme",
                requirement="ALB is internet-facing",
                expected=EXPECTED_ALB["scheme"],
                actual=alb.get("Scheme"),
                score=1.0 if alb.get("Scheme") == EXPECTED_ALB["scheme"] else 0.0,
                max_score=1.0,
                status="PASS" if alb.get("Scheme") == EXPECTED_ALB["scheme"] else "FAIL",
                evidence=f"DNS: {dns_name}",
            ))

            # Listener Check
            listeners = self.elbv2.describe_listeners(LoadBalancerArn=alb_arn).get("Listeners", [])
            http_80_listener = next((l for l in listeners if l.get("Port") == 80 and l.get("Protocol") == "HTTP"), None)

            if http_80_listener:
                actions = http_80_listener.get("DefaultActions", [])
                tg_arn = self.context.get("tg_arn")
                forward_to_tg = any(a.get("TargetGroupArn") == tg_arn for a in actions if a.get("Type") == "forward")

                if forward_to_tg:
                    results.append(make_result(
                        check_id="INF-ALB-002",
                        category="Infrastructure",
                        component="ALB Listener",
                        requirement="Listener HTTP:80 forwards to mbg-tg-fe",
                        expected="HTTP:80 -> mbg-tg-fe",
                        actual="HTTP:80 -> mbg-tg-fe",
                        score=1.0,
                        max_score=1.0,
                        status="PASS",
                        evidence=f"Listener ARN: {http_80_listener['ListenerArn']}",
                    ))
                else:
                    results.append(make_result(
                        check_id="INF-ALB-002",
                        category="Infrastructure",
                        component="ALB Listener",
                        requirement="Listener HTTP:80 forwards to mbg-tg-fe",
                        expected="HTTP:80 -> mbg-tg-fe",
                        actual=str(actions),
                        score=0.0,
                        max_score=1.0,
                        status="FAIL",
                        error_code="CONFIGURATION_MISMATCH",
                        error_message="ALB Listener does not forward to target group mbg-tg-fe",
                    ))
            else:
                results.append(make_result(
                    check_id="INF-ALB-002",
                    category="Infrastructure",
                    component="ALB Listener",
                    requirement="Listener HTTP:80 exists",
                    expected="HTTP:80 Listener",
                    actual="None Found",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="HTTP:80 Listener not found on ALB",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-ALB-ERR",
                category="Infrastructure",
                component="ALB",
                requirement="Describe ALB",
                expected="ALB metadata",
                actual=str(e),
                score=0.0,
                max_score=3.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results

    # =========================================================================
    # 15. Auto Scaling Group Check
    # =========================================================================
    def check_asg(self) -> List[Dict[str, Any]]:
        results = []
        try:
            asgs = self.asg.describe_auto_scaling_groups(AutoScalingGroupNames=[EXPECTED_ASG["name"]]).get("AutoScalingGroups", [])
            if not asgs:
                results.append(make_result(
                    check_id="INF-ASG-001",
                    category="Infrastructure",
                    component="Auto Scaling Group",
                    requirement="ASG mbg-asg-fe exists",
                    expected=EXPECTED_ASG["name"],
                    actual="Not Found",
                    score=0.0,
                    max_score=3.0,
                    status="FAIL",
                    error_code="RESOURCE_NOT_FOUND",
                    error_message="Auto Scaling Group mbg-asg-fe not found",
                ))
                return results

            asg_obj = asgs[0]

            # Capacity Check
            min_s = asg_obj.get("MinSize")
            max_s = asg_obj.get("MaxSize")
            des_s = asg_obj.get("DesiredCapacity")
            instances = asg_obj.get("Instances", [])
            in_service = [inst for inst in instances if inst.get("LifecycleState") == "InService"]

            if min_s == EXPECTED_ASG["min_size"] and max_s == EXPECTED_ASG["max_size"] and len(in_service) >= EXPECTED_ASG["min_size"]:
                results.append(make_result(
                    check_id="INF-ASG-001",
                    category="Infrastructure",
                    component="ASG Capacity",
                    requirement="Min=2, Max=4, InService >= 2",
                    expected="Min=2, Max=4, InService >= 2",
                    actual=f"Min={min_s}, Max={max_s}, InService={len(in_service)}",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=f"Instances: {[i['InstanceId'] for i in in_service]}",
                ))
            else:
                results.append(make_result(
                    check_id="INF-ASG-001",
                    category="Infrastructure",
                    component="ASG Capacity",
                    requirement="Min=2, Max=4, InService >= 2",
                    expected="Min=2, Max=4, InService >= 2",
                    actual=f"Min={min_s}, Max={max_s}, InService={len(in_service)}",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="ASG_CAPACITY_MISMATCH",
                    error_message="ASG capacity or in-service count mismatch",
                ))

            # Target Group Attached Check
            tg_arns = asg_obj.get("TargetGroupARNs", [])
            tg_arn = self.context.get("tg_arn")
            if tg_arn and tg_arn in tg_arns:
                results.append(make_result(
                    check_id="INF-ASG-002",
                    category="Infrastructure",
                    component="ASG Target Group",
                    requirement="ASG attached to mbg-tg-fe",
                    expected="Attached to mbg-tg-fe",
                    actual="Attached",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                ))
            else:
                results.append(make_result(
                    check_id="INF-ASG-002",
                    category="Infrastructure",
                    component="ASG Target Group",
                    requirement="ASG attached to mbg-tg-fe",
                    expected="Attached to mbg-tg-fe",
                    actual=str(tg_arns),
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message="ASG is not attached to target group mbg-tg-fe",
                ))

            # Scaling Policy Check
            policies = self.asg.describe_policies(AutoScalingGroupName=EXPECTED_ASG["name"]).get("ScalingPolicies", [])
            target_policy = next((p for p in policies if p.get("PolicyType") == "TargetTrackingScaling"), None)

            if target_policy:
                results.append(make_result(
                    check_id="INF-ASG-003",
                    category="Infrastructure",
                    component="ASG Scaling Policy",
                    requirement="Target tracking policy configured (CPU 60%)",
                    expected="TargetTracking (CPU 60%)",
                    actual="TargetTracking Found",
                    score=1.0,
                    max_score=1.0,
                    status="PASS",
                    evidence=f"Policy ARN: {target_policy.get('PolicyARN')}",
                ))
            else:
                results.append(make_result(
                    check_id="INF-ASG-003",
                    category="Infrastructure",
                    component="ASG Scaling Policy",
                    requirement="Target tracking policy configured (CPU 60%)",
                    expected="TargetTracking (CPU 60%)",
                    actual="None Found",
                    score=0.0,
                    max_score=1.0,
                    status="FAIL",
                    error_code="CONFIGURATION_MISMATCH",
                    error_message="Target tracking scaling policy missing on ASG",
                ))

        except Exception as e:
            results.append(make_result(
                check_id="INF-ASG-ERR",
                category="Infrastructure",
                component="Auto Scaling Group",
                requirement="Describe ASG",
                expected="ASG metadata",
                actual=str(e),
                score=0.0,
                max_score=3.0,
                status="ERROR",
                error_code="AWS_API_ERROR",
                error_message=str(e),
            ))
        return results


if __name__ == "__main__":
    import argparse
    from aws_session import AWSSessionManager

    parser = argparse.ArgumentParser(description="UKK AWS Infrastructure Grader (Standalone)")
    parser.add_argument("--nis", default="15671", help="NIS peserta untuk pencarian S3 bucket")
    parser.add_argument("--profile", default=None, help="AWS Profile name")
    parser.add_argument("--region", default="us-east-1", help="AWS Region (default: us-east-1)")
    args = parser.parse_args()

    print("\n" + "=" * 55)
    print("       UKK AWS INFRASTRUCTURE CHECKER (STANDALONE)")
    print("=" * 55)

    aws = AWSSessionManager(profile_name=args.profile, region_name=args.region)
    auth = aws.initialize()

    if not auth["success"]:
        print(f"\n[!] AWS Auth gagal: {auth['error']}")
        print("[i] Masukkan credential AWS Academy Anda sekarang:")
        acc_key = input("AWS Access Key ID     : ").strip()
        sec_key = input("AWS Secret Access Key : ").strip()
        tok = input("AWS Session Token     : ").strip()

        aws = AWSSessionManager(
            aws_access_key_id=acc_key,
            aws_secret_access_key=sec_key,
            aws_session_token=tok,
            region_name=args.region,
        )
        auth = aws.initialize()
        if not auth["success"]:
            print(f"\n[FATAL] Gagal login ke AWS: {auth['error']}")
            exit(1)

    print(f"\n[✓] AWS Account : {auth['account_id']}")
    print(f"[✓] Region      : {auth['region']}\n")
    print("Memulai pemeriksaan infrastruktur AWS...\n" + "-" * 55)

    checker = InfrastructureChecker(aws)
    results = checker.run_all_checks(nis=args.nis)

    total_score = 0.0
    max_total = 0.0
    pass_cnt = 0
    fail_cnt = 0

    for r in results:
        passed = r["status"] == "PASS"
        icon = "\033[92m✓\033[0m" if passed else "\033[91m✗\033[0m"
        score_str = f"({r['score']}/{r['max_score']})"
        total_score += r["score"]
        max_total += r["max_score"]

        if passed:
            pass_cnt += 1
            print(f"  {icon} {r['component']:<30} {score_str}")
        else:
            fail_cnt += 1
            err_msg = r.get("error_message") or r.get("error_code")
            print(f"  {icon} {r['component']:<30} {score_str} -> \033[93m{err_msg}\033[0m")

    final_pct = (total_score / max_total * 100) if max_total > 0 else 0.0
    print("-" * 55)
    print(f"HASIL INFRASTRUKTUR:")
    print(f"  Total Score : {total_score:.1f} / {max_total:.1f} ({final_pct:.1f}%)")
    print(f"  Status      : \033[92mPASS\033[0m" if final_pct >= 75 else f"  Status      : \033[91mFAIL\033[0m")
    print("=" * 55 + "\n")
