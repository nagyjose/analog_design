import subprocess
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
from eda_fra_old.eda_tools import pridej_bodovy_marker, pridej_delta_marker, pridej_statistiku_intervalu, pridej_analyzu_skoku

# 1. NASTAVENÍ SOUBORŮ
# Zde zadejte přesný název netlistu, který vám vygeneroval Xschem
NETLIST_XSCHEM = "simulations/NMOS_lv_sim.spice" 
SIM_WRAPPER = "sim_python.spice"
DATA_TXT = "NMOS_lv_res.txt"

# 2. SESTAVENÍ SPICE KÓDU (Dynamický obalový skript)
# V Pythonu můžeme přes f-stringy libovolně měnit jakýkoliv parametr smyčky
spice_kód = f"""
.title Python Řízená Simulace
* Vložíme zlatý netlist nakreslený v Xschemu
.include {NETLIST_XSCHEM}

.control
  * 1. Ignorujeme výchozí .param Vg=0.6 a rovnou proladíme zdroj V1
  dc V1 0 1.2 0.01

  * 2. Výpočet proudu a transkonduktance
  let Idrain = -i(v2)
  let gm = deriv(Idrain)

  * 3. Uložení dat do čistého textového souboru pomocí wrdata
  * Výstup bude mít sloupce: Osa_X(V1), Idrain, Osa_X(V1), gm
  wrdata {DATA_TXT} Idrain gm
.endc
"""

# Zápis wrapperu na disk
with open(SIM_WRAPPER, "w") as f:
    f.write(spice_kód)

# 3. SPUŠTĚNÍ SIMULÁTORU
print("Spouštím Ngspice v dávkovém režimu...")
# -b = batch mode (žádná okna, jen výpočet a ukončení)
subprocess.run(["ngspice", "-b", SIM_WRAPPER], stdout=subprocess.DEVNULL)
print("Simulace dokončena. Zpracovávám data...")

# 4. ZPRACOVÁNÍ DAT (Pandas)
# Příkaz wrdata vždy před každou proměnnou opakuje osu X (sweep), takže formát je: X, Y1, X, Y2
sloupce = ["Vgs1", "Idrain", "Vgs2", "gm"]
df = pd.read_csv(DATA_TXT, sep=r'\s+', header=None, names=sloupce)

# Extrahujeme jen to podstatné
Vgs = df["Vgs1"]
Idrain = df["Idrain"]
gm = df["gm"]

# 5. VYKRESLENÍ EXTRÉMNĚ INTERAKTIVNÍHO GRAFU (Plotly)
# Vytvoříme dva grafy pod sebou se sdílenou osou X
fig = make_subplots(
    rows=2, cols=1, 
    shared_xaxes=True,
    vertical_spacing=0.1,
    subplot_titles=("DC Charakteristika NMOS (Idrain)", "Transkonduktance (gm)")
)

# Přidání křivky Idrain
fig.add_trace(
    go.Scatter(x=Vgs, y=Idrain, mode='lines', name='Idrain', line=dict(color='blue', width=2.5)),
    row=1, col=1
)

# Přidání křivky gm
fig.add_trace(
    go.Scatter(x=Vgs, y=gm, mode='lines', name='gm', line=dict(color='red', width=2.5)),
    row=2, col=1
)

# Nastavení kurzorů a chování grafu
fig.update_layout(
    height=800,
    template="plotly", # Tmavé téma podobné Virtuoso / Xschem
    hovermode="x unified",  # KLÍČOVÁ FUNKCE: Vertikální kurzor protínající oba grafy
    title_text="Návrhová charakteristika NMOS"
)

fig.update_yaxes(title_text="Proud [A]", exponentformat="SI", row=1, col=1, showgrid=True)
fig.update_xaxes(title_text="Vgs [V]", exponentformat="SI", row=2, col=1, showgrid=True)
fig.update_yaxes(title_text="gm [S]", exponentformat="SI", row=2, col=1, showgrid=True)

# --- APLIKACE NAŠICH EXTERNÍCH MARKERŮ ---

# Příklad 1: Vertikální čáry jen pro horní graf (Idrain)
pridej_delta_marker(fig, x_a=0.4, x_b=0.7, x_data=Vgs, y_data=Idrain, 
                    nazev="Id_delta", styl="crosshair", 
                    jednotka_x="V", jednotka_y="A", row=1, col=1)

# Příklad 2: Tečkové markery pro dolní graf (gm) - třeba pro odečet špičky
pridej_delta_marker(fig, x_a=0.5, x_b=0.8, x_data=Vgs, y_data=gm, 
                    nazev="gm_delta", styl="point",
                    jednotka_x="V", jednotka_y="S", row=2, col=1)

# Najde absolutní maximum transkonduktance a udělá tam kříž s popiskem
pridej_bodovy_marker(
    fig, x_data=Vgs, y_data=gm, 
    rezim="max", 
    nazev="Maximum gm", 
    jednotka_x="V", jednotka_y="S", 
    row=2, col=1
)

pridej_bodovy_marker(
    fig, x_data=Vgs, y_data=Idrain, 
    rezim="x", cil_x=1.0, 
    nazev="Pracovní bod", 
    jednotka_x="V", jednotka_y="A", 
    odsazeni_y=40, # Vyklopíme box nahoru, ať nepřekáží
    row=1, col=1
)

pridej_statistiku_intervalu(
    fig, 
    x_a=0.2, x_b=0.45, 
    x_data=Vgs, y_data=gm, 
    nazev="Stats", 
    jednotka_x="s", jednotka_y="V",
    row=2, col=1
)

pridej_analyzu_skoku(
    fig, 
    t_data=Vgs, y_data=gm, 
    nazev="Analýza přechodu", 
    jednotka_x="s", jednotka_y="V", 
    row=2, col=1
)

# Uložení do HTML souboru
vystupni_soubor = "interaktivni_graf.html"
fig.write_html(vystupni_soubor)
print(f"Graf uložen. Otevřete si soubor: {vystupni_soubor}")

