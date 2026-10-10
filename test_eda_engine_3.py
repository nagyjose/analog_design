from eda_engine import WorkspaceManager, NgspiceRunner, Testbench, DCAnalysis

# --- INICIALIZACE PROSTŘEDÍ ---
ws = WorkspaceManager(project_root="./muj_lna_projekt")
ws.clear_work_directory()

# Vytvoření "laboratorního stolu"
tb = Testbench(
    engine=NgspiceRunner(ws),
    template="tb_lna.spice",
    default_params={"{VDD}": 1.2, "{TEMP}": 25, "{CORNER}": "mos_tt"}
)

# --- SCÉNÁŘ 1: Rychlý Sweep pro nalezení optimální šířky ---
# VDD, TEMP a CORNER se automaticky převezmou z defaultu!
tb.set_parameters({
    "{W}": [1.0, 2.0, 3.0], 
    "{L}": 0.13
}, keep_previous=True)

# Spustíme paralelně. Testbench sám generuje .control přes třídu DCAnalysis.
# Výsledkem je list slovníků s cestami k 3 RAW souborům
data_sweep = tb.run(DCAnalysis(sweep1=("vgs", 0, 1.2, 0.01)))

# --- SCÉNÁŘ 2: Sign-Off PVT analýza nad finální šířkou ---
# Tady demonstrujeme chytré slučování (update=True s polem slovníků).
# W a L se zachovají z předchozího kroku (ale vezmeme fixní W=2.0).
tb.set_parameters({"{W}": 2.0, "{L}": 0.13}, keep_previous=False) # Čistý reset
tb.set_parameters({"{VDD}": 1.2}) # Globální znovunastavení

pvt_corners = [
    {"{CORNER}": "mos_ss", "{TEMP}": 125}, # Pomalý, horký
    {"{CORNER}": "mos_ff", "{TEMP}": -40}, # Rychlý, studený
    {"{CORNER}": "mos_fs", "{TEMP}": 25}   # Křížový
]

# Modul chytře sloučí W, L, VDD s těmito třemi kouty.
tb.set_parameters(pvt_corners, keep_previous=True)

# Spustíme tu samou DC analýzu na novém stavu stolu. Odbaví se paralelně 3 rohy.
data_pvt = tb.run(DCAnalysis(sweep1=("vgs", 0, 1.2, 0.01)))