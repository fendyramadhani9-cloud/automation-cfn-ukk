# UKK Cloud Engineer SMKN 1 Banyumas TA. 2026/2027
**Studi Kasus:** Sistem Pelaporan, Monitoring & Aduan Program MBG (Makan Bergizi Gratis)

Repository ini berisi template otomatisasi **AWS CloudFormation** dan script **Checker (Infrastruktur & Fungsi)** untuk pengujian deployment aplikasi web PHP/MySQL di AWS Academy Learner Lab.

---

## 📁 Struktur File

```text
├── template.yaml       # Template CloudFormation lengkap (VPC, RDS, EFS, S3, SNS, EC2, ASG, ALB)
├── cek_infra.py        # Script pemeriksa infrastruktur AWS otomatis
├── cek_fungsi.py       # Script penguji fungsional web & endpoint ALB
├── requirements.txt    # Library python (boto3, requests)
└── README.md
```

---

## 🚀 1. Cara Deploy Infrastruktur (CloudFormation)

1. Buka AWS CloudFormation Console di Region **`us-east-1`**.
2. Upload file [`template.yaml`](file:///d:/Projects/Cloud/AWS/mbg%20-cfn/template.yaml).
3. Masukkan parameter NIS/Username (default: `15671`), Key Pair `vockey`, lalu klik **Create Stack**.
4. Tunggu sampai stack berstatus **`CREATE_COMPLETE`**.

---

## 🔍 2. Cara Menjalankan Pemeriksaan (Checker)

### Install Dependensi:
```bash
pip install -r requirements.txt
```

### A. Periksa Infrastruktur AWS (`cek_infra.py`):
```bash
python cek_infra.py
```
> Memeriksa VPC, 7 Subnet, IGW, NAT Gateway, Route Tables, 5 Security Groups, RDS MySQL, S3 Bucket, SNS Topic, EFS File System, EC2 Backend, Launch Template, Target Group, ALB, dan Auto Scaling Group.

### B. Periksa Fungsi Aplikasi Web (`cek_fungsi.py`):
```bash
python cek_fungsi.py
```
> Menguji respon HTTP 200 frontend melalui Application Load Balancer (ALB), health endpoint, upload ke S3, dan publish notifikasi email SNS.

---

*(Catatan: Versi engine grading batch Google Spreadsheet tersimpan di branch `v1-detail`)*
