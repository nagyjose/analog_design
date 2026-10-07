from eda_engine import WorkspaceManager, NgspiceRunner

# Inicializace
ws = WorkspaceManager(project_root="./Moje_LNA")
ws.clear_work_directory()
engine = NgspiceRunner(ws)

# Řídící blok, který chceme ke každému běhu přidat
# Využíváme standardní Ngspice 'write' pro RAW binární soubor
control_blok = """
.control
  tran 10p 100n
  write {RAW_OUT} all
.endc
"""

# Spuštění analýzy přes různé teploty
raw_soubory = []
teploty = [-40, 25, 125]

for T in teploty:
    run_id = f"teplota_{T}C"
    
    # Engine se postará o vytvoření složky, přepsání {T_VAL} na hodnotu, 
    # vložení control bloku, spuštění Ngspice a vrátí nám cestu k .raw souboru.
    raw_path = engine.run_simulation(
        run_id=run_id,
        template_name="NMOS_lv_sim.spice",
        params={"{CORNER_MOS_lv}": "mos_tt", "{TEMP}": T},
        control_block=control_blok
    )
    
    if raw_path:
        raw_soubory.append(raw_path)

print("\nSeznam připravených RAW souborů k analýze:")
for f in raw_soubory:
    print(f)