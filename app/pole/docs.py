"""OpenAPI (/docs) text and examples for POST /api/pole/calculate.

Request examples come from tests/parity/fixtures, so every one returns 200.
"""

DESCRIPTION = """
Hitung beban angin (dan seismik, kalau dikirim) pada tiang, lalu cek penampang
di setiap elevasi dalam `evaluated_positions_m`.

**Pilih contoh di dropdown *Examples*** untuk melihat body yang valid.

### Field yang bergantung pada field lain
| Field penentu | Nilai | Field yang wajib |
|---|---|---|
| `wind.design_standard` | `1`, `6` | `structure_height_m`, `atmospheric_category` (1-4), `basic_wind_speed_m_s` |
| `wind.design_standard` | `2`, `3`, `4`, `5` | `structure_height_m` saja |
| `seismic.position` | `"Ground"` | `k_value` |
| `seismic.position` | `"Rooftop"` | `seismic_class` (`"A"`, `"B"`, `"S"`) |
| `poles[].pole_type` | `"Straight"` | `diameter_mm`, `thickness_mm` |
| `poles[].pole_type` | `"Taper"` | `diameter_lower_mm`, `diameter_upper_mm`, `thickness_lower_mm`, `thickness_upper_mm` |
| `direct_objects[].object_type` | `"Omni"` | tanpa `side_area_m2` / `fixed_angle_deg` |
| `direct_objects[].object_type` | `"Directional"` | `side_area_m2`, `fixed_angle_deg` |

### Aturan penting
- Key wajib **snake_case**. Key yang tidak dikenal (termasuk field milik
  varian lain, camelCase, atau `overhead_wires`) ditolak dengan 422.
- `seismic` opsional. Kalau dihilangkan, `data.checks` = `["wind"]` dan hasil
  seismik tidak dihitung.
- `name` harus unik di dalam `poles` dan di dalam `direct_objects`.
- `evaluated_positions_m` harus unik dan tidak boleh di bawah `base_elevation_m`.

### Response 200
Envelope `{"success": true, "data": {...}}`. Isi `data`:
- `schema_version`, `checks`: cek yang dihitung (`["wind"]` atau `["wind", "seismic"]`).
- `design_condition`: kondisi angin/seismik yang dipakai engine.
- `evaluated_positions[]`: satu item per elevasi, berisi `pole`, `direct_object`
  (`null` kalau tidak ada objek), dan `section_check`.
"""

REQUEST_EXAMPLES = {
    "ground_seismic": {
        "summary": "Seismic Ground + wind standard 3",
        "description": "Seismik di tanah memakai `k_value`. Tiga segmen (Straight + Taper) dan satu objek Directional.",
        "value": {
            "wind": {"design_standard": 3, "structure_height_m": 8.15},
            "seismic": {"position": "Ground", "k_value": 0.5},
            "overdesign_factor": 1.0,
            "base_elevation_m": 0.0,
            "poles": [
                {
                    "name": "Pole-1",
                    "pole_type": "Straight",
                    "material": "STK400",
                    "top_elevation_m": 8.15,
                    "diameter_mm": 75,
                    "thickness_mm": 4.5,
                },
                {
                    "name": "Pole-2",
                    "pole_type": "Taper",
                    "material": "STK400",
                    "top_elevation_m": 6.65,
                    "diameter_lower_mm": 165.2,
                    "diameter_upper_mm": 75,
                    "thickness_lower_mm": 4.5,
                    "thickness_upper_mm": 4.5,
                },
                {
                    "name": "Pole-3",
                    "pole_type": "Straight",
                    "material": "STK400",
                    "top_elevation_m": 1.65,
                    "diameter_mm": 165.2,
                    "thickness_mm": 4.5,
                },
            ],
            "direct_objects": [
                {
                    "name": "DO1",
                    "object_type": "Directional",
                    "front_area_m2": 0.049,
                    "side_area_m2": 0.041,
                    "mass_per_unit_kg": 5.8,
                    "elevation_m": 8.15,
                    "base_wind_coefficient": 1.0,
                    "quantity": 1,
                    "fixed_angle_deg": 0,
                }
            ],
            "evaluated_positions_m": [6.65, 1.65, 0.0],
        },
    },
    "rooftop_seismic": {
        "summary": "Seismic Rooftop + wind standard 6",
        "description": "Seismik di atap memakai `seismic_class` (A = 1.5, B = 1.0, S = 2.0). Wind standard 6 wajib `atmospheric_category` dan `basic_wind_speed_m_s`.",
        "value": {
            "wind": {
                "design_standard": 6,
                "structure_height_m": 12.0,
                "atmospheric_category": 3,
                "basic_wind_speed_m_s": 34,
            },
            "seismic": {"position": "Rooftop", "seismic_class": "S"},
            "overdesign_factor": 1.2,
            "base_elevation_m": 0.0,
            "poles": [
                {
                    "name": "Lower",
                    "pole_type": "Taper",
                    "material": "STK490",
                    "top_elevation_m": 7.0,
                    "diameter_lower_mm": 216.3,
                    "diameter_upper_mm": 139.8,
                    "thickness_lower_mm": 6,
                    "thickness_upper_mm": 4.5,
                },
                {
                    "name": "Upper",
                    "pole_type": "Straight",
                    "material": "STK400",
                    "top_elevation_m": 12.0,
                    "diameter_mm": 139.8,
                    "thickness_mm": 4.5,
                },
            ],
            "direct_objects": [
                {
                    "name": "Lamp",
                    "object_type": "Omni",
                    "front_area_m2": 0.3,
                    "mass_per_unit_kg": 20,
                    "elevation_m": 12.0,
                    "base_wind_coefficient": 1.0,
                    "quantity": 2,
                },
                {
                    "name": "Sign",
                    "object_type": "Directional",
                    "front_area_m2": 0.5,
                    "side_area_m2": 0.1,
                    "mass_per_unit_kg": 15,
                    "elevation_m": 7.0,
                    "base_wind_coefficient": 1.2,
                    "quantity": 1,
                    "fixed_angle_deg": 45,
                },
            ],
            "evaluated_positions_m": [7.0, 3.5, 0.0],
        },
    },
    "wind_only": {
        "summary": "Tanpa seismic (wind standard 2, tiang saja)",
        "description": "Body minimal: `seismic`, `direct_objects`, dan `overdesign_factor` dihilangkan.",
        "value": {
            "wind": {"design_standard": 2, "structure_height_m": 6.0},
            "base_elevation_m": 0.5,
            "poles": [
                {
                    "name": "Pole",
                    "pole_type": "Straight",
                    "material": "SGP",
                    "top_elevation_m": 6.0,
                    "diameter_mm": 114.3,
                    "thickness_mm": 4.5,
                }
            ],
            "evaluated_positions_m": [0.5, 2.0],
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
            "Input tidak valid. `errors[].field` menunjuk field yang salah; segmen "
            "seperti `Rooftop` atau `Straight` adalah varian yang dipilih. Kalau input "
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
                            "field": "seismic.Rooftop.seismic_class",
                            "message": "Field required",
                            "type": "missing",
                        }
                    ],
                }
            }
        },
    },
}
