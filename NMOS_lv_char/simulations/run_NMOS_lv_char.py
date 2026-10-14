import numpy as np
from eda_framework.eda_engine import WorkspaceManager, NgspiceRunner, Testbench, DCAnalysis
from eda_framework.eda_data import SimulationDataSet
from eda_framework.eda_plot import EDAPlotter
from eda_framework.eda_analysis import SignalAnalyzer

# =====================================================================
# 1. INICIALIZACE WORKSPACE A TESTBENCHE
# =====================================================================
ws = WorkspaceManager(project_root="..")
ws.clear_work_directory()
engine = NgspiceRunner(ws)

# Výchozí parametry odpovídající značkám ve vašem Xschem schématu
default_params = {
    "{Vg}": 0.6,
    "{Vd}": 0.6,
    "{Vs}": 0,
    "{Vb}": 0,
    "{W_n}": "1.5u",
    "{L_n}": "0.13u",
    "{NG_n}": 1,
    "{M_n}": 1,
    "{TEMP}": 25,
    "{CORNER_MOS_lv}": "mos_tt"
}

# Ujistěte se, že název .spice souboru odpovídá netlistu vygenerovanému z Xschemu
tb = Testbench(engine, template="NMOS_lv_char.spice", default_params=default_params)


# =====================================================================
# ČÁST A: PŘEVODNÍ CHARAKTERISTIKA & METODIKA gm/Id (Sweep Vgs)
# =====================================================================
print("\n--- 1. Spouštím převodní charakteristiku (Sweep Vgs) ---")

# Porovnáme 4 délky kanálu L_n při Vds = 0.6 V
tb.set_parameters({
    "{L_n}": ["0.13u", "0.26u", "0.5u", "1.0u"],
    "{W_n}": "1.5u",
    "{Vd}": 0.6,
    "{CORNER_MOS_lv}": "mos_tt"
}, keep_previous=True)

# DC sweep zdroje V1 (Vgs) od 0 V do 1.2 V s jemným krokem 5 mV
res_vgs = tb.run(DCAnalysis(sweep1=("V1", 0.0, 1.2, 0.005)))

ds_vgs = SimulationDataSet()
ds_vgs.load_engine_results(res_vgs)

# Vektorová matematika přímo v datovém skladu:
# 1. Proud drainem Id = -i(v2) (ošetříme případné nulové/záporné šumové hodnoty v off-stavu)
ds_vgs.add_derived_vector("Id", lambda df: np.maximum(-df["i(v2)"], 1e-15))

# 2. Transkonduktance gm = dId / dVgs
ds_vgs.add_derived_vector("gm", lambda df: np.gradient(df["Id"], df["v(vg)"]))

# 3. Transkonduktanční efektivita gm / Id [S/A = V^-1] (počítáme tam, kde Id > 1 nA)
ds_vgs.add_derived_vector(
    "gm_Id", 
    lambda df: np.where(df["Id"] > 1e-9, df["gm"] / df["Id"], np.nan)
)

# --- Vykreslení Dashboardu 1 (Převodní charakteristiky) ---
plotter_vgs = EDAPlotter(theme="plotly_dark")
fig_vgs = plotter_vgs.create_dashboard(
    rozlozeni=[
        [("graf", "Převodní char. Id(Vgs)"), ("graf", "Transkonduktance gm(Vgs)"), ("graf", "Efektivita gm/Id(Vgs)")],
        [("tabulka", "Id při Vgs = 0.8 V"),  ("tabulka", "Maximum gm"),            ("tabulka", "gm/Id při Vgs = 0.5 V")]
    ],
    title_text="NMOS (sg13_lv_nmos) – Převodní charakteristiky a gm/Id"
)

# Vložení křivek do horního řádku (obarveno podle délky kanálu {L_n})
plotter_vgs.add_pvt_corridor(fig_vgs, ds_vgs, signal="Id",    x_axis="v(vg)", row=1, col=1, hue_param="{L_n}")
plotter_vgs.add_pvt_corridor(fig_vgs, ds_vgs, signal="gm",    x_axis="v(vg)", row=1, col=2, hue_param="{L_n}")
plotter_vgs.add_pvt_corridor(fig_vgs, ds_vgs, signal="gm_Id", x_axis="v(vg)", row=1, col=3, hue_param="{L_n}")

# Automatická analýza pomocí markerů a vypsání tabulek do spodního řádku
analyzer_vgs = SignalAnalyzer(fig=fig_vgs)

vgs_batch = ds_vgs.get_signal("v(vg)")
id_batch  = ds_vgs.get_signal("Id")
gm_batch  = ds_vgs.get_signal("gm")
gmid_batch = ds_vgs.get_signal("gm_Id")

# 1. Odečet proudu Id při Vgs = 0.8 V
data_id = analyzer_vgs.analyzuj_bod(
    vgs_batch, id_batch, rezim="x", cil_x=0.8, 
    jednotka_x="V", jednotka_y="A", row=1, col=1, draw_text=False
)
plotter_vgs.add_analysis_table(fig_vgs, data_id, row=2, col=1, dataset=ds_vgs, meta_keys=["{L_n}"])

