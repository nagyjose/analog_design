from eda_engine import WorkspaceManager, NgspiceRunner
from eda_data import NgspiceParser, SimulationDataSet

# 1. PŘÍPRAVA PROSTŘEDÍ
ws = WorkspaceManager(project_root="..")
ws.clear_work_directory()
engine = NgspiceRunner(ws)
dataset = SimulationDataSet() # Náš nový datový sklad

# 2. DEFINICE MATICE ÚLOH (PVT Sweep)
kouty = ["mos_ss", "mos_tt", "mos_ff"]
teploty = [-40, 25, 125]

# Řídící blok ukládající všechna data do RAW binárního formátu
control_blok = """
.control
  tran 10p 10n
  write {RAW_OUT} all
.endc
"""

print("Zahajuji PVT analýzu (9 simulací)...")

# 3. SPUSŤ A ULOŽ (Masivní automatizace)
for roh in kouty:
    for teplota in teploty:
        run_id = f"{roh}_{teplota}C"
        
        parametry = {
            "{CORNER}": roh,
            "{TEMP}": teplota
        }
        
        # ENGINE: Fyzicky odřídí Ngspice v pískovišti
        raw_path = engine.run_simulation(
            run_id=run_id,
            template_name="NMOS_lv_sim.spice",
            params=parametry,
            control_block=control_blok
        )
        
        if raw_path:
            # DATA PARSER: Bleskově načte RAW soubor
            df = NgspiceParser.read_raw(raw_path)
            
            # DATA WAREHOUSE: Uloží do skladu pod příslušnými štítky
            dataset.add_run(run_id, parametry, df)
            
            # WORKSPACE: Úklid - smažeme pískoviště, už ho nepotřebujeme (šetříme GB místa!)
            ws.cleanup_sandbox(raw_path.parent)

print(f"Simulace dokončeny. Ve skladu je uloženo {len(dataset.get_all_runs())} běhů.")

# --- UKÁZKA DATABÁZOVÉHO FILTRU ---
# Dej mi všechna data pro Teplotu 125 stupňů (vrátí 3 ze 9 simulací: SS, TT, FF)
horke_rohy = dataset.filter_runs(TEMP=125)

for run in horke_rohy:
    df = run['data']
    maximalni_napeti = df['v(out)'].max()
    print(f"Běh {run['run_id']} dosáhl V_out_max = {maximalni_napeti:.3f} V")