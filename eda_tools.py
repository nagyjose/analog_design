import plotly.graph_objects as go
import numpy as np
import math

# --- NOVÁ FUNKCE PRO INŽENÝRSKÉ FORMÁTOVÁNÍ ---
def format_eng(hodnota, jednotka="", platne_cislice=4):
    """
    Převede číslo s využitím platných číslic (jako na displeji multimetru).
    """
    if hodnota == 0:
        return f"0 {jednotka}".strip()
    
    # 1. Nalezení řádu čísla (exponent pro základ 10)
    exponent = math.floor(math.log10(abs(hodnota)))
    
    # 2. Zaokrouhlení na nejbližší násobek 3 (pro inženýrský zápis)
    exp3 = (exponent // 3) * 3
    
    # 3. Slovník předpon
    predpony = {
        -18: "a", -15: "f", -12: "p", -9: "n", -6: "µ", -3: "m",
        0: "", 3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E"
    }
    
    # 4. Sestavení stringu (pokud jsme mimo rozsah, použijeme klasický vědecký zápis)
    if exp3 in predpony:
        mantisa = hodnota / (10**exp3)
        predpona = predpony[exp3]
        return f"{mantisa:.{platne_cislice}g} {predpona}{jednotka}".strip()
    else:
        return f"{hodnota:.{platne_cislice}g} {jednotka}".strip()


def pridej_delta_marker(fig, x_a, x_b, x_data, y_data, nazev="Delta", 
                        styl="crosshair", jednotka_x="", jednotka_y="", 
                        vypocet_sklonu=True, nazev_sklonu="auto", jednotka_sklonu="auto", 
                        odsazeni_x=0, odsazeni_y=-45, row=1, col=1):
    """
    Přidá A/B kurzory a vypočte Delta hodnoty do specifického podgrafu.
    
    Parametry:
    - fig: Plotly figure objekt
    - x_a, x_b: Požadované pozice kurzorů na ose X
    - x_data, y_data: Pandas Series nebo Numpy pole s daty
    - styl: "vline" (vertikální čáry), "point" (pouze body), "hline" (horizontální čáry k ose Y)
    - row, col: Umístění podgrafu (defaultně 1, 1 - první graf nahoře)
    """
    
    # Nalezení indexů pro hodnoty nejbližší požadovaným X
    idx_a = (np.abs(x_data - x_a)).argmin()
    idx_b = (np.abs(x_data - x_b)).argmin()
    
    # Skutečné hodnoty z dat
    real_xa, real_ya = x_data.iloc[idx_a], y_data.iloc[idx_a]
    real_xb, real_yb = x_data.iloc[idx_b], y_data.iloc[idx_b]
    
    # Tyto hodnoty slouží pro matematiku boxu (např. 15e-6 pro A)
    delta_x = real_xb - real_xa
    delta_y = real_yb - real_ya

    # Společná definice pro "malou černou tečku" (velikost 5), abychom to nemuseli psát 4x
    trace_tecky = go.Scatter(
        x=[real_xa, real_xb], y=[real_ya, real_yb], 
        mode='markers',
        marker=dict(symbol='circle', size=6, color='black', line=dict(color='white', width=1)),
        showlegend=False, hoverinfo='skip'
    )
    
    # 1. VYKRESLENÍ KURZORŮ PODLE ZVOLENÉHO STYLU
    if styl == "vline":
        fig.add_vline(x=real_xa, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
        fig.add_vline(x=real_xb, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
        fig.add_trace(trace_tecky, row=row, col=col)

    elif styl == "hline":
        fig.add_hline(y=real_ya, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
        fig.add_hline(y=real_yb, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
        fig.add_trace(trace_tecky, row=row, col=col)

    elif styl == "point":
        fig.add_trace(
            go.Scatter(
                x=[real_xa, real_xb], 
                y=[real_ya, real_yb],
                mode='markers',
                marker=dict(symbol='circle-open', size=14, color='grey', line=dict(width=2)),
                name=f"Markery: {nazev}",
                showlegend=False
            ),
            row=row, col=col
        )
        fig.add_trace(trace_tecky, row=row, col=col)

    elif styl == "crosshair": # <--- TADY JE NOVÝ PROFESIONÁLNÍ STYL
        # Vertikální čáry
        fig.add_vline(x=real_xa, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
        fig.add_vline(x=real_xb, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
        # Horizontální čáry
        fig.add_hline(y=real_ya, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
        fig.add_hline(y=real_yb, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
        # Zvýraznění průsečíku (bodu na křivce)
        fig.add_trace(trace_tecky, row=row, col=col)
    

    # 2. SESTAVENÍ INFORMAČNÍHO BOXU
    str_dx = format_eng(delta_x, jednotka_x)
    str_dy = format_eng(delta_y, jednotka_y)
    
    # (Tady do budoucna přidáme ty inženýrské předpony a sklon)
    text_box = f"<b>{nazev}</b><br>ΔX: {str_dx}<br>ΔY: {str_dy}"
    
    if vypocet_sklonu and delta_x != 0:
        sklon = delta_y / delta_x

        # Slovník známých fyzikálních vztahů: (Y, X) -> (Název, Jednotka)
        fyzikalni_vztahy = {
            ("A", "V"): ("g_m", "S"),       # Transkonduktance / Vodivost
            ("V", "A"): ("R", "Ω"),         # Odpor (např. Rout)
            ("C", "V"): ("C", "F"),         # Kapacita (Náboj / Napětí)
            ("V", "s"): ("SR", "V/s"),      # Slew Rate (Rychlost přeběhu)
            ("A", "s"): ("di/dt", "A/s"),   # Změna proudu v čase
            ("Wb", "A"): ("L", "H"),        # Indukčnost
            ("Hz", "V"): ("K_vco", "Hz/V"), # Ladicí citlivost VCO
            ("rad", "s"): ("ω", "rad/s")    # Úhlová frekvence
        }
        
        # Získání automatických hodnot (pokud kombinace není ve slovníku, použije se default "k" a "Y/X")
        auto_nazev, auto_jednotka = fyzikalni_vztahy.get(
            (jednotka_y, jednotka_x), 
            ("k", f"{jednotka_y}/{jednotka_x}")
        )
        
        # Pokud uživatel nezadal vlastní název/jednotku, použijeme automatiku
        finalni_nazev = auto_nazev if nazev_sklonu == "auto" else nazev_sklonu
        finalni_jednotka = auto_jednotka if jednotka_sklonu == "auto" else jednotka_sklonu
            
        str_sklon = format_eng(sklon, finalni_jednotka)
        text_box += f"<br>{finalni_nazev}:  {str_sklon}"

    # Výpočet středu pro umístění boxu
    stred_x = real_xa + (delta_x / 2)
    stred_y = max(real_ya, real_yb)
    
    fig.add_annotation(
        x=stred_x, y=stred_y,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="gray", arrowhead=2, 
        ax=odsazeni_x, ay=odsazeni_y, 
        bgcolor="rgba(40, 40, 40, 0.9)", bordercolor="gray", font=dict(color="white"),
        row=row, col=col
    )



def pridej_bodovy_marker(fig, x_data, y_data, rezim="max", cil_x=None, 
                         nazev="Bod", styl="crosshair", 
                         jednotka_x="", jednotka_y="", 
                         odsazeni_x=0, odsazeni_y=-45, row=1, col=1):
    """
    Vyhledá na křivce specifický bod (max, min, nebo konkrétní X) a označí ho.
    """
    # 1. NALEZENÍ SPRÁVNÉHO INDEXU PODLE REŽIMU
    if rezim == "max":
        # idxmax() funguje pro Pandas, argmax() pro čistý Numpy
        idx = y_data.idxmax() if hasattr(y_data, "idxmax") else np.argmax(y_data)
    elif rezim == "min":
        idx = y_data.idxmin() if hasattr(y_data, "idxmin") else np.argmin(y_data)
    elif rezim == "x":
        if cil_x is None:
            raise ValueError("Pro rezim='x' musíte zadat hodnotu 'cil_x'.")
        idx = (np.abs(x_data - cil_x)).argmin()
    else:
        raise ValueError("Neznámý režim! Použijte 'max', 'min', nebo 'x'.")

    # Získání skutečných hodnot X a Y na nalezeném indexu
    real_x = x_data.iloc[idx] if hasattr(x_data, "iloc") else x_data[idx]
    real_y = y_data.iloc[idx] if hasattr(y_data, "iloc") else y_data[idx]

    # 2. VYKRESLENÍ GRAFIKY (Stejná logika jako u Delty)
    trace_tecka = go.Scatter(
        x=[real_x], y=[real_y], mode='markers',
        marker=dict(symbol='circle', size=6, color='black', line=dict(color='white', width=1)),
        showlegend=False, hoverinfo='skip'
    )
    
    if styl == "vline":
        fig.add_vline(x=real_x, line_dash="dash", line_color="gray", opacity=0.7, row=row, col=col)
    elif styl == "hline":
        fig.add_hline(y=real_y, line_dash="dash", line_color="gray", opacity=0.7, row=row, col=col)
    elif styl == "crosshair":
        fig.add_vline(x=real_x, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
        fig.add_hline(y=real_y, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
    
    fig.add_trace(trace_tecka, row=row, col=col)

    # 3. INFORMAČNÍ BOX
    str_x = format_eng(real_x, jednotka_x)
    str_y = format_eng(real_y, jednotka_y)
    
    text_box = f"<b>{nazev}</b><br>X: {str_x}<br>Y: {str_y}"
    
    fig.add_annotation(
        x=real_x, y=real_y,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="gray", arrowhead=2, 
        ax=odsazeni_x, ay=odsazeni_y,
        bgcolor="rgba(40, 40, 40, 0.9)", bordercolor="gray", font=dict(color="white"),
        row=row, col=col
    )

def pridej_statistiku_intervalu(fig, x_a, x_b, x_data, y_data, nazev="Statistika", 
                                jednotka_x="", jednotka_y="", 
                                odsazeni_x=0, odsazeni_y=-60, row=1, col=1):
    """
    Vybere data mezi body x_a a x_b, vystínuje tuto oblast a spočítá v ní Průměr, Zvlnění (Pk-Pk) a RMS.
    """
    # 1. BEZPEČNÉ NALEZENÍ INTERVALU (ochrana proti obrácenému zadání A a B)
    x_min, x_max = min(x_a, x_b), max(x_a, x_b)
    idx_a = (np.abs(x_data - x_min)).argmin()
    idx_b = (np.abs(x_data - x_max)).argmin()
    
    # Pojistka, aby byl první index vždy ten menší (pro správný slicing/výřez)
    if idx_a > idx_b:
        idx_a, idx_b = idx_b, idx_a
        
    # Výřez (slicing) dat spadajících čistě do tohoto intervalu
    x_interval = x_data.iloc[idx_a:idx_b+1] if hasattr(x_data, "iloc") else x_data[idx_a:idx_b+1]
    y_interval = y_data.iloc[idx_a:idx_b+1] if hasattr(y_data, "iloc") else y_data[idx_a:idx_b+1]
    
    real_xa = x_interval.iloc[0] if hasattr(x_interval, "iloc") else x_interval[0]
    real_xb = x_interval.iloc[-1] if hasattr(x_interval, "iloc") else x_interval[-1]
    
    # 2. VÝPOČTY STATISTIKY (Numpy to zvládne bleskově)
    y_avg = np.mean(y_interval)
    y_max = np.max(y_interval)
    y_min = np.min(y_interval)
    y_pkpk = y_max - y_min                  # Zvlnění (Peak-to-Peak)
    y_rms = np.sqrt(np.mean(y_interval**2)) # Efektivní hodnota (Root-Mean-Square)
    y_std = np.std(y_interval)
    
    # 3. VYKRESLENÍ GRAFIKY
    # Vykreslení stínovaného obdélníku přes analyzovanou oblast
    fig.add_vrect(
        x0=real_xa, x1=real_xb, 
        fillcolor="gray", opacity=0.15, 
        layer="below", line_width=1, line_dash="dash", line_color="gray",
        row=row, col=col
    )
    
    # Vykreslení vizuální linky znázorňující vypočtený průměr
    fig.add_trace(
        go.Scatter(
            x=[real_xa, real_xb], y=[y_avg, y_avg], 
            mode='lines', line=dict(color='gray', width=2, dash='dot'),
            showlegend=False, hoverinfo='skip'
        ),
        row=row, col=col
    )

    # 4. INFORMAČNÍ BOX
    str_avg = format_eng(y_avg, jednotka_y)
    str_pkpk = format_eng(y_pkpk, jednotka_y)
    str_rms = format_eng(y_rms, jednotka_y)
    str_std = format_eng(y_std, jednotka_y)
    
    text_box = (f"<b>{nazev}</b><br>"
                f"Průměr: {str_avg}<br>"
                f"Zvlnění: {str_pkpk}<br>"
                f"RMS: {str_rms}<br>"
                f"σ: {str_std}")
    
    # Ukotvíme šipku přesně do středu intervalu a na výšku průměru
    stred_x = real_xa + (real_xb - real_xa) / 2
    
    fig.add_annotation(
        x=stred_x, y=y_avg,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="gray", arrowhead=2, 
        ax=odsazeni_x, ay=odsazeni_y,
        bgcolor="rgba(40, 40, 40, 0.9)", bordercolor="gray", font=dict(color="white"),
        row=row, col=col
    )

def pridej_ac_markery(fig, f_data, mag_data, phase_data, 
                      row_mag=1, col_mag=1, row_phase=2, col_phase=1):
    """
    Provede kompletní AC analýzu (Bode plot) - najde DC zisk, f_3dB, f_T a Phase Margin.
    Předpokládá mag_data v decibelech (dB) a phase_data ve stupních (°).
    """
    # 1. NALEZENÍ DC ZISKU (A0)
    # DC zisk bývá na nejnižší frekvenci, ale pro jistotu najdeme absolutní maximum
    idx_max = mag_data.idxmax() if hasattr(mag_data, "idxmax") else np.argmax(mag_data)
    a0_gain = mag_data.iloc[idx_max] if hasattr(mag_data, "iloc") else mag_data[idx_max]
    a0_freq = f_data.iloc[idx_max] if hasattr(f_data, "iloc") else f_data[idx_max]
    
    # 2. NALEZENÍ ŠÍŘKY PÁSMA (-3 dB)
    target_3db = a0_gain - 3.0
    # Najdeme indexy, kde zisk klesl pod -3dB a vezmeme ten první
    klesnuto_3db = np.where(mag_data <= target_3db)[0]
    
    # 3. NALEZENÍ TRANZITNÍ FREKVENCE (f_T, kde zisk = 0 dB)
    klesnuto_0db = np.where(mag_data <= 0.0)[0]
    
    # Vykreslení A0 (DC zisk)
    str_a0_freq = format_eng(a0_freq, "Hz")
    fig.add_annotation(
        x=np.log10(a0_freq) if a0_freq > 0 else 0, y=a0_gain, # Plotly anotace na log ose chtějí log10(x)
        text=f"<b>DC Zisk (A₀)</b><br>{a0_gain:.2f} dB",
        showarrow=True, arrowhead=2, ay=-40, bgcolor="rgba(40,40,40,0.9)", bordercolor="green", font=dict(color="white"),
        row=row_mag, col=col_mag
    )

    # Vykreslení -3dB šířky pásma (pokud existuje)
    if len(klesnuto_3db) > 0:
        idx_3db = klesnuto_3db[0]
        f_3db = f_data.iloc[idx_3db] if hasattr(f_data, "iloc") else f_data[idx_3db]
        
        str_f3db = format_eng(f_3db, "Hz")
        # Křížový marker pro -3dB
        fig.add_trace(go.Scatter(x=[f_3db], y=[target_3db], mode='markers', marker=dict(symbol='x', size=8, color='yellow'), showlegend=False), row=row_mag, col=col_mag)
        fig.add_hline(y=target_3db, line_dash="dot", line_color="gray", opacity=0.5, row=row_mag, col=col_mag)
        
        fig.add_annotation(
            x=np.log10(f_3db), y=target_3db,
            text=f"<b>Šířka pásma (-3dB)</b><br>BW: {str_f3db}",
            showarrow=True, arrowhead=2, ax=40, ay=-40, bgcolor="rgba(40,40,40,0.9)", bordercolor="yellow", font=dict(color="white"),
            row=row_mag, col=col_mag
        )

    # Vykreslení f_T a Fázové bezpečnosti (Phase Margin)
    if len(klesnuto_0db) > 0:
        idx_0db = klesnuto_0db[0]
        f_T = f_data.iloc[idx_0db] if hasattr(f_data, "iloc") else f_data[idx_0db]
        faze_pri_0db = phase_data.iloc[idx_0db] if hasattr(phase_data, "iloc") else phase_data[idx_0db]
        
        # Standardní výpočet fázové bezpečnosti (PM = 180 + fáze, pokud se blížíme k -180°)
        # (Záleží na tom, zda fáze začíná na 180 nebo 0, ale toto je nejběžnější)
        phase_margin = 180.0 + faze_pri_0db
        str_fT = format_eng(f_T, "Hz")
        
        # Vertikální čára protínající OBA grafy (Amplitudu i Fázi) na frekvenci f_T
        fig.add_vline(x=f_T, line_dash="dash", line_color="red", opacity=0.7, row=row_mag, col=col_mag)
        fig.add_vline(x=f_T, line_dash="dash", line_color="red", opacity=0.7, row=row_phase, col=col_phase)
        
        # Anotace pro f_T v Amplitudě
        fig.add_annotation(
            x=np.log10(f_T), y=0,
            text=f"<b>f_T (0 dB)</b><br>{str_fT}",
            showarrow=True, arrowhead=2, ax=50, ay=30, bgcolor="rgba(40,40,40,0.9)", bordercolor="red", font=dict(color="white"),
            row=row_mag, col=col_mag
        )
        
        # Anotace pro Phase Margin ve Fázi
        fig.add_annotation(
            x=np.log10(f_T), y=faze_pri_0db,
            text=f"<b>Phase Margin (PM)</b><br>{phase_margin:.1f}°",
            showarrow=True, arrowhead=2, ax=50, ay=-40, bgcolor="rgba(40,40,40,0.9)", bordercolor="red", font=dict(color="white"),
            row=row_phase, col=col_phase
        )

def pridej_analyzu_skoku(fig, t_data, y_data, nazev="Analýza skoku", 
                         jednotka_x="s", jednotka_y="V", 
                         tolerance_pct=2.0, row=1, col=1):
    """
    Provede kompletní analýzu hrany: Rise time (10-90%), Slew Rate, Překmit (Overshoot)
    a Dobu ustálení (Settling time) pro zadanou toleranci (výchozí 2 %).
    """
    # 1. PŘEVOD NA NUMPY
    t = np.array(t_data)
    y = np.array(y_data)
    
    # 2. NALEZENÍ POČÁTEČNÍ A USTÁLENÉ HODNOTY
    y_init = np.mean(y[:max(1, len(y)//100)])
    y_final = np.mean(y[-max(1, len(y)//20):])
    amplituda = y_final - y_init
    is_rising = amplituda > 0
    
    if amplituda == 0:
        print("Varování: Amplituda skoku je nulová.")
        return

    # 3. VÝPOČET ÚROVNÍ (10 %, 90 % a Toleranční pásmo pro Settling Time)
    y_10 = y_init + 0.10 * amplituda
    y_90 = y_init + 0.90 * amplituda
    
    # Toleranční pásmo v absolutních hodnotách osy Y
    tolerance_val = (tolerance_pct / 100.0) * abs(amplituda)
    y_tol_upper = y_final + tolerance_val
    y_tol_lower = y_final - tolerance_val

    # 4. HLEDÁNÍ ČASŮ PROTNUTÍ
    if is_rising:
        idx_10 = np.argmax(y >= y_10)
        idx_90 = np.argmax(y >= y_90)
        idx_peak = np.argmax(y)
    else:
        idx_10 = np.argmax(y <= y_10)
        idx_90 = np.argmax(y <= y_90)
        idx_peak = np.argmin(y)

    t_10, t_90 = t[idx_10], t[idx_90]
    y_peak, t_peak = y[idx_peak], t[idx_peak]
    
    # Výpočet Doby ustálení (Settling Time) - prohledáváme, kde křivka "vyletěla" ven
    # Vezmeme všechny indexy, kde je signál MIMO toleranci
    out_of_band = np.where((y > y_tol_upper) | (y < y_tol_lower))[0]
    
    if len(out_of_band) > 0:
        # Poslední bod, který byl mimo toleranci, plus jeden = první bod definitivního vstupu
        idx_settled = out_of_band[-1] + 1
        if idx_settled >= len(t):
            idx_settled = len(t) - 1
    else:
        idx_settled = idx_10 # Pokud to nikdy nevyletělo (extrémně tlumený systém)

    t_settled = t[idx_settled]
    y_settled = y[idx_settled]

    # 5. VÝPOČET METRIK
    rise_time = t_90 - t_10
    slew_rate = abs(y_90 - y_10) / rise_time if rise_time != 0 else 0
    overshoot_pct = (abs(y_peak - y_final) / abs(amplituda)) * 100.0

    # 6. VYKRESLENÍ GRAFIKY
    # Ustálená hodnota a hrany (10%, 90%)
    fig.add_hline(y=y_final, line_dash="dash", line_color="green", opacity=0.6, row=row, col=col)
    fig.add_hline(y=y_90, line_dash="dot", line_color="gray", opacity=0.4, row=row, col=col)
    fig.add_hline(y=y_10, line_dash="dot", line_color="gray", opacity=0.4, row=row, col=col)

    # Zvýraznění hrany (10 - 90 %)
    fig.add_trace(go.Scatter(
        x=[t_10, t_90], y=[y_10, y_90], mode='lines+markers',
        marker=dict(symbol='circle', size=6, color='yellow'),
        line=dict(color='yellow', width=3), showlegend=False, hoverinfo='skip'
    ), row=row, col=col)

    # Marker pro překmit
    if overshoot_pct > 0.1:
        fig.add_trace(go.Scatter(
            x=[t_peak], y=[y_peak], mode='markers', marker=dict(symbol='x', size=8, color='red'),
            showlegend=False, hoverinfo='skip'
        ), row=row, col=col)

    # --- NOVĚ: GRAFIKA PRO SETTLING TIME ---
    # Vykreslíme toleranční pásmo (od hrany až do konce grafu, ať nespamujeme začátek)
    fig.add_trace(go.Scatter(x=[t_10, t[-1]], y=[y_tol_upper, y_tol_upper], mode='lines', line=dict(color='cyan', width=1, dash='dot'), showlegend=False, hoverinfo='skip'), row=row, col=col)
    fig.add_trace(go.Scatter(x=[t_10, t[-1]], y=[y_tol_lower, y_tol_lower], mode='lines', line=dict(color='cyan', width=1, dash='dot'), showlegend=False, hoverinfo='skip'), row=row, col=col)
    
    # Marker přesně v bodě ustálení
    fig.add_trace(go.Scatter(
        x=[t_settled], y=[y_settled], mode='markers', 
        marker=dict(symbol='diamond', size=8, color='cyan', line=dict(color='white', width=1)),
        showlegend=False, hoverinfo='skip'
    ), row=row, col=col)

    # 7. INFORMAČNÍ BOXY
    # Box pro hranu a Slew Rate
    str_tr = format_eng(rise_time, jednotka_x)
    str_sr = format_eng(slew_rate, f"{jednotka_y}/{jednotka_x}")
    nazev_hrany = "Rise Time" if is_rising else "Fall Time"
    
    fig.add_annotation(
        x=t_90, y=y_90, text=f"<b>{nazev_hrany}</b><br>t: {str_tr}<br>SR: {str_sr}",
        showarrow=True, arrowhead=2, ax=-50, ay=-40 if is_rising else 40,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="yellow", font=dict(color="white"),
        row=row, col=col
    )

    # Box pro Překmit
    if overshoot_pct > 0.1:
        fig.add_annotation(
            x=t_peak, y=y_peak, text=f"<b>Překmit (OS)</b><br>{overshoot_pct:.1f} %",
            showarrow=True, arrowhead=2, ax=40, ay=-40 if is_rising else 40,
            bgcolor="rgba(40,40,40,0.9)", bordercolor="red", font=dict(color="white"),
            row=row, col=col
        )
        
    # Box pro Settling Time
    str_settle = format_eng(t_settled, jednotka_x)
    fig.add_annotation(
        x=t_settled, y=y_settled, 
        text=f"<b>Doba ustálení</b><br>ts (±{tolerance_pct}%): {str_settle}",
        showarrow=True, arrowhead=2, ax=50, ay=50,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="cyan", font=dict(color="white"),
        row=row, col=col
    )

def pridej_zpozdeni_signalu(fig, t_data, y_in, y_out, nazev="Zpoždění (t_pd)", 
                            jednotka_x="s", threshold_in=None, threshold_out=None, 
                            odsazeni_y=40, row=1, col=1):
    """
    Změří zpoždění šíření (propagation delay) mezi vstupním a výstupním signálem.
    Hledá průchod přes 50 % rozkmitu (nebo uživatelem definovaný práh).
    """
    t = np.array(t_data)
    v_in = np.array(y_in)
    v_out = np.array(y_out)
    
    # 1. URČENÍ 50% PRAHOVÝCH HODNOT (pokud nejsou zadány uživatelem)
    if threshold_in is None:
        in_min, in_max = np.min(v_in), np.max(v_in)
        threshold_in = in_min + (in_max - in_min) / 2.0
        
    if threshold_out is None:
        out_min, out_max = np.min(v_out), np.max(v_out)
        threshold_out = out_min + (out_max - out_min) / 2.0

    # 2. HLEDÁNÍ PRŮCHODU HRANY
    # Najdeme index prvního průchodu vstupu přes svůj práh
    # (hledáme, kde rozdíl hodnot mění znaménko, nebo kde poprvé překročí práh)
    in_vysoko = v_in >= threshold_in
    in_hrany = np.where(in_vysoko[:-1] != in_vysoko[1:])[0]
    
    if len(in_hrany) == 0:
        print("Varování: Vstupní signál neprotnul prahovou hodnotu.")
        return
        
    idx_in = in_hrany[0] + 1
    t_in = t[idx_in]
    
    # Najdeme průchod výstupu přes svůj práh, ale MUSÍ to být AŽ PO vstupu (kauzalita)
    out_vysoko = v_out >= threshold_out
    out_hrany = np.where(out_vysoko[:-1] != out_vysoko[1:])[0]
    
    # Vyfiltrujeme jen ty hrany výstupu, které se staly po t_in
    out_hrany_validni = [idx for idx in out_hrany if t[idx + 1] > t_in]
    
    if len(out_hrany_validni) == 0:
        print("Varování: Výstupní signál po vstupu nereagoval (neprotnul práh).")
        return
        
    idx_out = out_hrany_validni[0] + 1
    t_out = t[idx_out]
    
    # 3. VÝPOČET ZPOŽDĚNÍ
    t_pd = t_out - t_in
    
    # 4. VYKRESLENÍ GRAFIKY
    # Vykreslení horizontálních čar pro prahové hodnoty (50 % úrovně)
    fig.add_hline(y=threshold_in, line_dash="dot", line_color="magenta", opacity=0.4, row=row, col=col)
    fig.add_hline(y=threshold_out, line_dash="dot", line_color="magenta", opacity=0.4, row=row, col=col)
    
    # Zvýraznění konkrétních bodů průchodu
    fig.add_trace(go.Scatter(
        x=[t_in, t_out], y=[threshold_in, threshold_out], mode='markers',
        marker=dict(symbol='circle-cross', size=8, color='magenta', line=dict(color='white', width=1)),
        showlegend=False, hoverinfo='skip'
    ), row=row, col=col)

    # Natažení šipky z bodu IN do bodu OUT
    # Plotly umí udělat kótu tak, že ax a ay nastavíme jako data (xref/axref = "x")
    fig.add_annotation(
        x=t_out, y=threshold_out,
        ax=t_in, ay=threshold_in,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=3, arrowcolor="magenta", arrowwidth=2,
        row=row, col=col
    )
    
    # 5. INFORMAČNÍ BOX UPROSTŘED
    str_tpd = format_eng(t_pd, jednotka_x)
    stred_t = t_in + (t_pd / 2)
    stred_v = max(threshold_in, threshold_out)
    
    fig.add_annotation(
        x=stred_t, y=stred_v,
        text=f"<b>{nazev}</b><br>Δt: {str_tpd}",
        showarrow=True, arrowcolor="magenta", arrowhead=1, ay=-odsazeni_y,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="magenta", font=dict(color="white"),
        row=row, col=col
    )

def pridej_mereni_frekvence(fig, t_data, y_data, nazev="Frekvence", 
                            threshold=None, jednotka_t="s", jednotka_f="Hz", 
                            odsazeni_y=40, row=1, col=1):
    """
    Změří průměrnou frekvenci, periodu a střídu (Duty Cycle) periodického signálu.
    Funguje pro obdélník, sinus i trojúhelník.
    """
    t = np.array(t_data)
    y = np.array(y_data)
    
    # 1. URČENÍ ROZHODOVACÍ ÚROVNĚ (Pokud uživatel nezadá, použijeme DC průměr signálu)
    if threshold is None:
        threshold = np.mean(y)
        
    # 2. HLEDÁNÍ HRAN (Průchodů přes threshold)
    nad_prahem = y >= threshold
    
    # Indexy, kde se signál mění z Low na High a z High na Low
    rising_edges = np.where((~nad_prahem[:-1]) & (nad_prahem[1:]))[0]
    falling_edges = np.where((nad_prahem[:-1]) & (~nad_prahem[1:]))[0]
    
    if len(rising_edges) < 2:
        print(f"Varování ({nazev}): Signál neobsahuje ani dvě náběžné hrany. Nelze určit frekvenci.")
        return
        
    # 3. VÝPOČET PERIOD A FREKVENCE (Průměr přes všechny nalezené periody)
    periody = t[rising_edges[1:]] - t[rising_edges[:-1]]
    avg_period = np.mean(periody)
    freq = 1.0 / avg_period
    
    # 4. VÝPOČET STŘÍDY (Duty Cycle)
    pulse_widths = []
    for r_idx in rising_edges:
        # Hledáme první sestupnou hranu, která následuje hned po této náběžné
        valid_falls = falling_edges[falling_edges > r_idx]
        if len(valid_falls) > 0:
            pulse_widths.append(t[valid_falls[0]] - t[r_idx])
            
    if len(pulse_widths) > 0:
        avg_pw = np.mean(pulse_widths)
        duty_cycle = (avg_pw / avg_period) * 100.0
    else:
        duty_cycle = 0.0

    # 5. VYKRESLENÍ GRAFIKY (Pro názornost nakreslíme kóty jen přes první nalezenou periodu)
    t_start = t[rising_edges[0]]
    t_end = t[rising_edges[1]]
    
    # Najdeme sestupnou hranu, která je mezi t_start a t_end (pro vizualizaci střídy)
    f_idx = falling_edges[(falling_edges > rising_edges[0]) & (falling_edges < rising_edges[1])]
    t_fall = t[f_idx[0]] if len(f_idx) > 0 else t_end
    
    # Horizontální osa prahu (Threshold)
    fig.add_hline(y=threshold, line_dash="dot", line_color="cyan", opacity=0.5, row=row, col=col)
    
    # Značky na začátku a konci periody
    fig.add_trace(go.Scatter(
        x=[t_start, t_end], y=[threshold, threshold], mode='markers',
        marker=dict(symbol='circle-cross', size=8, color='cyan'),
        showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Kóta pro celou Periodu (Zvýrazněná nad signálem)
    y_kota = np.max(y) + (np.max(y) - np.min(y)) * 0.05 # Lehce nad maximem signálu
    
    fig.add_annotation(
        x=t_end, y=y_kota, ax=t_start, ay=y_kota,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=3, arrowside="end+start", arrowcolor="cyan", arrowwidth=2,
        row=row, col=col
    )
    
    # Kóta pro šířku pulzu (T_high) pro znázornění střídy
    fig.add_annotation(
        x=t_fall, y=threshold, ax=t_start, ay=threshold,
        xref="x", yref="y", axref="x", ayref="y",
        showarrow=True, arrowhead=2, arrowside="end+start", arrowcolor="orange", opacity=0.7,
        row=row, col=col
    )

    # 6. INFORMAČNÍ BOX
    str_freq = format_eng(freq, jednotka_f)
    str_per = format_eng(avg_period, jednotka_t)
    
    stred_t = t_start + (avg_period / 2)
    
    fig.add_annotation(
        x=stred_t, y=y_kota,
        text=f"<b>{nazev}</b><br>f: {str_freq}<br>T: {str_per}<br>Střída: {duty_cycle:.1f} %",
        showarrow=True, arrowcolor="cyan", arrowhead=1, ay=-odsazeni_y,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="cyan", font=dict(color="white"),
        row=row, col=col
    )

def pridej_analyzu_thd(fig, f_data, mag_data, num_harmonics=5, is_db=True, 
                       osa_x_log=False, nazev="Analýza zkreslení (THD)", 
                       jednotka_f="Hz", jednotka_y="V", row=1, col=1):
    """
    Vyhledá základní harmonickou (f0), identifikuje vyšší harmonické (2f0, 3f0...) 
    a vypočítá celkové harmonické zkreslení (THD) v procentech a dBc.
    """
    f = np.array(f_data)
    mag = np.array(mag_data)
    
    # 1. IGNOROVÁNÍ DC SLOŽKY
    # Hledáme od prvního nenulového Hz, abychom nechytili DC ofset
    valid_idx = np.where(f > 0)[0]
    if len(valid_idx) == 0:
        return
        
    f_valid = f[valid_idx]
    mag_valid = mag[valid_idx]
    
    # 2. NALEZENÍ ZÁKLADNÍ HARMONICKÉ (Fundamental, f0)
    idx_f0_valid = np.argmax(mag_valid)
    f0 = f_valid[idx_f0_valid]
    mag_f0 = mag_valid[idx_f0_valid]
    
    # Pomocná funkce pro převod z dB na lineární napětí (potřebné pro správnou fyzikální matematiku)
    def to_lin(val):
        return 10**(val / 20.0) if is_db else val
        
    lin_f0 = to_lin(mag_f0)
    
    # 3. HLEDÁNÍ VYŠŠÍCH HARMONICKÝCH
    harmonics_f = []
    harmonics_mag = []
    lin_harmonics_sum_sq = 0.0
    
    # FFT okénko (hledáme špičku v okolí +/- 2.5 % od teoretického násobku f0)
    window = f0 * 0.025
    
    for k in range(2, num_harmonics + 1):
        target_f = k * f0
        # Je cílová frekvence vůbec v našich simulovaných datech?
        if target_f > np.max(f):
            break
            
        # Vyřízneme si okolí teoretické harmonické a najdeme v něm maximum
        mask = (f >= target_f - window) & (f <= target_f + window)
        if np.any(mask):
            idx_h = np.argmax(mag[mask])
            real_f = f[mask][idx_h]
            real_mag = mag[mask][idx_h]
            
            harmonics_f.append(real_f)
            harmonics_mag.append(real_mag)
            lin_harmonics_sum_sq += to_lin(real_mag)**2
            
    # 4. VÝPOČET THD
    if lin_harmonics_sum_sq == 0 or lin_f0 == 0:
        thd_pct = 0.0
        thd_dbc = -999.0
    else:
        # THD_F (IEEE definice: V_harmonics_rms / V_fundamental_rms)
        thd_lin = np.sqrt(lin_harmonics_sum_sq) / lin_f0
        thd_pct = thd_lin * 100.0
        thd_dbc = 20 * np.log10(thd_lin)
        
    # 5. VYKRESLENÍ GRAFIKY
    # Marker pro základní harmonickou (Zelená Hvězda)
    fig.add_trace(go.Scatter(
        x=[f0], y=[mag_f0], mode='markers',
        marker=dict(symbol='star', size=12, color='lime', line=dict(color='white', width=1)),
        showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Markery pro parazitní harmonické (Červené kříže)
    if len(harmonics_f) > 0:
        fig.add_trace(go.Scatter(
            x=harmonics_f, y=harmonics_mag, mode='markers',
            marker=dict(symbol='x', size=8, color='red', line=dict(width=2)),
            showlegend=False, hoverinfo='skip'
        ), row=row, col=col)
        
    # 6. INFORMAČNÍ BOX
    str_f0 = format_eng(f0, jednotka_f)
    
    # Pokud uživatel zapne osu X na logaritmickou (běžné u FFT), Plotly anotace vyžadují log10
    x_pos = np.log10(f0) if osa_x_log else f0
    
    # Vyklopení boxu vysoko nad graf, ať nepřekáží špičkám
    y_kota = np.max(mag) + (np.max(mag) - np.min(mag)) * 0.1
    
    text_box = (f"<b>{nazev}</b><br>"
                f"f₀ (Nosná): {str_f0}<br>"
                f"Výkon f₀: {mag_f0:.2f} {'dB' if is_db else jednotka_y}<br>"
                f"Harmonické (až do {len(harmonics_f)+1}f₀)<br>"
                f"<b>THD: {thd_pct:.3f} %  ({thd_dbc:.1f} dBc)</b>")
                
    fig.add_annotation(
        x=x_pos, y=mag_f0,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="lime", arrowhead=2, ax=60, ay=-50,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="lime", font=dict(color="white"),
        row=row, col=col
    )

def pridej_analyzu_fazoveho_sumu(fig, f_offset_data, pn_data, f_carrier, 
                                 int_bw=(1e4, 1e7), spot_offsets=[1e3, 1e6], 
                                 osa_x_log=True, nazev="Fázový šum (SSB)", 
                                 row=1, col=1):
    """
    Provede analýzu fázového šumu:
    1. Označí Spot Noise (dBc/Hz) na zadaných offsetech (např. 1 kHz, 1 MHz).
    2. Zintegruje šum v pásmu int_bw a vypočítá RMS Jitter v časové doméně.
    """
    f = np.array(f_offset_data)
    pn = np.array(pn_data)
    
    # 1. BODOVÉ MARKERY (Spot Noise na specifických dekádách)
    spot_results = []
    for target_f in spot_offsets:
        if target_f >= np.min(f) and target_f <= np.max(f):
            idx = (np.abs(f - target_f)).argmin()
            real_f = f[idx]
            real_pn = pn[idx]
            
            spot_results.append((real_f, real_pn))
            
            # Zapíchnutí křížku do grafu
            fig.add_trace(go.Scatter(
                x=[real_f], y=[real_pn], mode='markers',
                marker=dict(symbol='x', size=8, color='cyan', line=dict(width=2)),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Anotace pro každý spot
            str_f = format_eng(real_f, "Hz")
            fig.add_annotation(
                x=np.log10(real_f) if osa_x_log else real_f, y=real_pn,
                text=f"{str_f}: {real_pn:.1f} dBc",
                showarrow=True, arrowcolor="cyan", arrowhead=2, ax=40, ay=-30,
                bgcolor="rgba(40,40,40,0.8)", bordercolor="cyan", font=dict(color="white", size=10),
                row=row, col=col
            )

    # 2. VÝPOČET RMS JITTERU (Integrace fázového šumu)
    mask = (f >= int_bw[0]) & (f <= int_bw[1])
    f_int = f[mask]
    pn_int = pn[mask]
    
    jitter_rms = 0.0
    if len(f_int) > 1:
        # Převod z logaritmického dBc/Hz na lineární výkonovou hustotu
        lin_pwr = 10**(pn_int / 10.0)
        
        # Integrace pomocí lichoběžníkové metody (np.trapz)
        int_pwr = np.trapz(lin_pwr, f_int)
        
        # Fázový rozptyl (Phase variance v rad^2) - násobíme 2 pro Double Side Band (DSB)
        phi_var = 2 * int_pwr
        
        # Převod fázové odchylky na časový Jitter (sekundy)
        if phi_var > 0:
            jitter_rms = np.sqrt(phi_var) / (2 * np.pi * f_carrier)

    # 3. VYKRESLENÍ INTEGRAČNÍ OBLASTI (Virtuoso styl stínování)
    if len(f_int) > 1:
        min_pn = np.min(pn) - 5  # Spodní hrana stínování
        
        # Neviditelná spodní linie
        fig.add_trace(go.Scatter(
            x=f_int, y=np.full(len(f_int), min_pn), mode='lines', 
            line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
        ), row=row, col=col)
        
        # Horní linie, která vyplní prostor ("tonexty") žlutou barvou
        fig.add_trace(go.Scatter(
            x=f_int, y=pn_int, mode='lines', 
            fill='tonexty', fillcolor='rgba(255, 255, 0, 0.2)', 
            line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
        ), row=row, col=col)
        
        # Svislé ohraničující čáry integračního okna
        fig.add_vline(x=int_bw[0], line_dash="dash", line_color="yellow", opacity=0.5, row=row, col=col)
        fig.add_vline(x=int_bw[1], line_dash="dash", line_color="yellow", opacity=0.5, row=row, col=col)

    # 4. HLAVNÍ INFORMAČNÍ BOX S VÝSLEDKY
    str_carrier = format_eng(f_carrier, "Hz")
    str_jitter = format_eng(jitter_rms, "s", platne_cislice=3)
    str_bw_start = format_eng(int_bw[0], "Hz")
    str_bw_stop = format_eng(int_bw[1], "Hz")
    
    # Umístění boxu doprostřed grafu (do horní části)
    stred_f = np.sqrt(int_bw[0] * int_bw[1]) # Logaritmický střed integračního pásma
    y_kota = np.max(pn)
    
    text_box = (f"<b>{nazev}</b><br>"
                f"Nosná (f₀): {str_carrier}<br>"
                f"Pásmo: {str_bw_start} - {str_bw_stop}<br>"
                f"<b>RMS Jitter: {str_jitter}</b>")
                
    fig.add_annotation(
        x=np.log10(stred_f) if osa_x_log else stred_f, y=y_kota,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="yellow", arrowhead=1, ay=-40,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="yellow", font=dict(color="white"),
        row=row, col=col
    )

def pridej_analyzu_p1db(fig, pin_data, pout_data, nazev="1dB Komprese (P1dB)", 
                        jednotka="dBm", row=1, col=1):
    """
    Analyzuje kompresi zisku (P1dB) pro výkonové a RF zesilovače.
    Předpokládá vstupní a výstupní data v logaritmických jednotkách (typicky dBm nebo dBV).
    """
    pin = np.array(pin_data)
    pout = np.array(pout_data)
    
    # 1. SEŘAZENÍ DAT (Pro jistotu, kdyby simulátor neplival data popořadě)
    sort_idx = np.argsort(pin)
    pin = pin[sort_idx]
    pout = pout[sort_idx]
    
    # 2. VÝPOČET MALOSIGNÁLOVÉHO ZISKU (Small-Signal Gain)
    # Vezmeme prvních 5 % dat (nebo alespoň první bod), kde je zesilovač zaručeně lineární
    linearni_pocet = max(1, len(pin) // 20)
    zisk_pole = pout[:linearni_pocet] - pin[:linearni_pocet]
    ss_gain = np.mean(zisk_pole)
    
    # 3. TEORIE VS PRAXE (Hledání komprese)
    pout_ideal = pin + ss_gain
    rozdil = pout_ideal - pout  # Jak moc zaostáváme za ideálem?
    
    # Najdeme první index, kde je rozdíl větší nebo roven 1 dB
    idx_komprese = np.where(rozdil >= 1.0)[0]
    
    if len(idx_komprese) == 0:
        print(f"Varování ({nazev}): Zesilovač nedosáhl komprese 1 dB. Zvyšte vstupní výkon v simulaci.")
        return
        
    idx2 = idx_komprese[0]
    
    # 4. LINEÁRNÍ INTERPOLACE PRO MAXIMÁLNÍ PŘESNOST
    # Simulované body málokdy vyjdou PŘESNĚ na 1.000 dB, interpolujeme mezi bodem před a bodem za
    if idx2 > 0:
        idx1 = idx2 - 1
        # Interpolace X-ové souřadnice pro hodnotu y=1.0 na křivce rozdílu
        pin_1db = np.interp(1.0, [rozdil[idx1], rozdil[idx2]], [pin[idx1], pin[idx2]])
        pout_1db = pin_1db + ss_gain - 1.0
    else:
        pin_1db = pin[idx2]
        pout_1db = pout[idx2]

    # 5. VYKRESLENÍ GRAFIKY
    # Vykreslení ideální lineární přímky (Extrapolace malosignálového zisku)
    fig.add_trace(go.Scatter(
        x=pin, y=pout_ideal, mode='lines', 
        line=dict(color='gray', width=2, dash='dot'),
        name="Ideální zisk", showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Zvýraznění bodu P1dB
    fig.add_trace(go.Scatter(
        x=[pin_1db], y=[pout_1db], mode='markers',
        marker=dict(symbol='x', size=10, color='red', line=dict(width=2)),
        showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Zaměřovací kříž (Crosshair)
    fig.add_vline(x=pin_1db, line_dash="dash", line_color="red", opacity=0.5, row=row, col=col)
    fig.add_hline(y=pout_1db, line_dash="dash", line_color="red", opacity=0.5, row=row, col=col)

    # 6. INFORMAČNÍ BOX
    # Zde nepoužíváme format_eng, protože dBm už jsou samy o sobě zformátované (nepoužívá se kdBm apod.)
    text_box = (f"<b>{nazev}</b><br>"
                f"Lineární zisk: {ss_gain:.2f} dB<br>"
                f"<b>Input P1dB: {pin_1db:.2f} {jednotka}</b><br>"
                f"<b>Output P1dB: {pout_1db:.2f} {jednotka}</b>")
                
    fig.add_annotation(
        x=pin_1db, y=pout_1db,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="red", arrowhead=2, ax=-60, ay=-40,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="red", font=dict(color="white"),
        row=row, col=col
    )

def pridej_analyzu_ip3(fig, pin_data, pout_fund_data, pout_im3_data, 
                       nazev="Intercept Point 3 (IP3)", jednotka="dBm", 
                       row=1, col=1):
    """
    Vypočítá a vizualizuje teoretický bod IP3 na základě vstupního výkonu,
    výkonu základní harmonické (Fundamental) a třetího intermodulačního produktu (IM3).
    Očekává data v logaritmických jednotkách (dBm, dBV).
    """
    pin = np.array(pin_data)
    pout_f = np.array(pout_fund_data)
    pout_i = np.array(pout_im3_data)
    
    # 1. SEŘAZENÍ DAT (Pro jistotu)
    sort_idx = np.argsort(pin)
    pin = pin[sort_idx]
    pout_f = pout_f[sort_idx]
    pout_i = pout_i[sort_idx]
    
    # 2. VÝPOČET TEORETICKÝCH SMĚRNIC (v lineární oblasti při nízkém vybuzení)
    # Vezmeme prvních pár bodů, kde je jistota, že se křivky chovají "ideálně" (před kompresí)
    n_lin = max(1, len(pin) // 20)
    
    # Rovnice přímky: y = k*x + q. 
    # Pro Fundamental: y = 1*x + q_f  =>  q_f = y - x (To je vlastně lineární zisk)
    q_f = np.mean(pout_f[:n_lin] - pin[:n_lin])
    
    # Pro IM3: y = 3*x + q_i  =>  q_i = y - 3x
    q_i = np.mean(pout_i[:n_lin] - 3.0 * pin[:n_lin])
    
    # 3. VÝPOČET PRŮSEČÍKU (IIP3 a OIP3)
    # 1*x + q_f = 3*x + q_i  =>  2*x = q_f - q_i  =>  x = (q_f - q_i) / 2
    iip3 = (q_f - q_i) / 2.0
    oip3 = iip3 + q_f  # Výstupní IP3 = Vstupní IP3 + Lineární Zisk
    
    # 4. EXTRAPOLACE (Abychom mohli čáry v grafu protáhnout až k průsečíku a kousek za něj)
    pin_start = pin[0]
    pin_end = iip3 + 5.0  # Protáhneme čáry 5 dB za teoretický bod, aby křížení bylo vidět
    
    x_ideal = [pin_start, pin_end]
    y_ideal_fund = [pin_start + q_f, pin_end + q_f]
    y_ideal_im3 = [3.0 * pin_start + q_i, 3.0 * pin_end + q_i]
    
    # 5. VYKRESLENÍ GRAFIKY
    # Tečkovaná linie základního signálu (Směrnice 1:1)
    fig.add_trace(go.Scatter(
        x=x_ideal, y=y_ideal_fund, mode='lines', 
        line=dict(color='gray', width=2, dash='dot'), showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Tečkovaná linie rušení IM3 (Směrnice 3:1)
    fig.add_trace(go.Scatter(
        x=x_ideal, y=y_ideal_im3, mode='lines', 
        line=dict(color='gray', width=2, dash='dot'), showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Zvýraznění samotného teoretického bodu IP3 (Oranžová Hvězda)
    fig.add_trace(go.Scatter(
        x=[iip3], y=[oip3], mode='markers',
        marker=dict(symbol='star', size=12, color='orange', line=dict(color='white', width=1)),
        showlegend=False, hoverinfo='skip'
    ), row=row, col=col)
    
    # Zaměřovací osy přesně na střed křížení
    fig.add_vline(x=iip3, line_dash="dash", line_color="orange", opacity=0.5, row=row, col=col)
    fig.add_hline(y=oip3, line_dash="dash", line_color="orange", opacity=0.5, row=row, col=col)

    # 6. INFORMAČNÍ BOX
    text_box = (f"<b>{nazev}</b><br>"
                f"Zisk (Linear): {q_f:.2f} dB<br>"
                f"<b>IIP3: {iip3:.2f} {jednotka}</b><br>"
                f"<b>OIP3: {oip3:.2f} {jednotka}</b>")
                
    fig.add_annotation(
        x=iip3, y=oip3,
        text=text_box, align="left", 
        showarrow=True, arrowcolor="orange", arrowhead=2, ax=-60, ay=-50,
        bgcolor="rgba(40,40,40,0.9)", bordercolor="orange", font=dict(color="white"),
        row=row, col=col
    )

def pridej_pasmovou_zonu(fig, x_data, y_data, threshold=-10.0, rezim="below", 
                         nazev="Pásmo", jednotka_x="Hz", barva="green", 
                         osa_x_log=False, odsazeni_y=-40, row=1, col=1):
    """
    Najde a vystínuje všechny úseky křivky, které splňují podmínku (pod/nad prahem).
    Vypočítá šířku nejširšího nalezeného pásma (BW) a jeho střední frekvenci.
    """
    x = np.array(x_data)
    y = np.array(y_data)
    
    # 1. IDENTIFIKACE STAVU V KAŽDÉM BODĚ (Jsme v pásmu?)
    in_zone_mask = (y <= threshold) if rezim == "below" else (y >= threshold)
    
    # 2. HLEDÁNÍ PRŮSEČÍKŮ (Místa, kde se maska mění z True na False a naopak)
    edges = np.where(in_zone_mask[:-1] != in_zone_mask[1:])[0]
    
    crossings_x = []
    for idx in edges:
        x0, x1 = x[idx], x[idx+1]
        y0, y1 = y[idx], y[idx+1]
        # Lineární interpolace pro nalezení zcela přesného X, kde Y = threshold
        if y1 != y0:
            x_c = x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)
        else:
            x_c = x0
        crossings_x.append(x_c)
        
    # 3. SESTAVENÍ INTERVALŮ
    intervals = []
    in_zone = in_zone_mask[0]
    current_start = x[0] if in_zone else None
    
    cross_idx = 0
    for idx in edges:
        xc = crossings_x[cross_idx]
        cross_idx += 1
        
        if in_zone:
            intervals.append((current_start, xc)) # Konec zóny
            in_zone = False
        else:
            current_start = xc # Začátek nové zóny
            in_zone = True
            
    if in_zone:
        intervals.append((current_start, x[-1])) # Zóna sahá až na konec grafu

    if not intervals:
        print(f"Varování ({nazev}): Křivka nikdy nedosáhla podmínky {rezim} {threshold}.")
        return

    # 4. VYKRESLENÍ GRAFIKY
    # Horizontální limitní čára
    fig.add_hline(y=threshold, line_dash="dash", line_color=barva, opacity=0.8, row=row, col=col)
    
    nejdelsi_interval = None
    max_bw = 0
    
    for start, end in intervals:
        bw = end - start
        if bw > max_bw:
            max_bw = bw
            nejdelsi_interval = (start, end)
            
        # Vykreslení stínovaného obdélníku přes každé vyhovující pásmo
        fig.add_vrect(
            x0=start, x1=end, 
            fillcolor=barva, opacity=0.15, 
            layer="below", line_width=0,
            row=row, col=col
        )
        # Svislé čáry ohraničující zónu
        fig.add_vline(x=start, line_dash="dot", line_color=barva, opacity=0.6, row=row, col=col)
        fig.add_vline(x=end, line_dash="dot", line_color=barva, opacity=0.6, row=row, col=col)

    # 5. INFORMAČNÍ BOX (Umístíme ho jen do toho nejširšího pásma, ať nespamujeme graf)
    if nejdelsi_interval:
        start, end = nejdelsi_interval
        stred_x = start + (max_bw / 2)
        
        str_bw = format_eng(max_bw, jednotka_x)
        str_fc = format_eng(stred_x, jednotka_x)
        str_start = format_eng(start, jednotka_x)
        str_end = format_eng(end, jednotka_x)
        
        # Umístění boxu na limitní čáru (Threshold)
        x_pos = np.log10(stred_x) if osa_x_log else stred_x
        
        text_box = (f"<b>{nazev}</b><br>"
                    f"Meze: {str_start} až {str_end}<br>"
                    f"Střed (f_c): {str_fc}<br>"
                    f"<b>Šířka (BW): {str_bw}</b>")
                    
        fig.add_annotation(
            x=x_pos, y=threshold,
            text=text_box, align="left", 
            showarrow=True, arrowcolor=barva, arrowhead=2, ay=odsazeni_y,
            bgcolor="rgba(40,40,40,0.9)", bordercolor=barva, font=dict(color="white"),
            row=row, col=col
        )