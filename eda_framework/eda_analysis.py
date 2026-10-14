import numpy as np
import math
import plotly.graph_objects as go

class SignalAnalyzer:
    """
    Jádro pro analytiku EDA simulací. 
    Poskytuje sdílené metody pro normalizaci dat, dávkové zpracování a jednotný vizuální styl.
    """
    
    # 1. SDÍLENÉ KONSTANTY (Třídní atributy)
    # Slovník známých fyzikálních vztahů pro výpočet derivací / sklonů.
    FYZIKALNI_VZTAHY = {
        ("A", "V"): ("g_m", "S"),       # Transkonduktance
        ("V", "A"): ("R", "Ω"),         # Odpor
        ("C", "V"): ("C", "F"),         # Kapacita
        ("V", "s"): ("SR", "V/s"),      # Slew Rate
        ("A", "s"): ("di/dt", "A/s"),   # Změna proudu v čase
        ("Wb", "A"): ("L", "H"),        # Indukčnost
        ("Hz", "V"): ("K_vco", "Hz/V"), # Ladicí citlivost VCO
        ("rad", "s"): ("ω", "rad/s")    # Úhlová frekvence
    }

    def __init__(self, fig=None):
        """
        :param fig: Plotly Figure objekt. Pokud je None, analyzátor běží v bezhlavém (extrakčním) režimu.
        """
        self.fig = fig
        
        # 2. JEDNOTNÝ VIZUÁLNÍ STYL (Téma)
        # Sjednotíme vzhled všech textových bublin, ať to nemusíme psát v každé funkci.
        self.style_annot = dict(
            bgcolor="rgba(40, 40, 40, 0.9)", 
            font=dict(color="white"),
            bordercolor="gray",
            align="left"
        )
        
        self.style_marker = dict(
            symbol='circle', 
            size=6, 
            color='black', 
            line=dict(color='white', width=1)
        )

    # ==========================================
    # POMOCNÉ METODY (Shared Utilities)
    # ==========================================

    @staticmethod
    def format_eng(hodnota, jednotka="", platne_cislice=4):
        """
        Převede číslo do inženýrského formátu (např. 1.2e-6 -> 1.2 µ).
        Využívá vaši původní otestovanou logiku.
        """
        if hodnota == 0:
            return f"0 {jednotka}".strip()
        
        exponent = math.floor(math.log10(abs(hodnota)))
        exp3 = (exponent // 3) * 3
        
        predpony = {
            -18: "a", -15: "f", -12: "p", -9: "n", -6: "µ", -3: "m",
            0: "", 3: "k", 6: "M", 9: "G", 12: "T", 15: "P", 18: "E"
        }
        
        if exp3 in predpony:
            mantisa = hodnota / (10**exp3)
            predpona = predpony[exp3]
            return f"{mantisa:.{platne_cislice}g} {predpona}{jednotka}".strip()
        else:
            return f"{hodnota:.{platne_cislice}g} {jednotka}".strip()

    @staticmethod
    def _to_numpy(data) -> np.ndarray:
        """
        Zcela eliminuje nutnost používat .iloc.
        Ať už uživatel pošle Pandas Series, List nebo Numpy pole, vždy vrátí čisté 1D Numpy pole.
        """
        if hasattr(data, "to_numpy"):
            return data.to_numpy()
        return np.array(data)

    @staticmethod
    def _is_batch(data) -> bool:
        """
        Detekuje, zda vstupní data představují "dávku" (např. pole 45 křivek z PVT).
        """
        return isinstance(data, list) or (isinstance(data, np.ndarray) and data.ndim > 1)

    def _resolve_batch_x(self, x_data, index: int):
        """
        Chytrý pomocník pro dávkové zpracování.
        Pokud je x_data sdílené (1D pole pro všechny simulace), vrátí ho celé.
        Pokud má každá Y křivka svou vlastní X osu (např. v .tran analýze), vrátí tu správnou pro daný index.
        """
        if self._is_batch(x_data):
            return x_data[index]
        return x_data

    def analyzuj_bod(self, x_data, y_data, rezim="max", cil_x=None, 
                     nazev="Bod", styl="crosshair", 
                     jednotka_x="", jednotka_y="", 
                     odsazeni_x=0, odsazeni_y=-45, row=1, col=1,
                     draw_markers=True, draw_text=True):
        """
        Vyhledá na křivce specifický bod (max, min, nebo konkrétní X) a označí ho.
        Podporuje dávkové zpracování (změří bod na více křivkách najednou).
        """
        
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(y_data):
            return [
                self.analyzuj_bod(
                    x_data=self._resolve_batch_x(x_data, i), 
                    y_data=y_data[i], 
                    rezim=rezim, cil_x=cil_x, nazev=nazev, styl=styl,
                    jednotka_x=jednotka_x, jednotka_y=jednotka_y,
                    odsazeni_x=odsazeni_x, odsazeni_y=odsazeni_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        # Získání čistých 1D Numpy polí (díky tomu už nemusíme všude psát if hasattr(..., 'iloc'))
        x = self._to_numpy(x_data)
        y = self._to_numpy(y_data)

        # --- 2. NALEZENÍ SPRÁVNÉHO INDEXU PODLE REŽIMU ---
        if rezim == "max":
            idx = np.argmax(y)
        elif rezim == "min":
            idx = np.argmin(y)
        elif rezim == "x":
            if cil_x is None:
                raise ValueError("Pro rezim='x' musíte zadat hodnotu 'cil_x'.")
            idx = (np.abs(x - cil_x)).argmin()
        else:
            raise ValueError("Neznámý režim! Použijte 'max', 'min', nebo 'x'.")

        # Získání skutečných hodnot X a Y na nalezeném indexu
        real_x = x[idx]
        real_y = y[idx]
        
        # Výsledek k navrácení (pro extrakční režim nebo tabulku)
        vysledek = {"x": real_x, "y": real_y}

        # --- 3. VYKRESLENÍ GRAFIKY (Stejná logika jako u Delty, ale chráněná flagem) ---
        if draw_markers and self.fig is not None:
            trace_tecka = go.Scatter(
                x=[real_x], y=[real_y], mode='markers',
                marker=self.style_marker,  # Využití sdíleného stylu z __init__
                showlegend=False, hoverinfo='skip'
            )
            
            if styl == "vline":
                self.fig.add_vline(x=real_x, line_dash="dash", line_color="gray", opacity=0.7, row=row, col=col)
            elif styl == "hline":
                self.fig.add_hline(y=real_y, line_dash="dash", line_color="gray", opacity=0.7, row=row, col=col)
            elif styl == "crosshair":
                self.fig.add_vline(x=real_x, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
                self.fig.add_hline(y=real_y, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
            
            self.fig.add_trace(trace_tecka, row=row, col=col)

        # --- 4. INFORMAČNÍ BOX ---
        if draw_text and self.fig is not None:
            str_x = self.format_eng(real_x, jednotka_x)
            str_y = self.format_eng(real_y, jednotka_y)
            
            text_box = f"<b>{nazev}</b><br>X: {str_x}<br>Y: {str_y}"
            
            self.fig.add_annotation(
                x=real_x, y=real_y,
                text=text_box, 
                showarrow=True, arrowcolor="gray", arrowhead=2, 
                ax=odsazeni_x, ay=odsazeni_y,
                row=row, col=col,
                **self.style_annot  # Rozbalení sdíleného formátování textu!
            )

        return vysledek

    def analyzuj_delta(self, x_a, x_b, x_data, y_data, nazev="Delta", 
                       styl="crosshair", jednotka_x="", jednotka_y="", 
                       vypocet_sklonu=True, nazev_sklonu="auto", jednotka_sklonu="auto", 
                       odsazeni_x=0, odsazeni_y=-45, row=1, col=1,
                       draw_markers=True, draw_text=True):
        """
        Přidá A/B kurzory a vypočte Delta hodnoty do specifického podgrafu.
        Podporuje hromadné zpracování (změří deltu na desítkách křivek najednou).
        
        Parametry:
        - x_a, x_b: Požadované pozice kurzorů na ose X
        - styl: "vline" (vertikální čáry), "point" (pouze body), "hline" (horizontální), "crosshair"
        """
        
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(y_data):
            return [
                self.analyzuj_delta(
                    x_a=x_a, x_b=x_b,
                    x_data=self._resolve_batch_x(x_data, i), 
                    y_data=y_data[i], 
                    nazev=nazev, styl=styl, jednotka_x=jednotka_x, jednotka_y=jednotka_y,
                    vypocet_sklonu=vypocet_sklonu, nazev_sklonu=nazev_sklonu, jednotka_sklonu=jednotka_sklonu,
                    odsazeni_x=odsazeni_x, odsazeni_y=odsazeni_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        x = self._to_numpy(x_data)
        y = self._to_numpy(y_data)

        # Nalezení indexů pro hodnoty nejbližší požadovaným X
        idx_a = (np.abs(x - x_a)).argmin()
        idx_b = (np.abs(x - x_b)).argmin()
        
        # Skutečné hodnoty z dat[cite: 3]
        real_xa, real_ya = x[idx_a], y[idx_a]
        real_xb, real_yb = x[idx_b], y[idx_b]
        
        # Tyto hodnoty slouží pro matematiku boxu (např. 15e-6 pro A)[cite: 3]
        delta_x = real_xb - real_xa
        delta_y = real_yb - real_ya

        # Předběžný výpočet sklonu pro návratová data[cite: 3]
        sklon = None
        if vypocet_sklonu and delta_x != 0:
            sklon = delta_y / delta_x
            
        # Zabalení dat pro extrakční (bezhlavý) režim nebo pro tabulky
        vysledek = {"delta_x": delta_x, "delta_y": delta_y, "sklon": sklon}

        # --- 2. VYKRESLENÍ KURZORŮ PODLE ZVOLENÉHO STYLU ---
        if draw_markers and self.fig is not None:
            # Společná definice pro "malou černou tečku" s využitím sdíleného třídního stylu[cite: 3]
            trace_tecky = go.Scatter(
                x=[real_xa, real_xb], y=[real_ya, real_yb], 
                mode='markers',
                marker=self.style_marker,
                showlegend=False, hoverinfo='skip'
            )
            
            if styl == "vline":
                self.fig.add_vline(x=real_xa, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
                self.fig.add_vline(x=real_xb, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
                self.fig.add_trace(trace_tecky, row=row, col=col)

            elif styl == "hline":
                self.fig.add_hline(y=real_ya, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
                self.fig.add_hline(y=real_yb, line_dash="dash", line_color="grey", opacity=0.7, row=row, col=col)
                self.fig.add_trace(trace_tecky, row=row, col=col)

            elif styl == "point":
                self.fig.add_trace(
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
                self.fig.add_trace(trace_tecky, row=row, col=col)

            elif styl == "crosshair": # TADY JE NOVÝ PROFESIONÁLNÍ STYL[cite: 3]
                # Vertikální čáry
                self.fig.add_vline(x=real_xa, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
                self.fig.add_vline(x=real_xb, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
                # Horizontální čáry
                self.fig.add_hline(y=real_ya, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
                self.fig.add_hline(y=real_yb, line_dash="dot", line_color="gray", opacity=0.6, row=row, col=col)
                # Zvýraznění průsečíku (bodu na křivce)[cite: 3]
                self.fig.add_trace(trace_tecky, row=row, col=col)
        

        # --- 3. SESTAVENÍ INFORMAČNÍHO BOXU ---
        if draw_text and self.fig is not None:
            str_dx = self.format_eng(delta_x, jednotka_x)
            str_dy = self.format_eng(delta_y, jednotka_y)
            
            text_box = f"<b>{nazev}</b><br>ΔX: {str_dx}<br>ΔY: {str_dy}"
            
            if sklon is not None:
                # Získání automatických hodnot přímo z TŘÍDNÍHO slovníku[cite: 3]
                auto_nazev, auto_jednotka = self.FYZIKALNI_VZTAHY.get(
                    (jednotka_y, jednotka_x), 
                    ("k", f"{jednotka_y}/{jednotka_x}")
                )
                
                # Pokud uživatel nezadal vlastní název/jednotku, použijeme automatiku[cite: 3]
                finalni_nazev = auto_nazev if nazev_sklonu == "auto" else nazev_sklonu
                finalni_jednotka = auto_jednotka if jednotka_sklonu == "auto" else jednotka_sklonu
                    
                str_sklon = self.format_eng(sklon, finalni_jednotka)
                text_box += f"<br>{finalni_nazev}:  {str_sklon}"

            # Výpočet středu pro umístění boxu[cite: 3]
            stred_x = real_xa + (delta_x / 2)
            stred_y = max(real_ya, real_yb)
            
            self.fig.add_annotation(
                x=stred_x, y=stred_y,
                text=text_box, 
                showarrow=True, arrowcolor="gray", arrowhead=2, 
                ax=odsazeni_x, ay=odsazeni_y, 
                row=row, col=col,
                **self.style_annot # Využití sdíleného zarovnání a formátování písma!
            )

        return vysledek

    def analyzuj_statistiku_intervalu(self, x_a, x_b, x_data, y_data, nazev="Statistika", 
                                      jednotka_x="", jednotka_y="", 
                                      odsazeni_x=0, odsazeni_y=-60, row=1, col=1,
                                      draw_markers=True, draw_text=True):
        """
        Vybere data mezi body x_a a x_b, vystínuje tuto oblast a spočítá v ní Průměr, Zvlnění (Pk-Pk) a RMS.
        Podporuje dávkové zpracování (vrátí pole výsledků pro pole signálů).
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(y_data):
            return [
                self.analyzuj_statistiku_intervalu(
                    x_a=x_a, x_b=x_b,
                    x_data=self._resolve_batch_x(x_data, i), 
                    y_data=y_data[i], 
                    nazev=nazev, jednotka_x=jednotka_x, jednotka_y=jednotka_y,
                    odsazeni_x=odsazeni_x, odsazeni_y=odsazeni_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace do 1D Numpy polí) ---
        x = self._to_numpy(x_data)
        y = self._to_numpy(y_data)

        # BEZPEČNÉ NALEZENÍ INTERVALU (ochrana proti obrácenému zadání A a B)
        x_min, x_max = min(x_a, x_b), max(x_a, x_b)
        idx_a = (np.abs(x - x_min)).argmin()
        idx_b = (np.abs(x - x_max)).argmin()
        
        # Pojistka, aby byl první index vždy ten menší (pro správný slicing/výřez)
        if idx_a > idx_b:
            idx_a, idx_b = idx_b, idx_a
            
        # Výřez (slicing) dat spadajících čistě do tohoto intervalu
        x_interval = x[idx_a:idx_b+1]
        y_interval = y[idx_a:idx_b+1]
        
        real_xa = x_interval[0]
        real_xb = x_interval[-1]
        
        # --- 2. VÝPOČTY STATISTIKY (Numpy to zvládne bleskově) ---
        y_avg = np.mean(y_interval)
        y_max = np.max(y_interval)
        y_min = np.min(y_interval)
        y_pkpk = y_max - y_min                  # Zvlnění (Peak-to-Peak)
        y_rms = np.sqrt(np.mean(y_interval**2)) # Efektivní hodnota (Root-Mean-Square)
        y_std = np.std(y_interval)
        
        # Zabalení výsledků pro návrat
        vysledek = {
            "avg": y_avg, "max": y_max, "min": y_min, 
            "pkpk": y_pkpk, "rms": y_rms, "std": y_std
        }
        
        # --- 3. VYKRESLENÍ GRAFIKY (Stínovaná oblast a průměr) ---
        if draw_markers and self.fig is not None:
            # Vykreslení stínovaného obdélníku přes analyzovanou oblast
            self.fig.add_vrect(
                x0=real_xa, x1=real_xb, 
                fillcolor="gray", opacity=0.15, 
                layer="below", line_width=1, line_dash="dash", line_color="gray",
                row=row, col=col
            )
            
            # Vykreslení vizuální linky znázorňující vypočtený průměr
            self.fig.add_trace(
                go.Scatter(
                    x=[real_xa, real_xb], y=[y_avg, y_avg], 
                    mode='lines', line=dict(color='gray', width=2, dash='dot'),
                    showlegend=False, hoverinfo='skip'
                ),
                row=row, col=col
            )

        # --- 4. INFORMAČNÍ BOX ---
        if draw_text and self.fig is not None:
            str_avg = self.format_eng(y_avg, jednotka_y)
            str_pkpk = self.format_eng(y_pkpk, jednotka_y)
            str_rms = self.format_eng(y_rms, jednotka_y)
            str_std = self.format_eng(y_std, jednotka_y)
            
            text_box = (f"<b>{nazev}</b><br>"
                        f"Průměr: {str_avg}<br>"
                        f"Zvlnění: {str_pkpk}<br>"
                        f"RMS: {str_rms}<br>"
                        f"σ: {str_std}")
            
            # Ukotvíme šipku přesně do středu intervalu a na výšku průměru
            stred_x = real_xa + (real_xb - real_xa) / 2
            
            self.fig.add_annotation(
                x=stred_x, y=y_avg,
                text=text_box, 
                showarrow=True, arrowcolor="gray", arrowhead=2, 
                ax=odsazeni_x, ay=odsazeni_y,
                row=row, col=col,
                **self.style_annot # Využití sdíleného formátování textu
            )

        return vysledek

    def analyzuj_ac(self, f_data, mag_data, phase_data, 
                    row_mag=1, col_mag=1, row_phase=2, col_phase=1,
                    draw_markers=True, draw_text=True):
        """
        Provede kompletní AC analýzu (Bode plot) - najde DC zisk, f_3dB, f_T a Phase Margin.
        Předpokládá mag_data v decibelech (dB) a phase_data ve stupních (°).
        Podporuje dávkové zpracování (vrátí tabulku výsledků pro celou sadu křivek).
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching pro 3 signály) ---
        if self._is_batch(mag_data):
            return [
                self.analyzuj_ac(
                    f_data=self._resolve_batch_x(f_data, i), 
                    mag_data=mag_data[i], 
                    phase_data=phase_data[i] if self._is_batch(phase_data) else phase_data,
                    row_mag=row_mag, col_mag=col_mag, row_phase=row_phase, col_phase=col_phase,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(mag_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        f = self._to_numpy(f_data)
        mag = self._to_numpy(mag_data)
        phase = self._to_numpy(phase_data)

        # 1. NALEZENÍ DC ZISKU (A0)
        # DC zisk bývá na nejnižší frekvenci, ale pro jistotu najdeme absolutní maximum
        idx_max = np.argmax(mag)
        a0_gain = mag[idx_max]
        a0_freq = f[idx_max]
        
        # 2. NALEZENÍ ŠÍŘKY PÁSMA (-3 dB)
        target_3db = a0_gain - 3.0
        # Najdeme indexy, kde zisk klesl pod -3dB a vezmeme ten první
        klesnuto_3db = np.where(mag <= target_3db)[0]
        
        # 3. NALEZENÍ TRANZITNÍ FREKVENCE (f_T, kde zisk = 0 dB)
        klesnuto_0db = np.where(mag <= 0.0)[0]
        
        # --- 2. VÝPOČTY (Příprava proměnných pro slovník i grafiku) ---
        f_3db = f[klesnuto_3db[0]] if len(klesnuto_3db) > 0 else None
        
        f_T = None
        faze_pri_0db = None
        phase_margin = None
        
        if len(klesnuto_0db) > 0:
            f_T = f[klesnuto_0db[0]]
            faze_pri_0db = phase[klesnuto_0db[0]]
            # Standardní výpočet fázové bezpečnosti (PM = 180 + fáze, pokud se blížíme k -180°)
            # (Záleží na tom, zda fáze začíná na 180 nebo 0, ale toto je nejběžnější)
            phase_margin = 180.0 + faze_pri_0db
            
        vysledek = {
            "a0_gain_dB": a0_gain, "a0_freq_Hz": a0_freq,
            "bw_3dB_Hz": f_3db, 
            "f_T_Hz": f_T, "phase_margin_deg": phase_margin
        }

        # --- 3. VYKRESLOVÁNÍ GRAFIKY (Němé značky a linie) ---
        if draw_markers and self.fig is not None:
            # Vykreslení -3dB šířky pásma (pokud existuje)
            if f_3db is not None:
                # Křížový marker pro -3dB
                self.fig.add_trace(go.Scatter(x=[f_3db], y=[target_3db], mode='markers', marker=dict(symbol='x', size=8, color='yellow'), showlegend=False), row=row_mag, col=col_mag)
                self.fig.add_hline(y=target_3db, line_dash="dot", line_color="gray", opacity=0.5, row=row_mag, col=col_mag)
                
            # Vykreslení f_T
            if f_T is not None:
                # Vertikální čára protínající OBA grafy (Amplitudu i Fázi) na frekvenci f_T
                self.fig.add_vline(x=f_T, line_dash="dash", line_color="red", opacity=0.7, row=row_mag, col=col_mag)
                self.fig.add_vline(x=f_T, line_dash="dash", line_color="red", opacity=0.7, row=row_phase, col=col_phase)

        # --- 4. INFORMAČNÍ BOXY (S využitím sdíleného formátování) ---
        if draw_text and self.fig is not None:
            # Vykreslení A0 (DC zisk)
            str_a0_freq = self.format_eng(a0_freq, "Hz")
            style_a0 = self.style_annot.copy(); style_a0["bordercolor"] = "green"
            
            self.fig.add_annotation(
                x=np.log10(a0_freq) if a0_freq > 0 else 0, y=a0_gain, # Plotly anotace na log ose chtějí log10(x)
                text=f"<b>DC Zisk (A₀)</b><br>{a0_gain:.2f} dB",
                showarrow=True, arrowhead=2, ay=-40, 
                row=row_mag, col=col_mag, **style_a0
            )

            # Vykreslení -3dB šířky pásma 
            if f_3db is not None:
                str_f3db = self.format_eng(f_3db, "Hz")
                style_bw = self.style_annot.copy(); style_bw["bordercolor"] = "yellow"
                
                self.fig.add_annotation(
                    x=np.log10(f_3db), y=target_3db,
                    text=f"<b>Šířka pásma (-3dB)</b><br>BW: {str_f3db}",
                    showarrow=True, arrowhead=2, ax=40, ay=-40, 
                    row=row_mag, col=col_mag, **style_bw
                )

            # Vykreslení f_T a Fázové bezpečnosti (Phase Margin)
            if f_T is not None:
                str_fT = self.format_eng(f_T, "Hz")
                style_pm = self.style_annot.copy(); style_pm["bordercolor"] = "red"
                
                # Anotace pro f_T v Amplitudě
                self.fig.add_annotation(
                    x=np.log10(f_T), y=0,
                    text=f"<b>f_T (0 dB)</b><br>{str_fT}",
                    showarrow=True, arrowhead=2, ax=50, ay=30, 
                    row=row_mag, col=col_mag, **style_pm
                )
                
                # Anotace pro Phase Margin ve Fázi
                self.fig.add_annotation(
                    x=np.log10(f_T), y=faze_pri_0db,
                    text=f"<b>Phase Margin (PM)</b><br>{phase_margin:.1f}°",
                    showarrow=True, arrowhead=2, ax=50, ay=-40, 
                    row=row_phase, col=col_phase, **style_pm
                )

        return vysledek

    def analyzuj_skok(self, t_data, y_data, nazev="Analýza skoku", 
                      jednotka_x="s", jednotka_y="V", 
                      tolerance_pct=2.0, row=1, col=1,
                      draw_markers=True, draw_text=True):
        """
        Provede kompletní analýzu hrany: Rise time (10-90%), Slew Rate, Překmit (Overshoot)
        a Dobu ustálení (Settling time) pro zadanou toleranci (výchozí 2 %).
        Podporuje dávkové zpracování (změří hrany na rodině křivek najednou).
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(y_data):
            return [
                self.analyzuj_skok(
                    t_data=self._resolve_batch_x(t_data, i), 
                    y_data=y_data[i], 
                    nazev=nazev, jednotka_x=jednotka_x, jednotka_y=jednotka_y,
                    tolerance_pct=tolerance_pct, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        t = self._to_numpy(t_data)
        y = self._to_numpy(y_data)
        
        # 2. NALEZENÍ POČÁTEČNÍ A USTÁLENÉ HODNOTY
        y_init = np.mean(y[:max(1, len(y)//100)])
        y_final = np.mean(y[-max(1, len(y)//20):])
        amplituda = y_final - y_init
        is_rising = amplituda > 0
        
        if amplituda == 0:
            print(f"Varování ({nazev}): Amplituda skoku je nulová.")
            return {"rise_time": 0, "slew_rate": 0, "overshoot_pct": 0, "settling_time": 0, "y_final": y_final}

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
        
        vysledek = {
            "rise_time": rise_time,
            "slew_rate": slew_rate,
            "overshoot_pct": overshoot_pct,
            "settling_time": t_settled,
            "y_final": y_final
        }

        # --- 6. VYKRESLENÍ GRAFIKY (Němé značky) ---
        if draw_markers and self.fig is not None:
            # Ustálená hodnota a hrany (10%, 90%)
            self.fig.add_hline(y=y_final, line_dash="dash", line_color="green", opacity=0.6, row=row, col=col)
            self.fig.add_hline(y=y_90, line_dash="dot", line_color="gray", opacity=0.4, row=row, col=col)
            self.fig.add_hline(y=y_10, line_dash="dot", line_color="gray", opacity=0.4, row=row, col=col)

            # Zvýraznění hrany (10 - 90 %)
            self.fig.add_trace(go.Scatter(
                x=[t_10, t_90], y=[y_10, y_90], mode='lines+markers',
                marker=dict(symbol='circle', size=6, color='yellow'),
                line=dict(color='yellow', width=3), showlegend=False, hoverinfo='skip'
            ), row=row, col=col)

            # Marker pro překmit
            if overshoot_pct > 0.1:
                self.fig.add_trace(go.Scatter(
                    x=[t_peak], y=[y_peak], mode='markers', marker=dict(symbol='x', size=8, color='red'),
                    showlegend=False, hoverinfo='skip'
                ), row=row, col=col)

            # --- NOVĚ: GRAFIKA PRO SETTLING TIME ---
            # Vykreslíme toleranční pásmo (od hrany až do konce grafu, ať nespamujeme začátek)
            self.fig.add_trace(go.Scatter(x=[t_10, t[-1]], y=[y_tol_upper, y_tol_upper], mode='lines', line=dict(color='cyan', width=1, dash='dot'), showlegend=False, hoverinfo='skip'), row=row, col=col)
            self.fig.add_trace(go.Scatter(x=[t_10, t[-1]], y=[y_tol_lower, y_tol_lower], mode='lines', line=dict(color='cyan', width=1, dash='dot'), showlegend=False, hoverinfo='skip'), row=row, col=col)
            
            # Marker přesně v bodě ustálení
            self.fig.add_trace(go.Scatter(
                x=[t_settled], y=[y_settled], mode='markers', 
                marker=dict(symbol='diamond', size=8, color='cyan', line=dict(color='white', width=1)),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)


        # --- 7. INFORMAČNÍ BOXY ---
        if draw_text and self.fig is not None:
            # Box pro hranu a Slew Rate
            str_tr = self.format_eng(rise_time, jednotka_x)
            str_sr = self.format_eng(slew_rate, f"{jednotka_y}/{jednotka_x}")
            nazev_hrany = "Rise Time" if is_rising else "Fall Time"
            
            style_edge = self.style_annot.copy(); style_edge["bordercolor"] = "yellow"
            
            self.fig.add_annotation(
                x=t_90, y=y_90, text=f"<b>{nazev_hrany}</b><br>t: {str_tr}<br>SR: {str_sr}",
                showarrow=True, arrowhead=2, ax=-50, ay=-40 if is_rising else 40,
                row=row, col=col, **style_edge
            )

            # Box pro Překmit
            if overshoot_pct > 0.1:
                style_os = self.style_annot.copy(); style_os["bordercolor"] = "red"
                self.fig.add_annotation(
                    x=t_peak, y=y_peak, text=f"<b>Překmit (OS)</b><br>{overshoot_pct:.1f} %",
                    showarrow=True, arrowhead=2, ax=40, ay=-40 if is_rising else 40,
                    row=row, col=col, **style_os
                )
                
            # Box pro Settling Time
            str_settle = self.format_eng(t_settled, jednotka_x)
            style_settle = self.style_annot.copy(); style_settle["bordercolor"] = "cyan"
            self.fig.add_annotation(
                x=t_settled, y=y_settled, 
                text=f"<b>Doba ustálení</b><br>ts (±{tolerance_pct}%): {str_settle}",
                showarrow=True, arrowhead=2, ax=50, ay=50,
                row=row, col=col, **style_settle
            )

        return vysledek

    def analyzuj_zpozdeni_signalu(self, t_data, y_in, y_out, nazev="Zpoždění (t_pd)", 
                                  jednotka_x="s", threshold_in=None, threshold_out=None, 
                                  odsazeni_y=40, row=1, col=1,
                                  draw_markers=True, draw_text=True):
        """
        Změří zpoždění šíření (propagation delay) mezi vstupním a výstupním signálem.
        Hledá průchod přes 50 % rozkmitu (nebo uživatelem definovaný práh).
        Podporuje dávkové zpracování (změří zpoždění pro celou rodinu křivek).
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        # Obvykle je v PVT analyzován výstup (y_out) jako pole. 
        if self._is_batch(y_out):
            return [
                self.analyzuj_zpozdeni_signalu(
                    t_data=self._resolve_batch_x(t_data, i), 
                    y_in=self._resolve_batch_x(y_in, i),  # Vstup může být jeden sdílený, nebo pole!
                    y_out=y_out[i], 
                    nazev=nazev, jednotka_x=jednotka_x, 
                    threshold_in=threshold_in, threshold_out=threshold_out, 
                    odsazeni_y=odsazeni_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_out))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        t = self._to_numpy(t_data)
        v_in = self._to_numpy(y_in)
        v_out = self._to_numpy(y_out)
        
        # 1. URČENÍ 50% PRAHOVÝCH HODNOT (pokud nejsou zadány uživatelem)
        # Uložíme si je do lokálních proměnných, abychom nepřepsali vstupní argument pro další běhy ve smyčce
        if threshold_in is None:
            in_min, in_max = np.min(v_in), np.max(v_in)
            thr_in_val = in_min + (in_max - in_min) / 2.0
        else:
            thr_in_val = threshold_in
            
        if threshold_out is None:
            out_min, out_max = np.min(v_out), np.max(v_out)
            thr_out_val = out_min + (out_max - out_min) / 2.0
        else:
            thr_out_val = threshold_out

        # Defaultní prázdný výsledek pro případ, že se signál nepřeklopí
        vysledek = {"t_pd": None, "t_in": None, "t_out": None, "thr_in": thr_in_val, "thr_out": thr_out_val}

        # --- 2. HLEDÁNÍ PRŮCHODU HRANY ---
        # Najdeme index prvního průchodu vstupu přes svůj práh
        # (hledáme, kde rozdíl hodnot mění znaménko, nebo kde poprvé překročí práh)
        in_vysoko = v_in >= thr_in_val
        in_hrany = np.where(in_vysoko[:-1] != in_vysoko[1:])[0]
        
        if len(in_hrany) == 0:
            print(f"Varování ({nazev}): Vstupní signál neprotnul prahovou hodnotu.")
            return vysledek
            
        idx_in = in_hrany[0] + 1
        t_in = t[idx_in]
        
        # Najdeme průchod výstupu přes svůj práh, ale MUSÍ to být AŽ PO vstupu (kauzalita)
        out_vysoko = v_out >= thr_out_val
        out_hrany = np.where(out_vysoko[:-1] != out_vysoko[1:])[0]
        
        # Vyfiltrujeme jen ty hrany výstupu, které se staly po t_in
        out_hrany_validni = [idx for idx in out_hrany if t[idx + 1] > t_in]
        
        if len(out_hrany_validni) == 0:
            print(f"Varování ({nazev}): Výstupní signál po vstupu nereagoval (neprotnul práh).")
            return vysledek
            
        idx_out = out_hrany_validni[0] + 1
        t_out = t[idx_out]
        
        # --- 3. VÝPOČET ZPOŽDĚNÍ ---
        t_pd = t_out - t_in
        vysledek.update({"t_pd": t_pd, "t_in": t_in, "t_out": t_out})
        
        # --- 4. VYKRESLENÍ GRAFIKY (Němé značky a kóty) ---
        if draw_markers and self.fig is not None:
            # Vykreslení horizontálních čar pro prahové hodnoty (50 % úrovně)
            self.fig.add_hline(y=thr_in_val, line_dash="dot", line_color="magenta", opacity=0.4, row=row, col=col)
            self.fig.add_hline(y=thr_out_val, line_dash="dot", line_color="magenta", opacity=0.4, row=row, col=col)
            
            # Zvýraznění konkrétních bodů průchodu
            self.fig.add_trace(go.Scatter(
                x=[t_in, t_out], y=[thr_in_val, thr_out_val], mode='markers',
                marker=dict(symbol='circle-cross', size=8, color='magenta', line=dict(color='white', width=1)),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)

            # Natažení šipky z bodu IN do bodu OUT
            # Plotly umí udělat kótu tak, že ax a ay nastavíme jako data (xref/axref = "x")
            self.fig.add_annotation(
                x=t_out, y=thr_out_val,
                ax=t_in, ay=thr_in_val,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowcolor="magenta", arrowwidth=2,
                row=row, col=col
            )
            
        # --- 5. INFORMAČNÍ BOX UPROSTŘED ---
        if draw_text and self.fig is not None:
            str_tpd = self.format_eng(t_pd, jednotka_x)
            stred_t = t_in + (t_pd / 2)
            stred_v = max(thr_in_val, thr_out_val)
            
            # Barvu boxu pro zpoždění sladíme s purpurovými liniemi (Magenta)
            style_box = self.style_annot.copy(); style_box["bordercolor"] = "magenta"
            
            self.fig.add_annotation(
                x=stred_t, y=stred_v,
                text=f"<b>{nazev}</b><br>Δt: {str_tpd}",
                showarrow=True, arrowcolor="magenta", arrowhead=1, ay=-odsazeni_y,
                row=row, col=col, **style_box
            )

        return vysledek

    def analyzuj_mereni_frekvence(self, t_data, y_data, nazev="Frekvence", 
                                  threshold=None, jednotka_t="s", jednotka_f="Hz", 
                                  odsazeni_y=40, row=1, col=1,
                                  draw_markers=True, draw_text=True):
        """
        Změří průměrnou frekvenci, periodu a střídu (Duty Cycle) periodického signálu.
        Funguje pro obdélník, sinus i trojúhelník.
        Podporuje dávkové zpracování (změří desítky oscilátorů najednou).
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(y_data):
            return [
                self.analyzuj_mereni_frekvence(
                    t_data=self._resolve_batch_x(t_data, i), 
                    y_data=y_data[i], 
                    nazev=nazev, threshold=threshold, 
                    jednotka_t=jednotka_t, jednotka_f=jednotka_f, 
                    odsazeni_y=odsazeni_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        t = self._to_numpy(t_data)
        y = self._to_numpy(y_data)
        
        # 1. URČENÍ ROZHODOVACÍ ÚROVNĚ (Pokud uživatel nezadá, použijeme DC průměr signálu)
        # Ukládáme do lokální proměnné thr_val, abychom nezničili None pro případné další běhy smyčky
        thr_val = np.mean(y) if threshold is None else threshold
        
        # Defaultní výsledek, kdyby se oscilátor např. v jednom PVT rohu nerozkmital
        vysledek = {"freq": None, "period": None, "duty_cycle": None, "threshold": thr_val}

        # --- 2. HLEDÁNÍ HRAN (Průchodů přes threshold) ---
        nad_prahem = y >= thr_val
        
        # Indexy, kde se signál mění z Low na High a z High na Low
        rising_edges = np.where((~nad_prahem[:-1]) & (nad_prahem[1:]))[0]
        falling_edges = np.where((nad_prahem[:-1]) & (~nad_prahem[1:]))[0]
        
        if len(rising_edges) < 2:
            print(f"Varování ({nazev}): Signál neobsahuje ani dvě náběžné hrany. Nelze určit frekvenci.")
            return vysledek
            
        # --- 3. VÝPOČET PERIOD A FREKVENCE (Průměr přes všechny nalezené periody) ---
        periody = t[rising_edges[1:]] - t[rising_edges[:-1]]
        avg_period = np.mean(periody)
        freq = 1.0 / avg_period
        
        # --- 4. VÝPOČET STŘÍDY (Duty Cycle) ---
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

        vysledek.update({"freq": freq, "period": avg_period, "duty_cycle": duty_cycle})

        # Příprava souřadnic pro kreslení
        t_start = t[rising_edges[0]]
        t_end = t[rising_edges[1]]
        y_kota = np.max(y) + (np.max(y) - np.min(y)) * 0.05 # Lehce nad maximem signálu

        # --- 5. VYKRESLENÍ GRAFIKY (Němé značky a kóty) ---
        if draw_markers and self.fig is not None:
            # Najdeme sestupnou hranu, která je mezi t_start a t_end (pro vizualizaci střídy)
            f_idx = falling_edges[(falling_edges > rising_edges[0]) & (falling_edges < rising_edges[1])]
            t_fall = t[f_idx[0]] if len(f_idx) > 0 else t_end
            
            # Horizontální osa prahu (Threshold)
            self.fig.add_hline(y=thr_val, line_dash="dot", line_color="cyan", opacity=0.5, row=row, col=col)
            
            # Značky na začátku a konci periody
            self.fig.add_trace(go.Scatter(
                x=[t_start, t_end], y=[thr_val, thr_val], mode='markers',
                marker=dict(symbol='circle-cross', size=8, color='cyan'),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Kóta pro celou Periodu (Zvýrazněná nad signálem)
            self.fig.add_annotation(
                x=t_end, y=y_kota, ax=t_start, ay=y_kota,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=3, arrowside="end+start", arrowcolor="cyan", arrowwidth=2,
                row=row, col=col
            )
            
            # Kóta pro šířku pulzu (T_high) pro znázornění střídy
            self.fig.add_annotation(
                x=t_fall, y=thr_val, ax=t_start, ay=thr_val,
                xref="x", yref="y", axref="x", ayref="y",
                showarrow=True, arrowhead=2, arrowside="end+start", arrowcolor="orange", opacity=0.7,
                row=row, col=col
            )

        # --- 6. INFORMAČNÍ BOX ---
        if draw_text and self.fig is not None:
            str_freq = self.format_eng(freq, jednotka_f)
            str_per = self.format_eng(avg_period, jednotka_t)
            
            stred_t = t_start + (avg_period / 2)
            style_freq = self.style_annot.copy(); style_freq["bordercolor"] = "cyan"
            
            self.fig.add_annotation(
                x=stred_t, y=y_kota,
                text=f"<b>{nazev}</b><br>f: {str_freq}<br>T: {str_per}<br>Střída: {duty_cycle:.1f} %",
                showarrow=True, arrowcolor="cyan", arrowhead=1, ay=-odsazeni_y,
                row=row, col=col, **style_freq
            )

        return vysledek

    def analyzuj_thd(self, f_data, mag_data, num_harmonics=5, is_db=True, 
                     osa_x_log=False, nazev="Analýza zkreslení (THD)", 
                     jednotka_f="Hz", jednotka_y="V", row=1, col=1,
                     draw_markers=True, draw_text=True):
        """
        Vyhledá základní harmonickou (f0), identifikuje vyšší harmonické (2f0, 3f0...) 
        a vypočítá celkové harmonické zkreslení (THD) v procentech a dBc.
        Podporuje dávkové zpracování (změří THD pro celou sadu spekter).
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(mag_data):
            return [
                self.analyzuj_thd(
                    f_data=self._resolve_batch_x(f_data, i), 
                    mag_data=mag_data[i], 
                    num_harmonics=num_harmonics, is_db=is_db, 
                    osa_x_log=osa_x_log, nazev=nazev, 
                    jednotka_f=jednotka_f, jednotka_y=jednotka_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(mag_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        f = self._to_numpy(f_data)
        mag = self._to_numpy(mag_data)
        
        # Defaultní výsledek pro případ chybných dat (např. systém bez AC odezvy)
        vysledek = {
            "f0": None, "mag_f0": None, 
            "thd_pct": None, "thd_dbc": None, 
            "harmonics_f": [], "harmonics_mag": []
        }

        # 1. IGNOROVÁNÍ DC SLOŽKY
        # Hledáme od prvního nenulového Hz, abychom nechytili DC ofset[cite: 1]
        valid_idx = np.where(f > 0)[0]
        if len(valid_idx) == 0:
            print(f"Varování ({nazev}): Spektrum neobsahuje žádné nenulové frekvence.")
            return vysledek
            
        f_valid = f[valid_idx]
        mag_valid = mag[valid_idx]
        
        # 2. NALEZENÍ ZÁKLADNÍ HARMONICKÉ (Fundamental, f0)[cite: 1]
        idx_f0_valid = np.argmax(mag_valid)
        f0 = f_valid[idx_f0_valid]
        mag_f0 = mag_valid[idx_f0_valid]
        
        # Pomocná funkce pro převod z dB na lineární napětí (potřebné pro správnou fyzikální matematiku)[cite: 1]
        def to_lin(val):
            return 10**(val / 20.0) if is_db else val
            
        lin_f0 = to_lin(mag_f0)
        
        # 3. HLEDÁNÍ VYŠŠÍCH HARMONICKÝCH[cite: 1]
        harmonics_f = []
        harmonics_mag = []
        lin_harmonics_sum_sq = 0.0
        
        # FFT okénko (hledáme špičku v okolí +/- 2.5 % od teoretického násobku f0)[cite: 1]
        window = f0 * 0.025
        
        for k in range(2, num_harmonics + 1):
            target_f = k * f0
            # Je cílová frekvence vůbec v našich simulovaných datech?[cite: 1]
            if target_f > np.max(f):
                break
                
            # Vyřízneme si okolí teoretické harmonické a najdeme v něm maximum[cite: 1]
            mask = (f >= target_f - window) & (f <= target_f + window)
            if np.any(mask):
                idx_h = np.argmax(mag[mask])
                real_f = f[mask][idx_h]
                real_mag = mag[mask][idx_h]
                
                harmonics_f.append(real_f)
                harmonics_mag.append(real_mag)
                lin_harmonics_sum_sq += to_lin(real_mag)**2
                
        # 4. VÝPOČET THD[cite: 1]
        if lin_harmonics_sum_sq == 0 or lin_f0 == 0:
            thd_pct = 0.0
            thd_dbc = -999.0
        else:
            # THD_F (IEEE definice: V_harmonics_rms / V_fundamental_rms)[cite: 1]
            thd_lin = np.sqrt(lin_harmonics_sum_sq) / lin_f0
            thd_pct = thd_lin * 100.0
            thd_dbc = 20 * np.log10(thd_lin)
            
        # Aktualizace reálných výsledků
        vysledek.update({
            "f0": f0, "mag_f0": mag_f0, 
            "thd_pct": thd_pct, "thd_dbc": thd_dbc, 
            "harmonics_f": harmonics_f, "harmonics_mag": harmonics_mag
        })

        # --- 5. VYKRESLENÍ GRAFIKY (Němé značky) ---
        if draw_markers and self.fig is not None:
            # Marker pro základní harmonickou (Zelená Hvězda)[cite: 1]
            self.fig.add_trace(go.Scatter(
                x=[f0], y=[mag_f0], mode='markers',
                marker=dict(symbol='star', size=12, color='lime', line=dict(color='white', width=1)),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Markery pro parazitní harmonické (Červené kříže)[cite: 1]
            if len(harmonics_f) > 0:
                self.fig.add_trace(go.Scatter(
                    x=harmonics_f, y=harmonics_mag, mode='markers',
                    marker=dict(symbol='x', size=8, color='red', line=dict(width=2)),
                    showlegend=False, hoverinfo='skip'
                ), row=row, col=col)
                
        # --- 6. INFORMAČNÍ BOX ---
        if draw_text and self.fig is not None:
            str_f0 = self.format_eng(f0, jednotka_f)
            
            # Pokud uživatel zapne osu X na logaritmickou (běžné u FFT), Plotly anotace vyžadují log10[cite: 1]
            x_pos = np.log10(f0) if osa_x_log else f0
            
            # Vyklopení boxu vysoko nad graf, ať nepřekáží špičkám[cite: 1]
            y_kota = np.max(mag) + (np.max(mag) - np.min(mag)) * 0.1
            
            text_box = (f"<b>{nazev}</b><br>"
                        f"f₀ (Nosná): {str_f0}<br>"
                        f"Výkon f₀: {mag_f0:.2f} {'dB' if is_db else jednotka_y}<br>"
                        f"Harmonické (až do {len(harmonics_f)+1}f₀)<br>"
                        f"<b>THD: {thd_pct:.3f} %  ({thd_dbc:.1f} dBc)</b>")
                        
            # Využití sdíleného formátování z __init__ s úpravou barvy
            style_thd = self.style_annot.copy(); style_thd["bordercolor"] = "lime"
            
            self.fig.add_annotation(
                x=x_pos, y=mag_f0,
                text=text_box, 
                showarrow=True, arrowcolor="lime", arrowhead=2, ax=60, ay=-50,
                row=row, col=col, **style_thd
            )
            
        return vysledek

    def analyzuj_fazovy_sum(self, f_offset_data, pn_data, f_carrier, 
                            int_bw=(1e4, 1e7), spot_offsets=[1e3, 1e6], 
                            osa_x_log=True, nazev="Fázový šum (SSB)", 
                            row=1, col=1,
                            draw_markers=True, draw_text=True):
        """
        Provede analýzu fázového šumu:
        1. Označí Spot Noise (dBc/Hz) na zadaných offsetech (např. 1 kHz, 1 MHz).
        2. Zintegruje šum v pásmu int_bw a vypočítá RMS Jitter v časové doméně.
        Podporuje dávkové zpracování pro masivní analýzu celých skupin oscilátorů.
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(pn_data):
            return [
                self.analyzuj_fazovy_sum(
                    f_offset_data=self._resolve_batch_x(f_offset_data, i), 
                    pn_data=pn_data[i], 
                    f_carrier=f_carrier, int_bw=int_bw, spot_offsets=spot_offsets, 
                    osa_x_log=osa_x_log, nazev=nazev, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(pn_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        f = self._to_numpy(f_offset_data)
        pn = self._to_numpy(pn_data)
        
        # --- 2. MATEMATIKA: BODOVÉ MARKERY (Spot Noise) ---
        spot_results = []
        for target_f in spot_offsets:
            if target_f >= np.min(f) and target_f <= np.max(f):
                idx = (np.abs(f - target_f)).argmin()
                real_f = f[idx]
                real_pn = pn[idx]
                spot_results.append((real_f, real_pn))

        # --- 3. MATEMATIKA: VÝPOČET RMS JITTERU (Integrace) ---
        mask = (f >= int_bw[0]) & (f <= int_bw[1])
        f_int = f[mask]
        pn_int = pn[mask]
        
        jitter_rms = 0.0
        if len(f_int) > 1:
            # Převod z logaritmického dBc/Hz na lineární výkonovou hustotu
            lin_pwr = 10**(pn_int / 10.0)
            
            # Integrace pomocí lichoběžníkové metody (np.trapz)[cite: 1]
            int_pwr = np.trapz(lin_pwr, f_int)
            
            # Fázový rozptyl (Phase variance v rad^2) - násobíme 2 pro Double Side Band (DSB)[cite: 1]
            phi_var = 2 * int_pwr
            
            # Převod fázové odchylky na časový Jitter (sekundy)[cite: 1]
            if phi_var > 0:
                jitter_rms = np.sqrt(phi_var) / (2 * np.pi * f_carrier)

        # Uložení kompletních výsledků k navrácení
        vysledek = {
            "jitter_rms_s": jitter_rms, 
            "spot_noise_results": spot_results
        }

        # --- 4. VYKRESLENÍ GRAFIKY (Němé značky a stínování) ---
        if draw_markers and self.fig is not None:
            # Zapíchnutí křížků pro Spot Noise[cite: 1]
            for real_f, real_pn in spot_results:
                self.fig.add_trace(go.Scatter(
                    x=[real_f], y=[real_pn], mode='markers',
                    marker=dict(symbol='x', size=8, color='cyan', line=dict(width=2)),
                    showlegend=False, hoverinfo='skip'
                ), row=row, col=col)

            # Vykreslení integrační oblasti (Virtuoso styl stínování)[cite: 1]
            if len(f_int) > 1:
                min_pn = np.min(pn) - 5  # Spodní hrana stínování[cite: 1]
                
                # Neviditelná spodní linie[cite: 1]
                self.fig.add_trace(go.Scatter(
                    x=f_int, y=np.full(len(f_int), min_pn), mode='lines', 
                    line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
                ), row=row, col=col)
                
                # Horní linie, která vyplní prostor ("tonexty") žlutou barvou[cite: 1]
                self.fig.add_trace(go.Scatter(
                    x=f_int, y=pn_int, mode='lines', 
                    fill='tonexty', fillcolor='rgba(255, 255, 0, 0.2)', 
                    line=dict(color='rgba(0,0,0,0)'), showlegend=False, hoverinfo='skip'
                ), row=row, col=col)
                
                # Svislé ohraničující čáry integračního okna[cite: 1]
                self.fig.add_vline(x=int_bw[0], line_dash="dash", line_color="yellow", opacity=0.5, row=row, col=col)
                self.fig.add_vline(x=int_bw[1], line_dash="dash", line_color="yellow", opacity=0.5, row=row, col=col)

        # --- 5. INFORMAČNÍ BOXY (S využitím sdílených stylů) ---
        if draw_text and self.fig is not None:
            # Anotace pro každý spot noise[cite: 1]
            style_spot = self.style_annot.copy(); style_spot["bordercolor"] = "cyan"
            style_spot["font"] = dict(color="white", size=10) # Drobné zmenšení fontu pro spoty[cite: 1]
            
            for real_f, real_pn in spot_results:
                str_f = self.format_eng(real_f, "Hz")
                self.fig.add_annotation(
                    x=np.log10(real_f) if osa_x_log else real_f, y=real_pn,
                    text=f"{str_f}: {real_pn:.1f} dBc",
                    showarrow=True, arrowcolor="cyan", arrowhead=2, ax=40, ay=-30,
                    row=row, col=col, **style_spot
                )

            # Hlavní informační box s RMS Jitterem[cite: 1]
            str_carrier = self.format_eng(f_carrier, "Hz")
            str_jitter = self.format_eng(jitter_rms, "s", platne_cislice=3)
            str_bw_start = self.format_eng(int_bw[0], "Hz")
            str_bw_stop = self.format_eng(int_bw[1], "Hz")
            
            # Umístění boxu doprostřed grafu (do horní části)[cite: 1]
            stred_f = np.sqrt(int_bw[0] * int_bw[1]) # Logaritmický střed integračního pásma[cite: 1]
            y_kota = np.max(pn)
            
            text_box = (f"<b>{nazev}</b><br>"
                        f"Nosná (f₀): {str_carrier}<br>"
                        f"Pásmo: {str_bw_start} - {str_bw_stop}<br>"
                        f"<b>RMS Jitter: {str_jitter}</b>")
                        
            style_jitter = self.style_annot.copy(); style_jitter["bordercolor"] = "yellow"
            
            self.fig.add_annotation(
                x=np.log10(stred_f) if osa_x_log else stred_f, y=y_kota,
                text=text_box, 
                showarrow=True, arrowcolor="yellow", arrowhead=1, ay=-40,
                row=row, col=col, **style_jitter
            )

        return vysledek

    def analyzuj_p1db(self, pin_data, pout_data, nazev="1dB Komprese (P1dB)", 
                      jednotka="dBm", row=1, col=1,
                      draw_markers=True, draw_text=True):
        """
        Analyzuje kompresi zisku (P1dB) pro výkonové a RF zesilovače.
        Předpokládá vstupní a výstupní data v logaritmických jednotkách (typicky dBm nebo dBV).
        Podporuje dávkové zpracování pro masivní extrakci bodu P1dB přes PVT rohy.
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(pout_data):
            return [
                self.analyzuj_p1db(
                    pin_data=self._resolve_batch_x(pin_data, i), 
                    pout_data=pout_data[i], 
                    nazev=nazev, jednotka=jednotka, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(pout_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        pin = self._to_numpy(pin_data)
        pout = self._to_numpy(pout_data)
        
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
        
        # Defaultní výsledek pro bezhlavý režim (pokud nenastala komprese)
        vysledek = {"ss_gain_dB": ss_gain, "pin_1db": None, "pout_1db": None}

        if len(idx_komprese) == 0:
            print(f"Varování ({nazev}): Zesilovač nedosáhl komprese 1 dB. Zvyšte vstupní výkon v simulaci.")
            return vysledek
            
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

        vysledek.update({"pin_1db": pin_1db, "pout_1db": pout_1db})

        # --- 5. VYKRESLENÍ GRAFIKY (Němé značky) ---
        if draw_markers and self.fig is not None:
            # Vykreslení ideální lineární přímky (Extrapolace malosignálového zisku)
            self.fig.add_trace(go.Scatter(
                x=pin, y=pout_ideal, mode='lines', 
                line=dict(color='gray', width=2, dash='dot'),
                name="Ideální zisk", showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Zvýraznění bodu P1dB
            self.fig.add_trace(go.Scatter(
                x=[pin_1db], y=[pout_1db], mode='markers',
                marker=dict(symbol='x', size=10, color='red', line=dict(width=2)),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Zaměřovací kříž (Crosshair)
            self.fig.add_vline(x=pin_1db, line_dash="dash", line_color="red", opacity=0.5, row=row, col=col)
            self.fig.add_hline(y=pout_1db, line_dash="dash", line_color="red", opacity=0.5, row=row, col=col)

        # --- 6. INFORMAČNÍ BOX ---
        if draw_text and self.fig is not None:
            # Zde nepoužíváme format_eng, protože dBm už jsou samy o sobě zformátované (nepoužívá se kdBm apod.)
            text_box = (f"<b>{nazev}</b><br>"
                        f"Lineární zisk: {ss_gain:.2f} dB<br>"
                        f"<b>Input P1dB: {pin_1db:.2f} {jednotka}</b><br>"
                        f"<b>Output P1dB: {pout_1db:.2f} {jednotka}</b>")
                        
            # Využití sdíleného stylu anotace s červeným ohraničením
            style_p1db = self.style_annot.copy(); style_p1db["bordercolor"] = "red"
            
            self.fig.add_annotation(
                x=pin_1db, y=pout_1db,
                text=text_box, 
                showarrow=True, arrowcolor="red", arrowhead=2, ax=-60, ay=-40,
                row=row, col=col, **style_p1db
            )

        return vysledek

    def analyzuj_ip3(self, pin_data, pout_fund_data, pout_im3_data, 
                     nazev="Intercept Point 3 (IP3)", jednotka="dBm", 
                     row=1, col=1,
                     draw_markers=True, draw_text=True):
        """
        Vypočítá a vizualizuje teoretický bod IP3 na základě vstupního výkonu,
        výkonu základní harmonické (Fundamental) a třetího intermodulačního produktu (IM3).
        Očekává data v logaritmických jednotkách (dBm, dBV).
        Podporuje dávkové zpracování pro masivní extrakci IP3 napříč mnoha rohy.
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching pro 3 signály) ---
        if self._is_batch(pout_fund_data):
            return [
                self.analyzuj_ip3(
                    pin_data=self._resolve_batch_x(pin_data, i), 
                    pout_fund_data=pout_fund_data[i], 
                    pout_im3_data=self._resolve_batch_x(pout_im3_data, i), 
                    nazev=nazev, jednotka=jednotka, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(pout_fund_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        pin = self._to_numpy(pin_data)
        pout_f = self._to_numpy(pout_fund_data)
        pout_i = self._to_numpy(pout_im3_data)
        
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
        
        # Zabalení hodnot pro extrakční (bezhlavý) režim a CSV tabulky
        vysledek = {
            "linear_gain_dB": q_f,
            "iip3": iip3,
            "oip3": oip3
        }
        
        # --- 5. VYKRESLENÍ GRAFIKY (Němé značky a extrapolace) ---
        if draw_markers and self.fig is not None:
            # Tečkovaná linie základního signálu (Směrnice 1:1)
            self.fig.add_trace(go.Scatter(
                x=x_ideal, y=y_ideal_fund, mode='lines', 
                line=dict(color='gray', width=2, dash='dot'), showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Tečkovaná linie rušení IM3 (Směrnice 3:1)
            self.fig.add_trace(go.Scatter(
                x=x_ideal, y=y_ideal_im3, mode='lines', 
                line=dict(color='gray', width=2, dash='dot'), showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Zvýraznění samotného teoretického bodu IP3 (Oranžová Hvězda)
            self.fig.add_trace(go.Scatter(
                x=[iip3], y=[oip3], mode='markers',
                marker=dict(symbol='star', size=12, color='orange', line=dict(color='white', width=1)),
                showlegend=False, hoverinfo='skip'
            ), row=row, col=col)
            
            # Zaměřovací osy přesně na střed křížení
            self.fig.add_vline(x=iip3, line_dash="dash", line_color="orange", opacity=0.5, row=row, col=col)
            self.fig.add_hline(y=oip3, line_dash="dash", line_color="orange", opacity=0.5, row=row, col=col)

        # --- 6. INFORMAČNÍ BOX ---
        if draw_text and self.fig is not None:
            text_box = (f"<b>{nazev}</b><br>"
                        f"Zisk (Linear): {q_f:.2f} dB<br>"
                        f"<b>IIP3: {iip3:.2f} {jednotka}</b><br>"
                        f"<b>OIP3: {oip3:.2f} {jednotka}</b>")
                        
            # Využití sdíleného formátování textu a pozadí s úpravou barvy rámečku na oranžovou
            style_ip3 = self.style_annot.copy()
            style_ip3["bordercolor"] = "orange"
            
            self.fig.add_annotation(
                x=iip3, y=oip3,
                text=text_box, 
                showarrow=True, arrowcolor="orange", arrowhead=2, ax=-60, ay=-50,
                row=row, col=col, **style_ip3
            )

        return vysledek

    def analyzuj_pasmovou_zonu(self, x_data, y_data, threshold=-10.0, rezim="below", 
                               nazev="Pásmo", jednotka_x="Hz", barva="green", 
                               osa_x_log=False, odsazeni_y=-40, row=1, col=1,
                               draw_markers=True, draw_text=True):
        """
        Najde a vystínuje všechny úseky křivky, které splňují podmínku (pod/nad prahem).
        Vypočítá šířku nejširšího nalezeného pásma (BW) a jeho střední frekvenci.
        Podporuje dávkové zpracování pro nalezení pásem na mnoha křivkách najednou.
        """
        # --- 0. DETEKCE DÁVKOVÉHO ZPRACOVÁNÍ (Batching) ---
        if self._is_batch(y_data):
            return [
                self.analyzuj_pasmovou_zonu(
                    x_data=self._resolve_batch_x(x_data, i), 
                    y_data=y_data[i], 
                    threshold=threshold, rezim=rezim, 
                    nazev=nazev, jednotka_x=jednotka_x, barva=barva, 
                    osa_x_log=osa_x_log, odsazeni_y=odsazeni_y, row=row, col=col,
                    draw_markers=draw_markers, draw_text=draw_text
                ) for i in range(len(y_data))
            ]

        # --- 1. PŘÍPRAVA DAT (Normalizace) ---
        x = self._to_numpy(x_data)
        y = self._to_numpy(y_data)
        
        # 1. IDENTIFIKACE STAVU V KAŽDÉM BODĚ (Jsme v pásmu?)[cite: 1]
        in_zone_mask = (y <= threshold) if rezim == "below" else (y >= threshold)
        
        # 2. HLEDÁNÍ PRŮSEČÍKŮ (Místa, kde se maska mění z True na False a naopak)[cite: 1]
        edges = np.where(in_zone_mask[:-1] != in_zone_mask[1:])[0]
        
        crossings_x = []
        for idx in edges:
            x0, x1 = x[idx], x[idx+1]
            y0, y1 = y[idx], y[idx+1]
            # Lineární interpolace pro nalezení zcela přesného X, kde Y = threshold[cite: 1]
            if y1 != y0:
                x_c = x0 + (threshold - y0) * (x1 - x0) / (y1 - y0)
            else:
                x_c = x0
            crossings_x.append(x_c)
            
        # 3. SESTAVENÍ INTERVALŮ[cite: 1]
        intervals = []
        in_zone = in_zone_mask[0]
        current_start = x[0] if in_zone else None
        
        cross_idx = 0
        for idx in edges:
            xc = crossings_x[cross_idx]
            cross_idx += 1
            
            if in_zone:
                intervals.append((current_start, xc)) # Konec zóny[cite: 1]
                in_zone = False
            else:
                current_start = xc # Začátek nové zóny[cite: 1]
                in_zone = True
                
        if in_zone:
            intervals.append((current_start, x[-1])) # Zóna sahá až na konec grafu[cite: 1]

        # Připravíme defaultní slovník pro případ selhání nebo absence pásma
        vysledek = {"max_bw": None, "f_c": None, "start": None, "end": None, "all_intervals": intervals}

        if not intervals:
            print(f"Varování ({nazev}): Křivka nikdy nedosáhla podmínky {rezim} {threshold}.")
            return vysledek

        # --- 2. MATEMATIKA (Hledání nejširšího pásma) ---
        nejdelsi_interval = None
        max_bw = 0
        
        for start, end in intervals:
            bw = end - start
            if bw > max_bw:
                max_bw = bw
                nejdelsi_interval = (start, end)
                
        # Zápis vypočítaných hodnot do výsledkového slovníku
        if nejdelsi_interval:
            stred_x = nejdelsi_interval[0] + (max_bw / 2)
            vysledek.update({
                "max_bw": max_bw, "f_c": stred_x, 
                "start": nejdelsi_interval[0], "end": nejdelsi_interval[1]
            })

        # --- 3. VYKRESLENÍ GRAFIKY (Stínování a ohraničení zón) ---
        if draw_markers and self.fig is not None:
            # Horizontální limitní čára[cite: 1]
            self.fig.add_hline(y=threshold, line_dash="dash", line_color=barva, opacity=0.8, row=row, col=col)
            
            for start, end in intervals:
                # Vykreslení stínovaného obdélníku přes každé vyhovující pásmo[cite: 1]
                self.fig.add_vrect(
                    x0=start, x1=end, 
                    fillcolor=barva, opacity=0.15, 
                    layer="below", line_width=0,
                    row=row, col=col
                )
                # Svislé čáry ohraničující zónu[cite: 1]
                self.fig.add_vline(x=start, line_dash="dot", line_color=barva, opacity=0.6, row=row, col=col)
                self.fig.add_vline(x=end, line_dash="dot", line_color=barva, opacity=0.6, row=row, col=col)

        # --- 4. INFORMAČNÍ BOX (Pro nejširší pásmo) ---
        if draw_text and self.fig is not None and nejdelsi_interval:
            start, end = nejdelsi_interval
            
            str_bw = self.format_eng(max_bw, jednotka_x)
            str_fc = self.format_eng(stred_x, jednotka_x)
            str_start = self.format_eng(start, jednotka_x)
            str_end = self.format_eng(end, jednotka_x)
            
            # Umístění boxu na limitní čáru (Threshold)[cite: 1]
            x_pos = np.log10(stred_x) if osa_x_log else stred_x
            
            text_box = (f"<b>{nazev}</b><br>"
                        f"Meze: {str_start} až {str_end}<br>"
                        f"Střed (f_c): {str_fc}<br>"
                        f"<b>Šířka (BW): {str_bw}</b>")
                        
            # Využití sdíleného formátování z __init__
            style_zone = self.style_annot.copy(); style_zone["bordercolor"] = barva
            
            self.fig.add_annotation(
                x=x_pos, y=threshold,
                text=text_box, 
                showarrow=True, arrowcolor=barva, arrowhead=2, ay=odsazeni_y,
                row=row, col=col, **style_zone
            )

        return vysledek