# Koribali Calculation Report

[![Python Version](https://img.shields.io/badge/python-3.12-blue)](https://www.python.org/)
[![Linting: Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Architecture: Feature--Based](https://img.shields.io/badge/Architecture-Feature--Based-green)](#struktur-folder)

Backend service yang dirancang untuk melakukan kalkulasi teknis otomatis dan menghasilkan laporan perhitungan (report) untuk proyek **Koribali**. Proyek ini menerapkan standar engineering yang ketat dengan pemisahan logika kalkulasi dan orkestrasi layanan.

## Fitur Utama

* **Automated Engineering Calculation:** Eksekusi formula teknis secara presisi melalui layer *calculators*.
* **Modular Report Generation:** Pembuatan laporan perhitungan yang sistematis.
* **Clean Architecture:** Pemisahan tanggung jawab yang jelas antara API logic (*routes*), business logic (*services*), dan formula (*calculators*).
* **Standardized Environment:** Manajemen dependensi yang aman dan terisolasi menggunakan Pipenv.

## Tech Stacks

* **Language:** Python 3.12
* **Web Framework:** FastAPI (ASGI) + Uvicorn, dijalankan lewat Gunicorn di production
* **Dependency Management:** Pipenv
* **Testing Framework:** Pytest (Target Coverage >80%)
* **Linter:** Ruff
* **Standards:** Conventional Commits & Gitflow

## Struktur Folder

Kode dibagi menjadi **engine** (rumus, Python murni) dan **fitur** (pintu HTTP). Arah dependensi selalu fitur → engine, tidak pernah sebaliknya.

```text
calculation_service/
├── app/
│   ├── __init__.py            # create_app: error handler + registrasi router
│   ├── engine/                # MESIN: salinan python_calc, TANPA FastAPI/pydantic
│   │   ├── basic_function.py  # = python_calc BasicFunction.py (penampang + massa pipa)
│   │   ├── calculation_service.py  # = application/calculation_service.py
│   │   ├── domain/            # = python_calc domain/: pole, direct object, OHW, arm,
│   │   │                      #   material, kondisi, standards/ (DesignStandard + factory)
│   │   └── calculation/       # = python_calc calculation/: calculator per objek,
│   │                          #   policy (wind, seismic, stress, rounding), workflow per d_st
│   ├── shared/                # dipakai lebih dari satu fitur
│   │   ├── schemas/           # sub-schema input (pydantic): pole, direct object, OHW, arm
│   │   ├── adapters.py        # schema -> objek engine
│   │   ├── errors.py          # 400 body bukan JSON object, 422 input tidak valid
│   │   └── response.py        # amplop {success, data, unique_code}
│   └── <fitur>/               # contoh: pole/
│       ├── routes.py          # APIRouter + endpoint, tanpa logika hitung
│       ├── schemas.py         # request khusus fitur (memakai shared/schemas)
│       ├── services.py        # schema -> adapter -> engine -> mapper
│       └── mappers.py         # hasil engine -> data response (per design standard)
├── tools/                     # alat pengembangan (tidak dipakai runtime)
│   ├── port_engine.sh         # port seluruh engine + test dari python_calc
│   └── port.sh, port_python_calc.sed   # port satu file (hanya import yang ditulis ulang)
└── tests/
    ├── engine/                # test python_calc, diport apa adanya
    └── api/                   # test endpoint lewat FastAPI TestClient
```

Aturan:

- `app/engine/` hanya boleh meng-import stdlib dan `app.engine.*` (dijaga `tests/test_engine_boundary.py`).
- Folder fitur tidak boleh meng-import folder fitur lain. Yang dipakai bersama dipindah ke `app/shared/`.
- Engine adalah salinan python_calc commit `270d23b` (rumus, rounding, policy per
  design standard). `tools/port_engine.sh` menyalin file apa adanya dan hanya menulis
  ulang import (`domain.` → `app.engine.domain.`, dst.). Engine tidak diubah di repo
  ini: perubahan rumus dilakukan di python_calc dulu, lalu engine diport ulang.
- Yang tidak diport: `application/output/` python_calc (penyusun nomor report PDF
  lama). Response API disusun `app/<fitur>/mappers.py`; layout report adalah tugas gateway.
- Engine membulatkan setiap nilai menurut rounding profile design standard
  (`app/engine/calculation/rounding/`). Mapper tidak membulatkan ulang nilai engine; nilai
  yang ia turunkan sendiri (mis. wind load per arm) memakai rounding profile yang sama.

## Instalasi & Persiapan

1.  **Clone Repository:**
    ```bash
    git clone [https://github.com/YantUgli/koribali_calculation_report.git](https://github.com/YantUgli/koribali_calculation_report.git)
    cd koribali_calculation_report
    ```

2.  **Install Dependencies:**
    Pastikan kamu sudah menginstal `pipenv`. Jika belum, jalankan `pip install pipenv`.
    ```bash
    pipenv install
    ```

3.  **Aktifkan Virtual Environment:**
    ```bash
    pipenv shell
    ```

## Cara Menjalankan

Mode development (auto-reload bila `DEBUG=True`):
```bash
python run.py
```

Mode production (sama seperti `Dockerfile`/`Procfile`):
```bash
gunicorn run:app -k uvicorn_worker.UvicornWorker -w 4 -b 0.0.0.0:5000
```

Dokumentasi API otomatis tersedia di `http://localhost:5000/docs` (Swagger UI) dan `/redoc`.

Lewat Docker Compose, service ini dipublish di port host **5001** (`calculation-service-fastapi`) supaya bisa jalan berdampingan dengan versi Flask di port 5000.

## Testing & Quality Gate

Kami menjaga kualitas kode dengan pengujian rutin dan linting otomatis:

* **Menjalankan Unit Test:**
    ```bash
    pipenv run pytest -q
    ```
* **Port ulang engine** (bila python_calc berubah; butuh clone python_calc di `../python_calc_V2`):
    ```bash
    PYTHON_CALC_REF=<commit> tools/port_engine.sh
    ```
* **Linting (Ruff):**
    ```bash
    ruff check .
    ```

## Kontribusi

1.  Lakukan **Fork** pada repository ini.
2.  Buat branch fitur baru (`git checkout -b fitur/NamaFitur`).
3.  Gunakan **Conventional Commits** (contoh: `feat: add calculation for wind pressure`).
4.  Commit perubahan kamu dan lakukan **Push** (`git push origin fitur/NamaFitur`).
5.  Buka **Pull Request**.
