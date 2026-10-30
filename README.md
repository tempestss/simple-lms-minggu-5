# Simple LMS

Project Simple LMS untuk praktikum Pemrograman Sisi Server (A11.64707).
Repository ini berisi project Minggu 4 (Django ORM + Core LMS Models) yang dilanjutkan
dengan tugas Minggu 5 (Database Optimization).

Febilah Purtin - A11.2022.14209

## Teknologi

- Python 3.12, Django 5.2
- PostgreSQL 17
- Redis 7 (untuk eksperimen cache)
- Django Debug Toolbar
- Docker Compose

Source code ada di host, sedangkan Django dan dependency berjalan di container `app`.
Semua perintah dijalankan dari root project. Kalau Docker dipasang di WSL, jalankan
perintahnya dari terminal WSL.

## Menjalankan Project

```bash
cp .env.example .env
docker compose up -d --build
docker compose exec app python manage.py migrate
docker compose exec app python manage.py createsuperuser
docker compose exec app python manage.py seed_demo
```

Django Admin ada di http://localhost:8000/admin/. Debug Toolbar muncul di halaman
HTML saat `DEBUG=True`.

## Membuat Dataset

```bash
docker compose exec app python manage.py generate_performance_data
docker compose exec app python manage.py generate_relationship_data
```

Kedua command repeatable, data yang sudah ada akan dilewati sehingga aman dijalankan
berulang. `seed_demo` harus dijalankan lebih dulu karena `generate_performance_data`
membutuhkan minimal satu User dengan role `LECTURER`.

| Data | Jumlah dari generator |
|---|---|
| Course | 10.000 (kode `PERF00000` sampai `PERF09999`) |
| User | 55 (5 dosen, 50 mahasiswa) |
| Enrollment | 1.000 |
| Lesson | 500 |
| Assignment | 200 |
| Submission | 1.000 |

Enrollment, Lesson, Assignment, dan Submission dibuat untuk 100 Course PERF pertama.

## Mengulang Benchmark

N+1 Query (Course + Lecturer dan Course + Lesson):

```bash
docker compose exec app python manage.py benchmark_queries
```

Database index. Index dilepas dulu supaya kondisi sebelum index bisa diukur lagi:

```bash
docker compose exec app python manage.py migrate catalog 0001
docker compose exec app python manage.py benchmark_index

docker compose exec app python manage.py migrate catalog
docker compose exec app python manage.py benchmark_index
```

Angka waktu bisa berbeda di tiap komputer, yang dibandingkan adalah before dan after
pada environment dan dataset yang sama.

## Hasil

| Percobaan | Before | After |
|---|---|---|
| Course + Lecturer (100 Course) | 101 query, 38,78 ms | 1 query, 1,56 ms |
| Course + Lesson (50 Course) | 51 query, 26,38 ms | 2 query, 2,86 ms |
| Course + Lecturer (10.000 Course) | 10.001 query, 4.081,65 ms | 1 query, 130,05 ms |
| Admin Assignment | 105 query | 5 query |
| Index `is_active + title` | Seq Scan, 0,303 ms | Index Scan, 0,013 ms |

Output lengkap ada di [docs/hasil](docs/hasil) dan screenshot ada di
[docs/screenshots](docs/screenshots). Query yang sudah dioptimasi ada di
[catalog/queries.py](catalog/queries.py).

## Test

```bash
docker compose exec app python manage.py test
```
