import http from "k6/http";
import { check, sleep } from "k6";

// ============================================================
// KONFIGURASI SKENARIO (PILIH SALAH SATU & UNCOMMENT)
// ============================================================

// 1. SMOKE TEST (Cek Kesehatan Skrip/Server)
// export const options = {
//   vus: 1,
//   duration: "30s",
//   thresholds: { http_req_failed: ["rate==0.00"] }, // Harus 0% error
// };

// 2. LOAD TEST (Beban Normal)
// export const options = {
//   stages: [
//     { duration: "10s", target: 20 }, // Naik pelan ke 20 user
//     { duration: "1m", target: 20 }, // Stabil di 20 user
//     { duration: "10s", target: 0 }, // Turun
//   ],
//   thresholds: { http_req_duration: ["p(95)<500"] }, // 95% request < 500ms
// };

// 3. STRESS TEST (Mencari Titik Hancur)
// export const options = {
//   stages: [
//     { duration: "1m", target: 100 }, // Tekan server sampai 100 user
//     { duration: "2m", target: 100 }, // Tahan beban berat
//     { duration: "1m", target: 200 }, // Tambah lagi ke 200 (Extreme)
//     { duration: "30s", target: 0 }, // Stop
//   ],
// };

// 4. SPIKE TEST (Lonjakan Tiba-tiba / Flash Sale)
export const options = {
  stages: [
    { duration: "10s", target: 100 }, // Lonjakan drastis dalam 10 detik!
    { duration: "30s", target: 100 }, // Tahan sebentar
    { duration: "10s", target: 0 }, // Langsung hilang
  ],
};

// ============================================================
// LOGIKA PENGUJIAN (Endpoint Kapita Project)
// ============================================================

const BASE_URL = "http://127.0.0.1:5000"; // Sesuaikan port

export default function () {
  // A. LOGIN
  const loginRes = http.post(
    `${BASE_URL}/auth/login`,
    JSON.stringify({ username: "admin", password: "12345678" }),
    { headers: { "Content-Type": "application/json" } },
  );

  check(loginRes, { "Login status 200": (r) => r.status === 200 });

  // B. AKSES DATA BARANG (Menggunakan Cookie otomatis dari Login)
  const itemsRes = http.get(`${BASE_URL}/api/items/`);

  check(itemsRes, { "Get Items status 200": (r) => r.status === 200 });

  sleep(1);
}
