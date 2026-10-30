"""OpenAPI (/docs) text and examples for POST /api/pole/calculate.

tests/api/test_api_pole.py sends every request example, so each one returns 200.
"""

DESCRIPTION = """
Hitung tiang design standard 3 (Old Lighting Pole): beban angin, tegangan lentur
tiang di setiap elevasi dalam `evaluated_positions_m`, dan cek lentur tiap arm.

**Pilih contoh di dropdown *Examples*** untuk melihat body yang valid.

### Field yang bergantung pada field lain
| Field penentu | Nilai | Field yang wajib / diabaikan |
|---|---|---|
| `poles[].pole_type` | `"Straight"` | `diameter_lower_mm`, `thickness_lower_mm`. Upper diabaikan bila dikirim. |
| `poles[].pole_type` | `"Taper"` | lower dan upper (`diameter_upper_mm`, `thickness_upper_mm`) |
| `direct_objects[].object_type` | `"Omni"` | `side_area_m2` / `fixed_angle_deg` diabaikan bila dikirim |
| `direct_objects[].object_type` | `"Directional"` | `side_area_m2`, `fixed_angle_deg` |
| `arms[].objects[].object_type` | `"Omni"` | `side_area_m2` diabaikan bila dikirim |
| `arms[].objects[].object_type` | `"Directional"` | `side_area_m2` |

### Aturan penting
- `design_standard` saat ini hanya `3`. Design standard 3 tidak menghitung
  seismic, jadi tidak ada field `seismic`.
- Tinggi struktur tidak dikirim: dipakai puncak segmen tertinggi.
- Key wajib **snake_case**. Key yang tidak dikenal ditolak dengan 422.
- `name` harus unik di dalam `poles`, `direct_objects`, `overhead_wires`, `arms`,
  dan di dalam `objects` satu arm. `top_elevation_m` harus unik.
- `evaluated_positions_m` harus unik dan tidak boleh di bawah `base_elevation_m`.

### Response 200
Envelope `{"success": true, "data": {...}}`. Semua nilai sudah dibulatkan engine
(aturan rounding design standard). Key mencantumkan satuan (`_m`, `_n`, `_nm`,
`_n_mm2`, ...). Isi `data`:
- `schema_version`: `"2.0"`. Simpan bersama hasil.
- `summary.status`: `"OK"` atau `"NG"`, dari seluruh `checks` (tiang dan arm).
  `summary.governing`: check dengan `utilization_ratio` terbesar.
- `conditions`: wind speed, air density, wind pressure, gravity, dan `wind_cases`
  yang dihitung (`STRAIGHT` 90°, plus `OBLIQUE` 45° bila `include_oblique_wind`).
- `overhead_wires[]`: satu item per kabel: tension akibat FixLoad dan, per wind
  case, line load serta tension saat angin.
- `arms[]`: satu item per arm: specification, `objects[]` (index 0 = badan arm,
  lalu objek dari yang terjauh), total, dan `checks` (`arm_bending`).
- `evaluated_positions[]`: satu item per elevasi: `section` tiang, total FixLoad
  vertikal, dan `wind_cases[]`. Tiap wind case berisi `load_rows[]` (urutan
  ARM, DIRECT_OBJECT, OVERHEAD_WIRE, POLE dari atas), `totals`, dan `checks`
  (`pole_bending`). Baris ARM tidak punya `projected_area_m2` / `wind_coefficient`
  (`null`); nilainya ada per objek di `arms[].objects[]`.
"""

_CASE_3_POLES = [
    {
        "name": "Pole-2",
        "pole_type": "Straight",
        "material": "STK400",
        "top_elevation_m": 0.1,
        "diameter_lower_mm": 175,
        "thickness_lower_mm": 4,
    },
    {
        "name": "Pole-1",
        "pole_type": "Taper",
        "material": "STK400",
        "top_elevation_m": 10.1,
        "diameter_lower_mm": 175,
        "thickness_lower_mm": 4,
        "diameter_upper_mm": 75,
        "thickness_upper_mm": 4,
    },
]

