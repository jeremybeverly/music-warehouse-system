# 🎸 Music Warehouse System

Sistem manajemen gudang musik berbasis web yang menangani stok barang, distribusi ke cabang, opname inventaris, dan manajemen pengguna. Dibangun dengan **Flask** dan **MongoDB Atlas**.

---

## 🚀 Fitur Utama

- **Autentikasi** — Login berbasis JWT dengan sesi tersimpan di database
- **Manajemen Barang** — CRUD barang dengan filter brand, kategori, harga, dan stok
- **Invoice & Transaksi** — Tipe `IN` (pembelian), `OUT` (distribusi ke cabang), `SALE` (penjualan langsung)
- **Alur Approval** — Multi-level approval sesuai role (Branch → Warehouse)
- **Opname Inventaris** — Penyesuaian stok fisik dengan sistem pengajuan dan approval
- **Manajemen Pengguna** — CRUD user dengan validasi role dan cabang
- **Dashboard** — Statistik real-time berdasarkan konteks role pengguna

---

## 👤 Role & Akses

| Role | Deskripsi |
|---|---|
| `warehouse_admin` | Akses penuh — approve semua invoice & opname gudang pusat |
| `warehouse_staff` | Buat invoice IN/OUT, ajukan opname gudang |
| `branch_admin` | Kelola cabang sendiri — approve invoice & opname cabang |
| `branch_staff` | Buat invoice SALE/OUT, ajukan opname cabang |

---

## ⚙️ Instalasi Lokal

### 1. Clone Repository

```bash
git clone https://github.com/USERNAME/music-warehouse-system.git
cd music-warehouse-system
```

### 2. Buat Virtual Environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment

Buat file `.env` di root folder (salin dari `.env.example`):

```bash
cp .env.example .env
```

Isi nilai yang sesuai:

```env
MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>.mongodb.net/?appName=<AppName>
MONGO_DATABASE_NAME=music_warehouse
FLASK_SECRET_KEY=ganti_dengan_secret_key_anda
JWT_SECRET_KEY=ganti_dengan_jwt_key_anda
```

> **Catatan:** Dapatkan `MONGODB_URI` dari MongoDB Atlas → Database Access → Connect.

### 5. Seed Data Awal (Opsional)

```bash
.venv/bin/python seed.py
```

Ini akan mengisi database dengan data contoh dan akun default:

| Role | Username | Password |
|---|---|---|
| Super Admin (Warehouse) | `admin` | `12345678` |
| Branch Admin | `kepala_jkt` | `12345678` |
| Branch Staff | `kasir_jkt` | `12345678` |

### 6. Jalankan Aplikasi

```bash
.venv/bin/python app.py
```

Akses di browser: **http://127.0.0.1:5000**

---

## 🗂️ Struktur Proyek

```
music-warehouse-system/
├── app.py                  # Entry point Flask
├── config.py               # Konfigurasi env & helper
├── connection.py           # Koneksi MongoDB
├── session_manager.py      # JWT & session management
├── seed.py                 # Script seed data awal
├── requirements.txt
├── .env.example
├── auth/
│   ├── login.py            # Blueprint autentikasi
│   └── decorators.py       # Role-based access control
├── routes/
│   ├── invoices.py         # Transaksi IN / OUT / SALE
│   ├── items.py            # Manajemen barang
│   ├── opname.py           # Opname & adjustment stok
│   ├── users.py            # Manajemen pengguna
│   ├── branch.py           # Manajemen cabang
│   ├── suppliers.py        # Manajemen supplier
│   ├── brands.py           # Master brand
│   ├── categories.py       # Master kategori
│   └── dashboard.py        # Statistik dashboard
└── templates/              # HTML templates (Jinja2)
```

---

## 📡 API Endpoints

### Auth
| Method | Endpoint | Deskripsi |
|---|---|---|
| `POST` | `/auth/login` | Login, set cookie `token` |
| `GET` | `/auth/logout` | Logout, hapus sesi |

### Items
| Method | Endpoint | Akses |
|---|---|---|
| `GET` | `/api/items/` | Semua role |
| `POST` | `/api/items/` | `warehouse_admin` |
| `PUT` | `/api/items/<id>` | `warehouse_admin` |
| `DELETE` | `/api/items/<id>` | `warehouse_admin` |

### Invoices
| Method | Endpoint | Akses |
|---|---|---|
| `GET` | `/api/invoices/` | Semua role |
| `POST` | `/api/invoices/` | Semua role (tipe terbatas per role) |
| `POST` | `/api/invoices/<id>/approve` | `branch_admin`, `warehouse_admin` |
| `POST` | `/api/invoices/<id>/reject` | `branch_admin`, `warehouse_admin` |
| `DELETE` | `/api/invoices/<id>` | `warehouse_admin` |

### Opname
| Method | Endpoint | Akses |
|---|---|---|
| `GET` | `/api/opname/` | Semua role |
| `POST` | `/api/opname/` | Semua role |
| `GET` | `/api/opname/pending` | `warehouse_admin`, `branch_admin` |
| `POST` | `/api/opname/approve/<id>` | `warehouse_admin`, `branch_admin` |
| `POST` | `/api/opname/reject/<id>` | `warehouse_admin`, `branch_admin` |

---

## 🛠️ Tech Stack

| Layer | Teknologi |
|---|---|
| Backend | Python 3, Flask |
| Database | MongoDB Atlas (via PyMongo) |
| Auth | JWT (PyJWT) + bcrypt |
| Deployment | Docker / Google Cloud Run |
