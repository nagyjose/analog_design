import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sim_engine import NgspiceRunner
from eda_fra_old.eda_tools import pridej_bodovy_marker

# 1. Inicializace enginu
engine = NgspiceRunner("simulations/NMOS_lv_sim.spice")

# 2. Definice toho, CO chceme simulovat (řídící blok pro Ngspice)
# Zde využíváme formátování pro jméno výstupního souboru {DATA_TXT}
control_kód = """
.control
  dc V1 0 1.2 0.01
  let Idrain = -i(v2)
  let gm = deriv(Idrain)
  wrdata {DATA_TXT} Idrain gm
.endc
"""

# 3. Definice rohů, které chceme prozkoumat (Corner Analysis)
rohy_mos = ["mos_ss", "mos_tt", "mos_ff"]
barvy = {"mos_ss": "red", "mos_tt": "green", "mos_ff": "blue"}

# Připravíme si graf
fig = make_subplots(rows=2, cols=1, shared_xaxes=True, subplot_titles=("Idrain", "gm"))

# 4. Spuštění hromadné automatizace
vysledky = {}

for roh in rohy_mos:
    print(f"Simuluji roh: {roh}...")
    
    # Namapování proměnných pro nahrazení v netlistu
    parametry = {
        "{CORNER_MOS_lv}": roh,
        "{TEMP}": 25 # Můžeme přidat i smyčku přes teploty
    }
    
    # Engine provede simulaci a vrátí cestu k textovému souboru
    cesta_k_datum = engine.run_simulation(sim_id=roh, params=parametry, control_block=control_kód)
    
    # Načtení dat pomocí enginu
    df = engine.load_wrdata(cesta_k_datum, columns=["Vgs1", "Idrain", "Vgs2", "gm"])
    
    # Přidání do grafu
    fig.add_trace(go.Scatter(x=df["Vgs1"], y=df["Idrain"], mode='lines', name=f"Idrain ({roh})", line=dict(color=barvy[roh])), row=1, col=1)
    fig.add_trace(go.Scatter(x=df["Vgs1"], y=df["gm"], mode='lines', name=f"gm ({roh})", line=dict(color=barvy[roh], dash='dash')), row=2, col=1)
    
    # Uložíme si data pro případnou další analýzu
    vysledky[roh] = df

# 5. Aplikace vašich analytických markerů z eda_tools na nominální roh (TT)
df_tt = vysledky["mos_tt"]
pridej_bodovy_marker(fig, x_data=df_tt["Vgs1"], y_data=df_tt["gm"], rezim="max", nazev="Max gm (TT)", row=2, col=1)

# Finální formátování
fig.update_layout(height=800, template="plotly", hovermode="x unified", title_text="Analýza NMOS přes rohy (PVT)")
fig.update_yaxes(exponentformat="SI")
fig.update_xaxes(exponentformat="SI")
fig.write_html("nmos_corners.html")