import subprocess
import pandas as pd
import pyqtgraph as pg
import numpy as np
import os
os.environ["DISPLAY"] = ":0"  # Nasměruje okna na hlavní plochu kontejneru

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
Idrain_uA = df["Idrain"] * 1e6
gm_mS = df["gm"] * 1e3

# 5. VYKRESLENÍ POMOCÍ PYQTGRAPH
print("Otevírám interaktivní grafické okno...")

# a) Inicializace grafické aplikace
app = pg.mkQApp("Analýza NMOS")

# b) Vytvoření hlavního okna s grafem (jako plt.figure)
win = pg.GraphicsLayoutWidget(show=True, title="Interaktivní návrh NMOS")
win.resize(1000, 600)  # Výchozí velikost okna v pixelech

plot = win.addPlot(title="Převodní charakteristika (Idrain vs Vgs)")
plot.showGrid(x=True, y=True, alpha=0.3)
plot.setLabel('left', "Proud Idrain", units='uA')
plot.setLabel('bottom', "Napětí Vgs", units='V')

# c) Vykreslení dat (používá se žlutá barva jako u osciloskopů)
krivka = plot.plot(Vgs, Idrain_uA, pen=pg.mkPen('y', width=2), name="Idrain")

# d) PŘIDÁNÍ INTERAKTIVNÍHO A/B KURZORU (Linear Region)
# Vytvoříme region, který na začátku položíme mezi Vgs 0.4 V a 0.8 V
region = pg.LinearRegionItem(values=[0.4, 0.8])
region.setBrush([0, 255, 0, 30]) # Zelenkavé průhledné pozadí
plot.addItem(region)

# e) Textové pole, které nám bude ukazovat naměřenou Deltu
delta_text = pg.TextItem(text="Posuňte hrany (A/B) pro měření...", color="w", fill=(50, 50, 50, 200))
plot.addItem(delta_text)
delta_text.setPos(0.05, max(Idrain_uA) * 0.9) # Umístění nahoru doleva

# f) Funkce, která se sama zavolá, kdykoliv hnete myší s kurzorem
def prepocitej_deltu():
    # Získání aktuální pozice hran A (min_x) a B (max_x)
    min_x, max_x = region.getRegion()
    
    # Najdeme indexy v poli, které jsou těmto pozicím nejblíž
    idx_a = (np.abs(Vgs - min_x)).argmin()
    idx_b = (np.abs(Vgs - max_x)).argmin()
    
    # Vypočítáme Deltu X a Deltu Y
    dx = Vgs.iloc[idx_b] - Vgs.iloc[idx_a]
    dy = Idrain_uA.iloc[idx_b] - Idrain_uA.iloc[idx_a]
    
    # Aktualizujeme nápis v grafu
    delta_text.setText(f"Kurzor A: {Vgs.iloc[idx_a]:.3f} V | Kurzor B: {Vgs.iloc[idx_b]:.3f} V\n"
                       f"ΔX (Vgs) = {dx:.3f} V\n"
                       f"ΔY (Idrain) = {dy:.3f} uA")

# Propojení pohybu myši s naší funkcí
region.sigRegionChanged.connect(prepocitej_deltu)

# Spustíme první přepočet, aby se tabulka ukázala rovnou správně
prepocitej_deltu()

# g) Spuštění smyčky aplikace (zastaví Python, dokud okno nezavřete)
pg.exec()
print("Grafické okno zavřeno, skript končí.")