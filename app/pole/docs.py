"""OpenAPI (/docs) text and examples for POST /api/pole/calculate (design standard 3 and 7).

tests/api/test_api_pole.py sends every request example, so each one returns 200.
"""

DESCRIPTION = """
Hitung tiang: beban angin (dan seismic untuk New JIL), tegangan tiang di setiap
elevasi dalam `evaluated_positions_m`, dan cek tiap arm. Design standard yang
dibuka:

| `design_standard` | Nama | Wind case | Cek tiang per wind case | Cek arm |
|---|---|---|---|---|
| `3` | Old Lighting Pole (Old JIL) | `STRAIGHT` (+ `OBLIQUE` bila `include_oblique_wind`) | `pole_bending` | `arm_bending` |
| `7` | New JIL | 8 arah: `N`, `S`, `E`, `W`, `NE`, `SW`, `NW`, `SE` | `pole_fix_load_bending`, `pole_wind_bending`, `pole_wind_torsion`, `pole_wind_combined`, `pole_seismic_bending`, `pole_seismic_torsion`, `pole_seismic_combined` | `arm_fix_load_bending`, `arm_wind_bending`, `arm_seismic_bending` |

**Pilih contoh di dropdown *Examples*** untuk melihat body yang valid.

### Field yang bergantung pada field lain
| Field penentu | Nilai | Field yang wajib / diabaikan |
|---|---|---|
| `design_standard` | `3` | `include_oblique_wind` boleh dikirim. Field seismic ditolak. |
| `design_standard` | `7` | `horizontal_acceleration_m_s2` (EQa) dan `response_ratio` (EQr) opsional, default 4.71 dan 1.0. `include_oblique_wind` ditolak. |
| `poles[].pole_type` | `"Straight"` | `diameter_lower_mm`, `thickness_lower_mm`. Upper diabaikan bila dikirim. |
| `poles[].pole_type` | `"Taper"` | lower dan upper (`diameter_upper_mm`, `thickness_upper_mm`) |
| `direct_objects[].object_type` | `"Omni"` | `side_area_m2` / `fixed_angle_deg` diabaikan bila dikirim |
| `direct_objects[].object_type` | `"Directional"` | `side_area_m2`, `fixed_angle_deg` |
| `arms[].objects[].object_type` | `"Omni"` | `side_area_m2` opsional: beban angin tetap dari `front_area_m2`, tetapi side area dipakai torque arm di design standard 7 |
| `arms[].objects[].object_type` | `"Directional"` | `side_area_m2` |

### Aturan penting
- `wind_speed_m_s` dan `air_density_kg_m3` wajib. Calculation Service tidak
  memegang default: kirim default master design standard, atau nilai yang
  diubah user.
- Tinggi struktur tidak dikirim: dipakai puncak segmen tertinggi.
- Key wajib **snake_case**. Key yang tidak dikenal ditolak dengan 422.
- `name` harus unik di dalam `poles`, `direct_objects`, `overhead_wires`, `arms`,
  dan di dalam `objects` satu arm. `top_elevation_m` harus unik.
- `evaluated_positions_m` harus unik dan tidak boleh di bawah `base_elevation_m`.

### Response 200
Envelope `{"success": true, "data": {...}}`. Semua nilai sudah dibulatkan engine
(aturan rounding design standard). Key mencantumkan satuan (`_m`, `_n`, `_nm`,
`_n_mm2`, ...). Isi `data` (bentuknya sama untuk kedua design standard):
- `schema_version`: `"2.2"`. Simpan bersama hasil.
- `summary.status`: `"OK"` atau `"NG"`, dari seluruh `checks` (tiang dan arm).
  `summary.governing`: check dengan `utilization_ratio` terbesar.
- `conditions`: wind speed, air density, wind pressure, gravity (d_st 7: 9.81),
  `wind_cases` yang dihitung, dan `seismic` (d_st 3: `null`; d_st 7: EQa dan EQr
  yang dipakai, termasuk default bila tidak dikirim).
- `overhead_wires[]`: satu item per kabel: tension akibat FixLoad dan, per wind
  case, line load serta tension saat angin. d_st 7 menambah `seismic_load_n` dan
  `seismic_tension_n`.
- `arms[]`: satu item per arm: `specification` (termasuk `unit_weight_kg_m`),
  `objects[]` (index 0 = badan arm, lalu objek dari yang terjauh), total, dan
  `checks`. d_st 7 menambah side wind load dan seismic per objek dan di total.
- `pole_sections[]`: satu item per step pole, urut seperti `poles`: section area,
  moment of inertia, radius of gyration, dan `unit_weight_kg_m`, dihitung di
  diameter dan tebal lower. Ada untuk setiap step pole, termasuk yang tidak
  punya posisi cek.
- `evaluated_positions[]`: satu item per elevasi: `section` tiang (diameter,
  tebal, dan section modulus; d_st 7 juga moment of inertia dan polar moment of
  inertia), total FixLoad vertikal (d_st 7 juga total seismic load dan moment),
  dan `wind_cases[]`. Tiap wind case berisi `load_rows[]` (urutan ARM,
  DIRECT_OBJECT, OVERHEAD_WIRE, POLE dari atas), `totals`, dan `checks`. Baris
  ARM tidak punya `projected_area_m2` / `wind_coefficient` (`null`); nilainya ada
  per objek di `arms[].objects[]`. Di d_st 7 setiap baris punya `seismic_load_n`
  dan `seismic_moment_nm`, baris ARM juga `wind_torque_nm` dan
  `seismic_torque_nm`, dan `totals` berisi moment FixLoad, torsi angin, dan
  moment seismic per arah.
- Check `*_torsion` memakai `moment_nm` = moment torsi dan allowable = shear
  jangka pendek. Check `*_combined` memakai `stress_n_mm2` = tegangan gabungan
  maksimum dan menambah `maximum_shear_stress_n_mm2`.

### Tambahan d_st 7 untuk laporan New JIL
Hanya design standard 7. Nilai komponen yang dihitung engine, dan beberapa nilai
turunan ringan dengan rounding yang sama:
- `pole_sections[]`: `section_modulus_cm3`, `length_m`, `mass_kg`, `fix_load_n`,
  `projected_area_m2` (seluruh step pole), dan `fix_load_per_meter_n_m` (massa per
  meter pada ukuran rata-rata lower dan upper, dikali gravitasi).
- `direct_objects[]` (baru): per objek, `quantity`, `mass_kg`, `front_wind_load_n`,
  `side_wind_load_n` (tidak bergantung arah angin).
- `arms[]`: `specification.fix_load_per_meter_n_m`, `objects[].mass_kg`,
  `totals.front_wind_load_n` (badan dan objek, masing-masing di sisi depan).
- `overhead_wires[]`: `mass_kg`, `front_wind_load_n`, dan `straight_wind` /
  `oblique_wind` (line load gabungan dan tension saat angin 90° dan 45° terhadap
  kabel).
- `evaluated_positions[]`: `seismic_tension_n`, `resultant_seismic_load_n`
  (seismic load + tension seismic), dan `component_totals` (fix load, seismic load,
  seismic moment per `pole`, `direct_object`, `arm`, `overhead_wire`).
- `wind_cases[].totals`: komponen X/Y `wind_load_*`, `wind_tension_*`,
  `resultant_horizontal_load_*`, `wind_tension_moment_*`, dan moment angin saja
  `wind_moment_nm` / `_x_nm` / `_y_nm` (tanpa fix load dan tension).
  `wind_cases[].component_totals`: wind load dan wind moment per komponen.
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
            "wind_speed_m_s": 60,
            "air_density_kg_m3": 1.23,
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
            "wind_speed_m_s": 60,
            "air_density_kg_m3": 1.23,
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
            "wind_speed_m_s": 60,
            "air_density_kg_m3": 1.23,
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

_NEW_JIL_POLES = [
    {
        "name": "Pole-3",
        "pole_type": "Straight",
        "material": "STK400",
        "top_elevation_m": 1.6,
        "diameter_lower_mm": 175,
        "thickness_lower_mm": 4,
    },
    {
        "name": "Pole-2",
        "pole_type": "Taper",
        "material": "STK400",
        "top_elevation_m": 7.6,
        "diameter_lower_mm": 175,
        "thickness_lower_mm": 4,
        "diameter_upper_mm": 75,
        "thickness_upper_mm": 4,
    },
    {
        "name": "Pole-1",
        "pole_type": "Straight",
        "material": "STK400",
        "top_elevation_m": 10.1,
        "diameter_lower_mm": 75,
        "thickness_lower_mm": 4,
    },
]

REQUEST_EXAMPLES |= {
    "new_jil_arm": {
        "summary": "New JIL (d_st 7): tiang taper + satu arm (LA10B)",
        "description": (
            "Tipe standard LA10B. Objek Omni di arm mengirim `side_area_m2`, yang dipakai "
            "torque. EQa dan EQr tidak dikirim, jadi dipakai default 4.71 dan 1.0."
        ),
        "value": {
            "design_standard": 7,
            "wind_speed_m_s": 60,
            "air_density_kg_m3": 1.23,
            "poles": _NEW_JIL_POLES,
            "arms": [
                {
                    "name": "Arm-1",
                    "material": "STK400",
                    "diameter_mm": 60.5,
                    "thickness_mm": 3.8,
                    "total_length_m": 0.18,
                    "exposed_length_m": 0.18,
                    "installation_height_m": 10.0,
                    "objects": [
                        {
                            "name": "Lamp",
                            "object_type": "Omni",
                            "front_area_m2": 0.1,
                            "side_area_m2": 0.1,
                            "mass_per_unit_kg": 14,
                            "horizontal_load_distance_m": 0.18,
                            "base_wind_coefficient": 1.0,
                            "quantity": 1,
                        }
                    ],
                }
            ],
            "evaluated_positions_m": [7.6, 0.0],
        },
    },
    "new_jil_wire_and_seismic": {
        "summary": "New JIL (d_st 7): direct object + kabel, EQa dan EQr diisi",
        "description": (
            "Tanpa arm. Satu objek Directional, satu overhead wire (tension seismic ikut "
            "dihitung), dan EQa/EQr yang diubah user."
        ),
        "value": {
            "design_standard": 7,
            "wind_speed_m_s": 60,
            "air_density_kg_m3": 1.23,
            "horizontal_acceleration_m_s2": 5.0,
            "response_ratio": 1.2,
            "poles": _NEW_JIL_POLES,
            "direct_objects": [
                {
                    "name": "Sign",
                    "object_type": "Directional",
                    "front_area_m2": 0.3,
                    "side_area_m2": 0.05,
                    "fixed_angle_deg": 30,
                    "mass_per_unit_kg": 12,
                    "elevation_m": 8.0,
                    "base_wind_coefficient": 1.2,
                    "quantity": 1,
                }
            ],
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
            "evaluated_positions_m": [1.6, 0.0],
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
