"""Sub-main check: total voltage drop, and breaker/cable coordination.

Reads a design from standard input: {"size_mm2": 95, "install": "buried", "breaker_A": 125}
Prints one JSON object: {"achieved": {"voltage_drop": percent, "coordination": ratio}, "basis": "one sentence"}

Cable data comes from cables.csv and the design basis from site.json, both beside this file.  This script computes;
it does not decide.  Whether the numbers meet the requirement is decided against the acceptance limits elsewhere.

Method (closed form, balanced three-phase):
  Ib   = maximum demand x spare factor
  kT   = sqrt((Tmax - Tambient) / (Tmax - Treference))            ambient correction of the catalogue rating
  Iz   = cables per phase x catalogue rating x kT
  Top  = Tambient + (Ib / Iz)^2 x (Tmax - Tambient)               conductor temperature at the design current
  R    = R20 x (1 + alpha20 x (Top - 20)) / cables per phase      ohm/km
  Vd   = sqrt(3) x Ib x L/1000 x (R cos(phi) + X/n sin(phi))      volts, line to line
  voltage_drop = 100 x Vd / Vnominal + drop already used elsewhere        percent
  coordination = max(Ib / In, In / Iz)                             Ib <= In <= Iz when this is at most 1
"""
import csv
import json
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REFERENCE = {'air': ('rating_air_A', 'T_air', 40.0), 'buried': ('rating_buried_A', 'T_soil', 25.0), 'duct': ('rating_duct_A', 'T_soil', 25.0)}

design = json.load(sys.stdin)
site = json.loads((HERE / 'site.json').read_text())
cables = {int(r['size_mm2']): r for r in csv.DictReader(open(HERE / 'cables.csv'))}

size, install, breaker = int(design['size_mm2']), design['install'], float(design['breaker_A'])
row = cables[size]
column, ambient_key, t_ref = REFERENCE[install]
t_amb, t_max, n = float(site[ambient_key]), float(site['T_max']), int(site['cables_per_phase'])
i_b = float(site['maximum_demand_A']) * float(site['spare_factor'])
k_t = math.sqrt((t_max - t_amb) / (t_max - t_ref))
i_z = n * float(row[column]) * k_t
t_op = t_amb + (i_b / i_z) ** 2 * (t_max - t_amb)
r = float(row['r20_ohm_per_km']) * (1.0 + float(site['alpha20_per_K']) * (t_op - 20.0)) / n
pf = float(site['power_factor'])
vd = math.sqrt(3.0) * i_b * float(site['route_length_m']) / 1000.0 * (r * pf + float(row['x_ohm_per_km']) / n * math.sqrt(1.0 - pf ** 2))
cable_pct = 100.0 * vd / float(site['V_nominal'])
total_pct = cable_pct + float(site['drop_used_elsewhere_pct'])
coordination = max(i_b / breaker, breaker / i_z)

basis = (f"{size} mm2 {install}: {total_pct:.2f} % total drop ({cable_pct:.2f} % = {vd:.1f} V in this cable at {t_op:.0f} C over "
         f"{float(site['route_length_m']):.0f} m, plus {float(site['drop_used_elsewhere_pct']):.2f} % elsewhere); "
         f"Ib {i_b:.0f} A, In {breaker:.0f} A, Iz {i_z:.0f} A (ambient factor {k_t:.3f}).")
print(json.dumps({'achieved': {'voltage_drop': round(total_pct, 2), 'coordination': round(coordination, 3)}, 'basis': basis}))
