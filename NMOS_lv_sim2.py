import subprocess
import os

NETLIST_XSCHEM = "simulations/NMOS_lv_sim.spice" 
SIM_WRAPPER = "sim_python.spice"
RAW_FILE = "NMOS_lv_res.raw"

# Python dynamicky sestaví řídící kód
spice_kód = f"""
.title Python Řízená Simulace
.include {NETLIST_XSCHEM}

.control
  dc V1 0 1.2 0.01
  
  let Idrain = -i(v2)
  let gm = deriv(Idrain)
  
  * Nyní uložíme všechna data v surovém formátu pro Gaw
  write {RAW_FILE} Idrain gm
.endc
"""

with open(SIM_WRAPPER, "w") as f:
    f.write(spice_kód)

print("Počítám...")
subprocess.run(["ngspice", "-b", SIM_WRAPPER], stdout=subprocess.DEVNULL)

# Spustíme Gaw, aby se zobrazil na ploše (musíte mít funkční export DISPLAY=:1)
print("Otevírám prohlížeč pro interaktivní měření...")
os.system(f"gaw {RAW_FILE} &")