_STEPPED_POLES = [
    {
        "name": "Pole-1",
        "pole_type": "Straight",
        "material": "STK400",
        "top_elevation_m": 8.15,
        "diameter_lower_mm": 75,
        "thickness_lower_mm": 4.5,
    },
    {
        "name": "Pole-2",
        "pole_type": "Taper",
        "material": "STK400",
        "top_elevation_m": 6.65,
        "diameter_lower_mm": 165.2,
        "thickness_lower_mm": 4.5,
        "diameter_upper_mm": 75,
        "thickness_upper_mm": 4.5,
    },
    {
        "name": "Pole-3",
        "pole_type": "Straight",
        "material": "STK400",
        "top_elevation_m": 1.65,
        "diameter_lower_mm": 165.2,
        "thickness_lower_mm": 4.5,
    },
]

REQUEST_EXAMPLES = {
    "arm_and_overhead_wire": {
        "summary": "Tiang + arm + kabel (Case 3 python_calc)",
        "description": "Straight + Taper, satu arm dengan satu objek Omni, satu overhead wire, cek di dasar tiang.",
        "value": {
            "design_standard": 3,
            "poles": _CASE_3_POLES,
            "overhead_wires": [
                {
                    "name": "OHW-1",
                    "mass_per_length_kg_m": 0.19,
                    "diameter_mm": 11.5,
                    "elevation_m": 6,
                    "span_length_m": 10,
                    "sag_ratio_percent": 3,
                    "base_wind_coefficient": 1.0,
                }
            ],
            "arms": [
                {
                    "name": "Arm-1",
                    "material": "STK400",
                    "diameter_mm": 60.5,
                    "thickness_mm": 3.8,
                    "total_length_m": 0.18,
                    "exposed_length_m": 0.18,
                    "installation_height_m": 10.1,
                    "objects": [
                        {
                            "name": "AO-11",
                            "object_type": "Omni",
                            "front_area_m2": 0.13,
                            "mass_per_unit_kg": 14,
                            "horizontal_load_distance_m": 0.18,
                            "base_wind_coefficient": 1.0,
                            "quantity": 1,
                        }
                    ],
                }
            ],
            "evaluated_positions_m": [0.0],
        },
    },
    "direct_object_oblique": {
        "summary": "Tiang bertingkat + direct object, angin lurus dan miring",
        "description": "Tiga segmen, satu objek Directional, `include_oblique_wind` = true, tiga posisi cek.",
        "value": {
            "design_standard": 3,
            "include_oblique_wind": True,
            "poles": _STEPPED_POLES,
            "direct_objects": [
                {
                    "name": "DO1",
                    "object_type": "Directional",
                    "front_area_m2": 0.049,
                    "side_area_m2": 0.041,
                    "fixed_angle_deg": 0,
                    "mass_per_unit_kg": 5.8,
                    "elevation_m": 8.15,
                    "base_wind_coefficient": 1.0,
                    "quantity": 1,
                }
            ],
            "evaluated_positions_m": [6.65, 1.65, 0.0],
        },
    },
    "pole_only": {
        "summary": "Tiang saja (body minimal)",
        "description": "Field opsional dihilangkan: tanpa objek, kabel, atau arm.",
        "value": {
            "design_standard": 3,
            "poles": [
                {
                    "name": "Pole",
                    "pole_type": "Straight",
                    "material": "SGP",
                    "top_elevation_m": 6.0,
                    "diameter_lower_mm": 114.3,
                    "thickness_lower_mm": 4.5,
                }
            ],
            "evaluated_positions_m": [0.0, 2.0],
        },
    },
}

RESPONSES = {
    200: {"description": "Hasil perhitungan. Struktur `data` dijelaskan di deskripsi endpoint."},
    400: {
        "description": "Body bukan JSON object (JSON rusak, kosong, atau berupa list).",
        "content": {
            "application/json": {
                "example": {"success": False, "message": "Request body harus berupa JSON object"}
            }
        },
    },
    422: {
        "description": (
            "Input tidak valid. `errors[].field` menunjuk field yang salah. Kalau input "
            "lolos schema tetapi ditolak engine (mis. posisi di atas puncak tiang), "
            "hanya `message` yang dikirim."
        ),
        "content": {
            "application/json": {
                "example": {
                    "success": False,
                    "message": "Input tidak valid",
                    "errors": [
                        {
                            "field": "poles.1",
                            "message": "Value error, Taper needs diameter_upper_mm and thickness_upper_mm",
                            "type": "value_error",
                        }
                    ],
                }
            }
        },
    },
}
