# Ujian Semester Antara: REST API Terdistribusi Sederhana

Implementasi sesuai lima bagian soal: Flask, dua instance lokal, NGINX
round-robin, satu database SQLite bersama, dan uji failover. Tidak memakai
message broker. Seluruh aplikasi hanya mendengarkan alamat loopback.

## Berkas utama

- `server.py`: aplikasi yang sama untuk Server A dan B.
- `nginx.conf`: port masuk 8080, upstream 5001 dan 5002.
- `schema.sql`, `init_db.py`, `data/shared.db`: skema, inisialisasi, dan database.
- `uji.py`: pemeriksaan 10 request bergantian, data bersama, dan failover.
- `demo_otomatis.py`: reproduksi opsional seluruh skenario dan penghentian A.
- `bukti/`: keluaran asli pengujian, screenshot penampil log, dan log NGINX.
- `Laporan_REST_API_Terdistribusi.pdf`: laporan delapan halaman.

## 1. Persiapan (Ubuntu / WSL Ubuntu di Windows)

Buka terminal di folder hasil ekstraksi. Untuk Windows gunakan WSL Ubuntu;
jalankan SEMUA terminal berikut di distribusi WSL dan folder yang sama.
Tidak perlu Oracle Cloud atau Docker.

```bash
sudo apt update
sudo apt install -y python3 python3-venv nginx
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p logs data bukti
python init_db.py
```

`init_db.py` tidak menghapus data lama. Database yang disertakan berisi dua
baris bukti pengujian. Setiap uji shared menambah baris dengan nama unik.

## 2. Jalankan dua instance bersamaan

Terminal A (biarkan tetap berjalan):

```bash
source .venv/bin/activate
python server.py --id A --port 5001
```

Terminal B (folder yang sama, biarkan berjalan):

```bash
source .venv/bin/activate
python server.py --id B --port 5002
```

Kedua proses membuka path database yang sama, dihitung dari lokasi server.py,
bukan dari direktori terminal. Jangan menyalin A dan B ke dua folder terpisah.

## 3. Jalankan NGINX dengan konfigurasi proyek

Terminal C, tetap di folder proyek. Tidak mengubah /etc/nginx/nginx.conf.

```bash
nginx -p "$PWD/" -c nginx.conf -t
nginx -p "$PWD/" -c nginx.conf -g 'daemon off;'
```

Jika `nginx` tidak ditemukan, gunakan `/usr/sbin/nginx` pada perintah tersebut.
Port 5001, 5002, dan 8080 harus bebas sebelum memulai. Layanan NGINX bawaan
yang menggunakan port 80 tidak diperlukan oleh proyek ini.

## 4. Uji distribusi: tepat 10 request melalui NGINX

Terminal D:

```bash
source .venv/bin/activate
python uji.py round-robin
```

Hasil lulus: HTTP 200 sebanyak 10, A=5, B=5, setiap respons berurutan berganti
server. A boleh menjadi respons pertama, atau B jika sebelumnya sudah ada
request. Jangan membuka browser/menjalankan trafik lain ke 8080 saat tes ini,
agar urutan pengamatan tidak disela request lain (misalnya favicon).

## 5. Buktikan data bersama

```bash
python uji.py shared
```

Skrip POST langsung ke A:5001, lalu GET langsung ke B:5002. Identitas layanan,
ID data, isi, pembuat A, dan waktu pembuatan harus cocok. Port langsung sengaja
dipakai agar diketahui pasti server mana yang menulis dan membaca. Pengujian
distribusi dan failover tetap melewati NGINX:8080.

Contoh manual:

```bash
curl -i -X POST http://127.0.0.1:5001/api/data \
  -H 'Content-Type: application/json' -d '{"name":"Data dari Server A"}'
curl -i http://127.0.0.1:5002/api/data
```

## 6. Failover: matikan Server A secara manual

1. Kembali ke Terminal A dan tekan **Ctrl+C**. Jangan hentikan B atau NGINX.
2. Di Terminal D, jalankan:

```bash
python uji.py failover
```

Skrip terlebih dahulu memastikan koneksi langsung ke A gagal. Kemudian ia
mengirim 10 request lewat NGINX. Hasil lulus: A=0, B=10, semuanya HTTP 200.
Header upstream pada request pertama dapat berisi A lalu B karena retry.
NGINX menggunakan pemeriksaan pasif, bukan polling aktif `/health`.
`max_fails=1` menandai upstream gagal; `fail_timeout=30s` menunda pemilihannya.
Setelah interval itu NGINX dapat mencoba A lagi; selama A tetap mati, request
GET dapat dicoba ulang ke B. Pembuktian laporan adalah 10 request pada satu
rangkaian pengujian, bukan jaminan seluruh jenis kegagalan.

Untuk kembali normal, jalankan ulang perintah Server A dan tunggu setidaknya
30 detik sebelum pengujian distribusi. Untuk menghentikan demo, Ctrl+C pada
Terminal A/B/C; NGINX juga dapat dihentikan dari folder proyek dengan:

```bash
nginx -p "$PWD/" -c nginx.conf -s quit
```

## Reproduksi otomatis (opsional)

Setelah semua proses manual dihentikan:

```bash
python demo_otomatis.py
```

Skrip ini menyalakan proses miliknya sendiri, menjalankan uji, mengirim SIGTERM
khusus ke PID A, menjalankan failover, lalu membersihkan proses. Berbeda dari
langkah penilaian manual di atas, penghentian pada mode ini dilakukan skrip.
Jika perlu: `NGINX_BIN=/usr/sbin/nginx python demo_otomatis.py`.

## Bukti pengujian yang disertakan

Pengujian dilakukan di lingkungan Linux eksekusi, bukan di laptop pengguna.
Versi teruji: Python 3.12, Flask 3.1.3, NGINX 1.28.0, SQLite bawaan Python.
Waktu detail tersimpan dalam log UTC (WITA = UTC+8).
NGINX 1.28.0 dikompilasi lokal karena tidak tersedia sebagai program terpasang.
Dalam sandbox dipakai tambahan runtime `user root; master_process off;`
untuk model proses yang kompatibel. Tambahan tersebut tidak tertulis dalam
nginx.conf dan tidak diperlukan pada komputer biasa. Algoritme, upstream,
port, timeout, dan endpoint yang diuji memakai nginx.conf yang disertakan.

Screenshot adalah tangkapan layar browser yang menampilkan berkas log asli,
bukan foto terminal pada laptop pengguna. Berkas `.txt` dan log upstream asli
disertakan agar angka dan hasil dapat diperiksa ulang. Jangan mengaku telah
menjalankan di laptop sendiri sebelum mengikuti langkah di atas.

## Batasan desain

- Ketersediaan dibuktikan pada kegagalan satu proses aplikasi. Komputer,
  NGINX, dan database bersama masih menjadi titik kegagalan tunggal.
- SQLite WAL cocok untuk dua proses pada host yang sama; tidak digunakan
  sebagai database lintas mesin melalui network filesystem.
- Flask development server digunakan untuk praktikum lokal. Belum ada TLS,
  login, backup terjadwal, atau benchmark kapasitas produksi.
- Retry POST setelah terkirim dapat menimbulkan ambiguitas/duplikasi; opsi
  `non_idempotent` sengaja tidak diaktifkan. Uji failover menggunakan GET.

## Referensi

- NGINX. (n.d.). Using nginx as HTTP load balancer.
  https://nginx.org/en/docs/http/load_balancing.html
- NGINX. (n.d.). Module ngx_http_proxy_module.
  https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_next_upstream
- SQLite. (n.d.). Write-ahead logging. https://www.sqlite.org/wal.html
