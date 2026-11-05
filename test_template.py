#!/usr/bin/env python3
"""
test_template.py - Validasi Otomatis CloudFormation template.yaml
Memeriksa kesesuaian template.yaml terhadap:
  1. Spesifikasi Soal UKK (Bab C, D, G, H)
  2. Kriteria Automated Grading (grade.py)
  3. Kriteria Pemeriksaan Infrastruktur (cek_infra.py)
"""
import re
import sys
import yaml

# Custom YAML Loader untuk CloudFormation tags
def cfn_constructor(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {tag_suffix: loader.construct_scalar(node)}
    elif isinstance(node, yaml.SequenceNode):
        return {tag_suffix: loader.construct_sequence(node)}
    elif isinstance(node, yaml.MappingNode):
        return {tag_suffix: loader.construct_mapping(node)}
    return {tag_suffix: None}

yaml.add_multi_constructor("!", cfn_constructor, Loader=yaml.SafeLoader)

GREEN = "\033[92m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

passed = 0
failed = 0

def check(title, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  {GREEN}[PASS]{RESET} {title}")
    else:
        failed += 1
        print(f"  {RED}[FAIL]{RESET} {title} -> {detail}")

def get_tag(resource, key="Name"):
    props = resource.get("Properties", {})
    tags = props.get("Tags") or props.get("FileSystemTags") or []
    if isinstance(tags, list):
        for t in tags:
            if isinstance(t, dict) and t.get("Key") == key:
                val = t.get("Value")
                if isinstance(val, dict):
                    return val.get("Sub", str(val))
                return str(val)
    return None

def main():
    print(f"\n{BOLD}======================================================{RESET}")
    print(f"{BOLD}   PENGUJIAN VALIDITAS TEMPLATE CLOUDFORMATION        {RESET}")
    print(f"{BOLD}   Sesuai Soal UKK MBG & Skrip Automated Grading      {RESET}")
    print(f"{BOLD}======================================================{RESET}\n")

    with open("template.yaml", "r", encoding="utf-8") as f:
        tmpl = yaml.safe_load(f)

    res = tmpl.get("Resources", {})
    outputs = tmpl.get("Outputs", {})

    # 1. VPC
    print(f"\n{BOLD}[1] VPC & Internet Gateway{RESET}")
    vpc = res.get("VPC", {})
    check("VPC Type AWS::EC2::VPC", vpc.get("Type") == "AWS::EC2::VPC")
    check("VPC CIDR 10.20.0.0/16", vpc.get("Properties", {}).get("CidrBlock") == "10.20.0.0/16")
    check("VPC Tag Name mbg-vpc", get_tag(vpc) == "mbg-vpc")
    check("VPC EnableDnsHostnames true", vpc.get("Properties", {}).get("EnableDnsHostnames") is True)
    check("VPC EnableDnsSupport true", vpc.get("Properties", {}).get("EnableDnsSupport") is True)

    igw = res.get("InternetGateway", {})
    check("IGW Tag Name mbg-igw", get_tag(igw) == "mbg-igw")
    attach = res.get("VPCGatewayAttachment", {})
    check("IGW Attached ke VPC", attach.get("Properties", {}).get("VpcId") == {"Ref": "VPC"})

    # 2. 7 Subnets
    print(f"\n{BOLD}[2] 7 Subnets (Bab C.2){RESET}")
    expected_subnets = {
        "SubnetPublicAlb1a": ("mbg-subnet-public-alb-1a", "10.20.1.0/24", True),
        "SubnetPublicAlb1b": ("mbg-subnet-public-alb-1b", "10.20.2.0/24", True),
        "SubnetPrivateFe1a": ("mbg-subnet-private-fe-1a", "10.20.11.0/24", False),
        "SubnetPrivateFe1b": ("mbg-subnet-private-fe-1b", "10.20.12.0/24", False),
        "SubnetPrivateBe":   ("mbg-subnet-private-be", "10.20.10.0/24", False),
        "SubnetDb1a":        ("mbg-subnet-db-1a", "10.20.20.0/24", False),
        "SubnetDb1b":        ("mbg-subnet-db-1b", "10.20.21.0/24", False),
    }
    for sid, (name, cidr, pub) in expected_subnets.items():
        s = res.get(sid, {})
        props = s.get("Properties", {})
        check(f"Subnet {name} ({cidr}) ada",
              get_tag(s) == name and props.get("CidrBlock") == cidr and props.get("MapPublicIpOnLaunch") is pub,
              f"Got {get_tag(s)}, {props.get('CidrBlock')}, pub={props.get('MapPublicIpOnLaunch')}")

    # 3. NAT Gateway & Route Tables
    print(f"\n{BOLD}[3] NAT Gateway & Routing (Bab C.3){RESET}")
    nat = res.get("NatGateway", {})
    check("NAT Gateway Tag mbg-natgw-1a", get_tag(nat) == "mbg-natgw-1a")
    check("NAT Gateway di SubnetPublicAlb1a", nat.get("Properties", {}).get("SubnetId") == {"Ref": "SubnetPublicAlb1a"})
    check("NAT Gateway pakai AllocationId EIP", "AllocationId" in nat.get("Properties", {}))

    rt_pub = res.get("RouteTablePublic", {})
    check("Route Table mbg-rt-public ada", get_tag(rt_pub) == "mbg-rt-public")
    r_pub = res.get("PublicRoute", {})
    check("Route 0.0.0.0/0 -> IGW di mbg-rt-public",
          r_pub.get("Properties", {}).get("DestinationCidrBlock") == "0.0.0.0/0" and
          r_pub.get("Properties", {}).get("GatewayId") == {"Ref": "InternetGateway"})

    rt_priv = res.get("RouteTablePrivate", {})
    check("Route Table mbg-rt-private ada", get_tag(rt_priv) == "mbg-rt-private")
    r_priv = res.get("PrivateRoute", {})
    check("Route 0.0.0.0/0 -> NAT di mbg-rt-private",
          r_priv.get("Properties", {}).get("DestinationCidrBlock") == "0.0.0.0/0" and
          r_priv.get("Properties", {}).get("NatGatewayId") == {"Ref": "NatGateway"})

    # Check associations
    assocs = [v for k, v in res.items() if v.get("Type") == "AWS::EC2::SubnetRouteTableAssociation"]
    pub_assocs = [a.get("Properties", {}).get("SubnetId", {}).get("Ref") for a in assocs if a.get("Properties", {}).get("RouteTableId") == {"Ref": "RouteTablePublic"}]
    priv_assocs = [a.get("Properties", {}).get("SubnetId", {}).get("Ref") for a in assocs if a.get("Properties", {}).get("RouteTableId") == {"Ref": "RouteTablePrivate"}]
    check("Public RT diasosiasikan ke SubnetPublicAlb1a & 1b", set(pub_assocs) == {"SubnetPublicAlb1a", "SubnetPublicAlb1b"})
    check("Private RT diasosiasikan ke SubnetPrivateFe1a, 1b & Be", set(priv_assocs) == {"SubnetPrivateFe1a", "SubnetPrivateFe1b", "SubnetPrivateBe"})
    db_assocs = [a for a in assocs if a.get("Properties", {}).get("SubnetId", {}).get("Ref") in {"SubnetDb1a", "SubnetDb1b"}]
    check("DB Subnet tidak memiliki route internet (tidak diasosiasikan ke RT luar)", len(db_assocs) == 0)

    # 4. Security Groups
    print(f"\n{BOLD}[4] 5 Security Groups (Bab C.4){RESET}")
    for sg_id, name in [("SecurityGroupAlb", "mbg-sg-alb"), ("SecurityGroupFe", "mbg-sg-fe"),
                        ("SecurityGroupBe", "mbg-sg-be"), ("SecurityGroupRds", "mbg-sg-rds"),
                        ("SecurityGroupEfs", "mbg-sg-efs")]:
        sg = res.get(sg_id, {})
        check(f"SG {name} ada", sg.get("Properties", {}).get("GroupName") == name)

    # Inbound rules
    sg_alb = res.get("SecurityGroupAlb", {}).get("Properties", {}).get("SecurityGroupIngress", [])
    check("mbg-sg-alb: TCP 80 dari 0.0.0.0/0", any(r.get("FromPort") == 80 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_alb))

    sg_fe = res.get("SecurityGroupFe", {}).get("Properties", {}).get("SecurityGroupIngress", [])
    check("mbg-sg-fe: TCP 22 & TCP 80 dari 0.0.0.0/0",
          any(r.get("FromPort") == 22 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_fe) and
          any(r.get("FromPort") == 80 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_fe))

    sg_be = res.get("SecurityGroupBe", {}).get("Properties", {}).get("SecurityGroupIngress", [])
    check("mbg-sg-be: TCP 22 & TCP 80 dari 0.0.0.0/0",
          any(r.get("FromPort") == 22 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_be) and
          any(r.get("FromPort") == 80 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_be))

    sg_rds = res.get("SecurityGroupRds", {}).get("Properties", {}).get("SecurityGroupIngress", [])
    check("mbg-sg-rds: TCP 3306 dari 0.0.0.0/0", any(r.get("FromPort") == 3306 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_rds))

    sg_efs = res.get("SecurityGroupEfs", {}).get("Properties", {}).get("SecurityGroupIngress", [])
    check("mbg-sg-efs: TCP 2049 dari 0.0.0.0/0", any(r.get("FromPort") == 2049 and r.get("CidrIp") == "0.0.0.0/0" for r in sg_efs))
    check("mbg-sg-efs: TCP 2049 dari mbg-sg-fe (C.8 / D.7 & grade.py warning preventer)",
          any(r.get("FromPort") == 2049 and r.get("SourceSecurityGroupId") == {"Ref": "SecurityGroupFe"} for r in sg_efs))

    # 5. RDS MySQL
    print(f"\n{BOLD}[5] RDS MySQL (Bab C.5){RESET}")
    rds = res.get("RDSInstance", {})
    props = rds.get("Properties", {})
    check("RDS Identifier mbg-rds-mysql", props.get("DBInstanceIdentifier") == "mbg-rds-mysql")
    check("Engine mysql", props.get("Engine") == "mysql")
    check("Free tier class db.t3.micro", props.get("DBInstanceClass") == "db.t3.micro")
    check("Master username admin", props.get("MasterUsername") == {"Ref": "DBUsername"})
    check("DBName mbg_db", props.get("DBName") == {"Ref": "DBName"})
    check("PubliclyAccessible false", props.get("PubliclyAccessible") is False)
    check("MultiAZ false", props.get("MultiAZ") is False)
    check("SecurityGroup mbg-sg-rds", props.get("VPCSecurityGroups") == [{"Ref": "SecurityGroupRds"}])
    check("DB Subnet Group mbg-db-subnet-group", res.get("DBSubnetGroup", {}).get("Properties", {}).get("DBSubnetGroupName") == "mbg-db-subnet-group")

    # 6. S3 Bucket
    print(f"\n{BOLD}[6] S3 Bucket (Bab C.6 & grade.py regex){RESET}")
    s3 = res.get("S3Bucket", {})
    bname = s3.get("Properties", {}).get("BucketName", {}).get("Sub", "")
    # Evaluasi pola regex grade.py: r"mbg-uploads-.+-us-east-1-an"
    mock_rendered = bname.replace("${StudentIdentifier}", "15671").replace("${AWS::AccountId}", "123456789012").replace("${AWS::Region}", "us-east-1")
    regex_ok = re.fullmatch(r"mbg-uploads-.+-us-east-1-an", mock_rendered) is not None
    check(f"Bucket Name ({mock_rendered}) cocok regex grade.py (berakhiran -us-east-1-an)", regex_ok, mock_rendered)
    pab = s3.get("Properties", {}).get("PublicAccessBlockConfiguration", {})
    check("Block all public access 4 opsi aktif", all([pab.get(k) is True for k in ["BlockPublicAcls", "BlockPublicPolicy", "IgnorePublicAcls", "RestrictPublicBuckets"]]))

    # 7. SNS Topic & Subscription
    print(f"\n{BOLD}[7] SNS Topic (Bab C.7){RESET}")
    sns = res.get("SNSTopic", {})
    check("TopicName mbg-sns-notifikasi", sns.get("Properties", {}).get("TopicName") == "mbg-sns-notifikasi")
    sub = res.get("SNSSubscription", {})
    check("Subscription email ke ukkce2627@smkn1bms.sch.id",
          sub.get("Properties", {}).get("Protocol") == "email" and
          sub.get("Properties", {}).get("Endpoint") == {"Ref": "SNSEmailEndpoint"})

    # 8. EFS File System
    print(f"\n{BOLD}[8] EFS File System & Mount Targets (Bab C.8){RESET}")
    efs = res.get("EFSFileSystem", {})
    check("EFS Name mbg-efs-fe-session", get_tag(efs) == "mbg-efs-fe-session")
    check("PerformanceMode generalPurpose", efs.get("Properties", {}).get("PerformanceMode") == "generalPurpose")
    check("ThroughputMode bursting", efs.get("Properties", {}).get("ThroughputMode") == "bursting")
    mt1 = res.get("EFSMountTarget1a", {}).get("Properties", {})
    mt2 = res.get("EFSMountTarget1b", {}).get("Properties", {})
    check("Mount Targets di private FE 1a & 1b dengan mbg-sg-efs",
          mt1.get("SubnetId") == {"Ref": "SubnetPrivateFe1a"} and
          mt2.get("SubnetId") == {"Ref": "SubnetPrivateFe1b"} and
          mt1.get("SecurityGroups") == [{"Ref": "SecurityGroupEfs"}] and
          mt2.get("SecurityGroups") == [{"Ref": "SecurityGroupEfs"}])

    # 9. EC2 Backend
    print(f"\n{BOLD}[9] EC2 Backend (Bab C.9 & D.6){RESET}")
    be = res.get("EC2Backend", {})
    bprops = be.get("Properties", {})
    check("EC2 Backend Tag Name mbg-ec2-be", get_tag(be) == "mbg-ec2-be")
    check("Subnet mbg-subnet-private-be", bprops.get("SubnetId") == {"Ref": "SubnetPrivateBe"})
    check("Instance profile LabInstanceProfile", bprops.get("IamInstanceProfile") == "LabInstanceProfile")
    check("Security Group mbg-sg-be", bprops.get("SecurityGroupIds") == [{"Ref": "SecurityGroupBe"}])
    be_ud = bprops.get("UserData", {}).get("Fn::Base64", {}).get("Sub", "")
    check("UserData BE: clone repo mbg-app-be", "git clone https://github.com/ukkce2627/mbg-app-be" in be_ud)
    check("UserData BE: config.php dibuat", "cat << 'EOF_CONFIG' > /var/www/html/config.php" in be_ud)
    check("UserData BE: buat folder prefix S3 aduan/ dan laporan/", "put-object --bucket ${S3Bucket} --key aduan/" in be_ud and "put-object --bucket ${S3Bucket} --key laporan/" in be_ud)
    check("UserData BE: auto-migration & seeding data awal (seed_users.php)", "seed_users.php" in be_ud)

    # 10. Launch Template Front End
    print(f"\n{BOLD}[10] Launch Template Front End (Bab C.11 & grade.py){RESET}")
    lt = res.get("LaunchTemplateFe", {})
    lt_props = lt.get("Properties", {})
    lt_data = lt_props.get("LaunchTemplateData", {})
    check("LaunchTemplateName mbg-lt-fe", lt_props.get("LaunchTemplateName") == "mbg-lt-fe")
    check("Instance profile LabInstanceProfile", lt_data.get("IamInstanceProfile", {}).get("Name") == "LabInstanceProfile")
    
    # Check NetworkInterfaces: AssociatePublicIpAddress = False (grade.py s08)
    nis = lt_data.get("NetworkInterfaces", [])
    assoc = nis[0].get("AssociatePublicIpAddress") if nis else None
    check("NetworkInterfaces[0] Auto-assign public IP = Disabled (False)", assoc is False, str(assoc))
    groups = nis[0].get("Groups") if nis else []
    check("NetworkInterfaces[0] Security group mbg-sg-fe", groups == [{"Ref": "SecurityGroupFe"}])
    
    # Tag Name mbg-ec2-fe
    tag_specs = lt_data.get("TagSpecifications", [])
    name_tags = [t["Value"] for ts in tag_specs if ts.get("ResourceType") == "instance" for t in ts.get("Tags", []) if t.get("Key") == "Name"]
    check("Tag Name instance mbg-ec2-fe di TagSpecifications", "mbg-ec2-fe" in name_tags)

    fe_ud = lt_data.get("UserData", {}).get("Fn::Base64", {}).get("Sub", "")
    check("UserData FE: mount EFS ke /mnt/efs/mbg-session", "mount -t efs" in fe_ud and "/mnt/efs/mbg-session" in fe_ud)
    check("UserData FE: entri fstab persisten EFS", "/etc/fstab" in fe_ud)
    check("UserData FE: config.php session_save_path & php.ini diarahkan", "session.save_path" in fe_ud)
    check("UserData FE: clone repo mbg-app-fe", "git clone https://github.com/ukkce2627/mbg-app-fe" in fe_ud)

    # 11. Target Group, ALB, ASG & Policy
    print(f"\n{BOLD}[11] Target Group, ALB, ASG & Scaling Policy (Bab C.11){RESET}")
    tg = res.get("TargetGroupFe", {})
    check("Target Group Name mbg-tg-fe", tg.get("Properties", {}).get("Name") == "mbg-tg-fe")
    check("Target Group Protocol HTTP:80", tg.get("Properties", {}).get("Protocol") == "HTTP" and tg.get("Properties", {}).get("Port") == 80)
    check("Health check /health.php dengan matcher 200", tg.get("Properties", {}).get("HealthCheckPath") == "/health.php" and tg.get("Properties", {}).get("Matcher", {}).get("HttpCode") == "200")

    alb = res.get("ApplicationLoadBalancerFe", {})
    check("ALB Name mbg-alb-fe", alb.get("Properties", {}).get("Name") == "mbg-alb-fe")
    check("ALB internet-facing di subnet public 1a & 1b",
          alb.get("Properties", {}).get("Scheme") == "internet-facing" and
          set([s.get("Ref") for s in alb.get("Properties", {}).get("Subnets", [])]) == {"SubnetPublicAlb1a", "SubnetPublicAlb1b"})
    check("ALB Security Group mbg-sg-alb", alb.get("Properties", {}).get("SecurityGroups") == [{"Ref": "SecurityGroupAlb"}])

    asg = res.get("AutoScalingGroupFe", {})
    check("ASG Name mbg-asg-fe", asg.get("Properties", {}).get("AutoScalingGroupName") == "mbg-asg-fe")
    check("ASG Subnet Private FE 1a & 1b", set([s.get("Ref") for s in asg.get("Properties", {}).get("VPCZoneIdentifier", [])]) == {"SubnetPrivateFe1a", "SubnetPrivateFe1b"})
    check("ASG Kapasitas Min:2, Max:4, Desired:2",
          asg.get("Properties", {}).get("MinSize") == "2" and
          asg.get("Properties", {}).get("MaxSize") == "4" and
          asg.get("Properties", {}).get("DesiredCapacity") == "2")
    check("ASG terhubung ke Target Group mbg-tg-fe", asg.get("Properties", {}).get("TargetGroupARNs") == [{"Ref": "TargetGroupFe"}])

    policy = res.get("ScalingPolicyFe", {})
    tt = policy.get("Properties", {}).get("TargetTrackingConfiguration", {})
    check("Scaling Policy Target Tracking CPU 60%",
          policy.get("Properties", {}).get("PolicyType") == "TargetTrackingScaling" and
          tt.get("PredefinedMetricSpecification", {}).get("PredefinedMetricType") == "ASGAverageCPUUtilization" and
          float(tt.get("TargetValue", 0)) == 60.0)

    # 12. Outputs
    print(f"\n{BOLD}[12] Outputs (Lembar Isian Penilaian Bab H){RESET}")
    expected_outputs = ["VPCId", "NatGatewayId", "RDSEndpoint", "S3BucketName", "SNSTopicArn",
                        "EC2BackendPrivateIp", "ALBDNSName", "AutoScalingGroupName", "TargetGroupArn", "EFSFileSystemId"]
    for out in expected_outputs:
        check(f"Output {out} tersedia", out in outputs)

    # Ringkasan
    total = passed + failed
    percent = (passed / total) * 100
    print("\n" + "=" * 55)
    print(f"{BOLD}HASIL PENGUJIAN TEMPLATE:{RESET} {passed}/{total} LULUS ({percent:.1f}%)")
    if failed == 0:
        print(f"Status Pengujian: {GREEN}{BOLD}ALL TESTS PASSED (100% LULUS){RESET}")
        print("Template valid, siap digunakan untuk deploy dan penilaian otomatis!")
    else:
        print(f"Status Pengujian: {RED}{BOLD}{failed} TEST GAGAL{RESET}")
        sys.exit(1)
    print("=" * 55 + "\n")

if __name__ == "__main__":
    main()
