## ⚙️ Cara Instalasi (Local)

1.  **Clone Repository**
    ```bash
    git clone [https://github.com/USERNAME/REPO_NAME.git](https://github.com/USERNAME/REPO_NAME.git)
    cd REPO_NAME
    ```

2.  **Buat Virtual Environment**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # Windows: .venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Konfigurasi Environment**
    Buat file `.env` di root folder dan isi sesuai `.env.example`:
    ```env
    MONGODB_URI=mongodb+srv://user:pass@cluster.url...
    FLASK_SECRET_KEY=rahasia_anda_disini
    JWT_SECRET_KEY=rahasia_jwt_disini
    ```

5.  **Jalankan Aplikasi**
    ```bash
    # Optional: Seed data awal (User default, Barang, dll)
    python seed.py

    # Jalankan server
    python app.py
    ```
    Akses di browser: `http://127.0.0.1:5000`