# 2. Nalezení maxima transkonduktance gm
data_gm = analyzer_vgs.analyzuj_bod(
    vgs_batch, gm_batch, rezim="max", 
    jednotka_x="V", jednotka_y="S", row=1, col=2, draw_text=False
)
plotter_vgs.add_analysis_table(fig_vgs, data_gm, row=2, col=2, dataset=ds_vgs, meta_keys=["{L_n}"])

# 3. Odečet gm/Id v oblasti mírné inverze (Vgs = 0.5 V)
data_gmid = analyzer_vgs.analyzuj_bod(
    vgs_batch, gmid_batch, rezim="x", cil_x=0.5, 
    jednotka_x="V", jednotka_y="V⁻¹", row=1, col=3, draw_text=False
)
plotter_vgs.add_analysis_table(fig_vgs, data_gmid, row=2, col=3, dataset=ds_vgs, meta_keys=["{L_n}"])

report_vgs_path = ws.dirs["reports"] / "NMOS_prevodni_gmId.html"
fig_vgs.write_html(str(report_vgs_path))
print(f"[✅] Report převodních charakteristik uložen do: {report_vgs_path}")


# =====================================================================
# ČÁST B: VÝSTUPNÍ CHARAKTERISTIKA & VÝSTUPNÍ ODPOR ro (Sweep Vds)
# =====================================================================
print("\n--- 2. Spouštím výstupní charakteristiku (Sweep Vds) ---")

# Porovnáme různá napětí Vg a dvě délky kanálu L_n
tb.set_parameters({
    "{Vg}": [0.5, 0.6, 0.7, 0.8],
    "{L_n}": ["0.13u", "0.5u"],
    "{W_n}": "1.5u",
    "{CORNER_MOS_lv}": "mos_tt"
}, keep_previous=True)

# DC sweep zdroje V2 (Vds) od 0 V do 1.2 V s krokem 10 mV
res_vds = tb.run(DCAnalysis(sweep1=("V2", 0.0, 1.2, 0.01)))

ds_vds = SimulationDataSet()
ds_vds.load_engine_results(res_vds)

# Vektorová matematika: Id, gds = dId/dVds a ro = 1/gds
ds_vds.add_derived_vector("Id",  lambda df: -df["i(v2)"])
ds_vds.add_derived_vector("gds", lambda df: np.gradient(df["Id"], df["v(vd)"]))
ds_vds.add_derived_vector("ro",  lambda df: np.where(df["gds"] > 1e-12, 1.0 / df["gds"], np.nan))

# --- Vykreslení Dashboardu 2 (Výstupní charakteristiky) ---
plotter_vds = EDAPlotter(theme="plotly_dark")
fig_vds = plotter_vds.create_dashboard(
    rozlozeni=[
        [("graf", "Výstupní char. Id(Vds)"), ("graf", "Výstupní odpor ro(Vds)")],
        [("tabulka", "Id v saturaci (Vds = 0.6 V)"), ("tabulka", "ro v saturaci (Vds = 0.6 V)")]
    ],
    title_text="NMOS (sg13_lv_nmos) – Výstupní charakteristiky (Barva = Vg, Čára = L_n)"
)

# Barva rozlišuje Vg, styl čáry (plná/čárkovaná) rozlišuje délku kanálu L_n!
plotter_vds.add_pvt_corridor(fig_vds, ds_vds, signal="Id", x_axis="v(vd)", row=1, col=1, hue_param="{Vg}", dash_param="{L_n}")
plotter_vds.add_pvt_corridor(fig_vds, ds_vds, signal="ro", x_axis="v(vd)", row=1, col=2, hue_param="{Vg}", dash_param="{L_n}")

analyzer_vds = SignalAnalyzer(fig=fig_vds)
vds_batch = ds_vds.get_signal("v(vd)")
id_vds_batch = ds_vds.get_signal("Id")
ro_vds_batch = ds_vds.get_signal("ro")

# Odečet Id a ro uprostřed napájecího rozsahu (Vds = 0.6 V)
data_id_sat = analyzer_vds.analyzuj_bod(vds_batch, id_vds_batch, rezim="x", cil_x=0.6, row=1, col=1, draw_text=False)
data_ro_sat = analyzer_vds.analyzuj_bod(vds_batch, ro_vds_batch, rezim="x", cil_x=0.6, row=1, col=2, draw_text=False)

plotter_vds.add_analysis_table(fig_vds, data_id_sat, row=2, col=1, dataset=ds_vds, meta_keys=["{Vg}", "{L_n}"])
plotter_vds.add_analysis_table(fig_vds, data_ro_sat, row=2, col=2, dataset=ds_vds, meta_keys=["{Vg}", "{L_n}"])

report_vds_path = ws.dirs["reports"] / "NMOS_vystupni_ro.html"
fig_vds.write_html(str(report_vds_path))
print(f"[✅] Report výstupních charakteristik uložen do: {report_vds_path}")