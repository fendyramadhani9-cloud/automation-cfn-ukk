# Deployment Guide - UKK Cloud Engineer SMKN 1 Banyumas
**Studi Kasus:** Sistem Pelaporan, Monitoring & Aduan Program MBG (Makan Bergizi Gratis)

File template CloudFormation: [`template.yaml`](file:///d:/Projects/Cloud/AWS/mbg%20-cfn/template.yaml)

---

##  Ringkasan Resource Lengkap (Full Architecture)

Template ini telah mengotomatiskan pembangunan arsitektur secara menyeluruh (End-to-End) sesuai seluruh tabel Bab C dan petunjuk Bab D:

1. **Jaringan (VPC & Subnet - Bab C.2 & C.3)**:
   - VPC: `mbg-vpc` (`10.20.0.0/16`)
   - 2 Subnet Public ALB: `mbg-subnet-public-alb-1a` (`10.20.1.0/24`), `mbg-subnet-public-alb-1b` (`10.20.2.0/24`)
   - 2 Subnet Private FE: `mbg-subnet-private-fe-1a` (`10.20.11.0/24`), `mbg-subnet-private-fe-1b` (`10.20.12.0/24`)
   - 1 Subnet Private BE: `mbg-subnet-private-be` (`10.20.10.0/24`)
   - 2 Subnet DB: `mbg-subnet-db-1a` (`10.20.20.0/24`), `mbg-subnet-db-1b` (`10.20.21.0/24`)
   - Internet Gateway: `mbg-igw`
   - Elastic IP + NAT Gateway: `mbg-natgw-1a` (di `mbg-subnet-public-alb-1a`)
   - Route Table Public (`mbg-rt-public`) & Route Table Private (`mbg-rt-private`)

2. **Security Groups (Bab C.4)**:
   - `mbg-sg-alb` (HTTP: 80)
   - `mbg-sg-fe` (SSH: 22, HTTP: 80)
   - `mbg-sg-be` (SSH: 22, HTTP: 80)
   - `mbg-sg-rds` (MySQL: 3306)
   - `mbg-sg-efs` (NFS: 2049)

3. **Database, Storage & Notifikasi**:
   - **RDS MySQL**: `mbg-rds-mysql` (`db.t3.micro`, user: `admin`, pass: `12345678`, DB: `mbg_db`)
   - **S3 Bucket**: `mbg-uploads-...` dengan Block All Public Access + auto-create prefix `aduan/` dan `laporan/`
   - **SNS Topic**: `mbg-sns-notifikasi` + Email Subscription
   - **EFS File System**: `mbg-efs-fe-session` dengan 2 Mount Target di Subnet Private FE (`mbg-subnet-private-fe-1a` & `mbg-subnet-private-fe-1b`)

4. **EC2 Servers & Production Auto Scaling**:
   - **EC2 Backend (`mbg-ec2-be`)**:
     - Subnet private `mbg-subnet-private-be` (tanpa IP publik).
     - Auto-configure PHP, Apache, Git, Composer, repo `mbg-app-be`, SDK AWS, S3 prefixes, dan `config.php`.
   - **EC2 Frontend Pre-Production / Bastion (`mbg-ec2-fe`)**:
     - Tetap ada di public subnet `mbg-subnet-public-alb-1a` (memiliki Public IP) untuk kebutuhan direct testing / troubleshooting / verifikasi.
   - **Target Group (`mbg-tg-fe`)**:
     - Protocol HTTP:80, health check path `/health.php`.
   - **Application Load Balancer (`mbg-alb-fe`)**:
     - Internet-facing di public subnet `mbg-subnet-public-alb-1a` dan `mbg-subnet-public-alb-1b`.
     - Listener HTTP:80 -> Forward ke `mbg-tg-fe`.
   - **Launch Template (`mbg-lt-fe`)**:
     - AMI AL2023, `t3.micro`, Key `vockey`, `LabInstanceProfile`, `mbg-sg-fe`.
     - User data auto mount EFS ke `/mnt/efs/mbg-session` dan auto-configure `mbg-app-fe`.
   - **Auto Scaling Group (`mbg-asg-fe`)**:
     - Berjalan di 2 Subnet Private FE (`mbg-subnet-private-fe-1a` & `mbg-subnet-private-fe-1b`).
     - Capacity: Min = 2, Desired = 2, Max = 4.
     - Scaling Policy: Target Tracking (Average CPU Utilization 60%).

---

##  Cara Deploy di AWS CloudFormation

1. Buka AWS CloudFormation di Region **us-east-1**.
2. Upload file [`template.yaml`](file:///d:/Projects/Cloud/AWS/mbg%20-cfn/template.yaml).
3. Masukkan parameter (sesuaikan NIS atau email jika ingin diubah).
4. Klik **Create Stack**.
5. Setelah status stack **CREATE_COMPLETE**, buka tab **Outputs** untuk mendapatkan semua ARN, ID, dan DNS Name untuk lembar penilaian (Lampiran G).

---

##  Verifikasi Pengujian (Bab D.9)

1. **Akses Dashboard Publik**: Buka `http://<ALBDNSName>/` di browser Anda (didapatkan dari Outputs `ALBDNSName`).
2. **Login & Upload**: Login sebagai role masyarakat/sppg/bgn dan uji upload foto laporan/aduan.
3. **Session Sharing (EFS)**: Login di satu tab/browser, request berpindah antar instance di balik ALB tanpa logout acak.
4. **Target Group Health**: Cek Target Group `mbg-tg-fe`, pastikan minimal 2 instance berstatus **Healthy**.
