import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.colors as pcolors
import pandas as pd
import numpy as np

class EDAPlotter:
    """
    Pokročilý vizualizační modul pro EDA framework.
    Pracuje v modulárním režimu: vygenerujete plátno a následně do něj přidáváte grafy a tabulky.
    """
    def __init__(self, theme: str = "plotly_dark"):
        self.theme = theme
        
        # Předdefinované palety a styly pro automatické mapování
        self.color_palette = pcolors.qualitative.Plotly + pcolors.qualitative.D3
        self.dash_styles = ['solid', 'dash', 'dot', 'dashdot', 'longdash']
        
        # Sledování již přidaných legend pro celý dashboard, abychom zamezili duplicitám napříč subploty
        self.added_legends = set()

    def create_dashboard(self, rozlozeni: list, title_text="EDA Report") -> go.Figure:
        """
        Vytvoří plátno na základě jednoduché textové matice.
        Příklad: 
        [
            [("graf", "AC Odezva"), ("mc", "Monte Carlo")],
            [("tabulka", "Hrany"),  ("tabulka", "Statistika")]
        ]
        """
        rows = len(rozlozeni)
        cols = len(rozlozeni[0]) if rows > 0 else 0
        
        # Překladač našeho lidského formátu do jazyka Plotly
        typova_mapa = {
            "graf": {"type": "xy"},
            "mc": {"secondary_y": True},
            "tabulka": {"type": "table"}
        }
        
        specs = []
        titles = []
        for radek in rozlozeni:
            spec_radek = []
            for typ, nadpis in radek:
                spec_radek.append(typova_mapa.get(typ.lower(), {"type": "xy"}))
                titles.append(nadpis)
            specs.append(spec_radek)
            
        fig = make_subplots(rows=rows, cols=cols, specs=specs, subplot_titles=titles, vertical_spacing=0.08)
        fig.update_layout(title=title_text, template=self.theme, hovermode="x unified", height=350 * rows + 100)
        return fig

    def _clean_key(self, key: str) -> str:
        """Očistí Ngspice tag od složených závorek pro hezčí popisky (např. '{TEMP}' -> 'TEMP')."""
        return key.strip("{}")

    def _build_legend_name(self, params: dict, hue_param: str = None, dash_param: str = None) -> str:
        """Sestaví dynamický název do legendy (např. 'TEMP: 125 | MOS: ss')."""
        parts = []
        if hue_param and hue_param in params:
            parts.append(f"{self._clean_key(hue_param)}: {params[hue_param]}")
        if dash_param and dash_param in params:
            parts.append(f"{self._clean_key(dash_param)}: {params[dash_param]}")
            
        return " | ".join(parts) if parts else "Výchozí běh"
        
    def _get_mapped_aesthetics(self, runs, hue_param, dash_param):
        """Vygeneruje konzistentní mapování barev a typů čar pro celou sadu dat."""
        unique_hues = list(set([str(r['params'].get(hue_param, 'N/A')) for r in runs])) if hue_param else ['N/A']
        unique_dashes = list(set([str(r['params'].get(dash_param, 'N/A')) for r in runs])) if dash_param else ['N/A']
        
        color_map = {val: self.color_palette[i % len(self.color_palette)] for i, val in enumerate(unique_hues)}
        dash_map = {val: self.dash_styles[i % len(self.dash_styles)] for i, val in enumerate(unique_dashes)}
        return color_map, dash_map

    def add_pvt_corridor(self, fig: go.Figure, dataset, signal: str, x_axis: str = "time", 
                         row: int = 1, col: int = 1, 
                         hue_param: str = None, dash_param: str = None):
        """
        Vykreslí rodinu křivek (PVT koridor) pro konkrétní signál do určené buňky.
        """
        runs = dataset.get_all_runs()
        if not runs:
            print(f"Varování: Nelze vykreslit PVT koridor, dataset je prázdný.")
            return

        color_map, dash_map = self._get_mapped_aesthetics(runs, hue_param, dash_param)

        for run in runs:
            df = run['data']
            params = run['params']
            
            if signal not in df.columns or x_axis not in df.columns:
                continue
                
            hue_val = str(params.get(hue_param, 'N/A'))
            dash_val = str(params.get(dash_param, 'N/A'))
            
            line_color = color_map.get(hue_val, self.color_palette[0])
            line_dash = dash_map.get(dash_val, 'solid')
            
            legend_name = self._build_legend_name(params, hue_param, dash_param)
            
            # Zapíšeme do legendy pouze pokud jsme to s takovými parametry ještě neviděli v celém dashboardu
            show_legend = legend_name not in self.added_legends
            
            fig.add_trace(
                go.Scatter(
                    x=df[x_axis], 
                    y=df[signal], 
                    mode='lines', 
                    name=legend_name,
                    legendgroup=legend_name, # Skrývání zapíná a vypíná celou rodinu naráz
                    showlegend=show_legend,
                    line=dict(color=line_color, dash=line_dash, width=2.0),
                    hovertemplate=f"{legend_name}<br>{x_axis}: %{{x}}<br>{signal}: %{{y}}<extra></extra>"
                ),
                row=row, col=col
            )
            self.added_legends.add(legend_name)

        # Formátování konkrétních os pro danou buňku
        fig.update_xaxes(title_text=x_axis, exponentformat="SI", showgrid=True, row=row, col=col)
        fig.update_yaxes(title_text=signal, exponentformat="SI", showgrid=True, row=row, col=col)

    def add_monte_carlo(self, fig: go.Figure, raw_data: pd.Series, stats_dict: dict, 
                        row: int, col: int, column_name: str = "Hodnota", 
                        lsl: float = None, usl: float = None):
        """
        Vykreslí histogram, scatter běhů a analytické křivky do určené buňky.
        Vyžaduje, aby daná buňka v plátně (gridu) byla inicializována s {"secondary_y": True}.
        """
        # Kontrola, zda máme co kreslit
        if raw_data is None or len(raw_data) == 0:
             return
             
        # 1. HISTOGRAM (Absolutní počty běhů - levá osa Y)
        fig.add_trace(go.Histogram(
            x=raw_data,
            name=f'{column_name} (Hist)',
            marker_color='gray',
            opacity=0.5,
            nbinsx=40,
            showlegend=False
        ), row=row, col=col, secondary_y=False)
        
        # 2. MRAČNO BODŮ (Scatter pro přesné zjištění outlierů - levá osa Y)
        odhad_max_poctu = len(raw_data) / 10
        y_jitter = np.random.uniform(0, odhad_max_poctu * 0.3, size=len(raw_data))
        
        fig.add_trace(go.Scatter(
            x=raw_data, y=y_jitter,
            mode='markers',
            name=f'{column_name} (Scatter)',
            marker=dict(size=4, color='rgba(255, 255, 255, 0.4)', line=dict(width=0.5, color='black')),
            hoverinfo="x",
            showlegend=False
        ), row=row, col=col, secondary_y=False)
        
        # 3. ANALYTICKÉ KŘIVKY (Hustota pravděpodobnosti - pravá osa Y)
        curve_df = stats_dict.get("curve_data")
        if curve_df is not None and "x" in curve_df.columns:
            x_vals = curve_df["x"]
            
            curve_styles = {
                "pdf_kde": {"name": "KDE", "color": "#1f77b4", "dash": "solid"},
                "pdf_norm": {"name": "Gauss", "color": "#d62728", "dash": "dash"},
                "pdf_lognorm": {"name": "LogNorm", "color": "#2ca02c", "dash": "dashdot"}
            }
            
            for c in curve_df.columns:
                if c.startswith("pdf_"):
                    style = curve_styles.get(c, {"name": c, "color": "#ff7f0e", "dash": "dot"})
                    
                    # Zabráníme duplikaci v legendě, pokud máme v gridu více Monte Carlo grafů
                    leg_name = f"{style['name']} ({column_name})"
                    show_leg = leg_name not in self.added_legends
                    
                    fig.add_trace(go.Scatter(
                        x=x_vals, y=curve_df[c],
                        mode='lines',
                        name=leg_name,
                        legendgroup=leg_name,
                        showlegend=show_leg,
                        line=dict(width=2.5, color=style["color"], dash=style["dash"])
                    ), row=row, col=col, secondary_y=True)
                    
                    self.added_legends.add(leg_name)
                    
        # 4. SPECIFIKAČNÍ LIMITY (LSL / USL)
        if lsl is not None:
            fig.add_vline(x=lsl, line_dash="dash", line_color="red", row=row, col=col)
            # Pomocný neviditelný scatter pro nápis, aby se nevytvářel problém s absolutními annotacemi napříč gridem
            fig.add_trace(go.Scatter(x=[lsl], y=[0], mode="text", text=["LSL"], textposition="top right", textfont=dict(color="red"), showlegend=False, hoverinfo='skip'), row=row, col=col, secondary_y=False)
            
        if usl is not None:
            fig.add_vline(x=usl, line_dash="dash", line_color="red", row=row, col=col)
            fig.add_trace(go.Scatter(x=[usl], y=[0], mode="text", text=["USL"], textposition="top left", textfont=dict(color="red"), showlegend=False, hoverinfo='skip'), row=row, col=col, secondary_y=False)
            
        # 5. INFORMAČNÍ BOX
        mu = stats_dict.get("mu_standard", 0)
        sigma = stats_dict.get("sigma_standard", 0)
        runs = stats_dict.get("runs", 0)
        yield_emp = stats_dict.get("empirical", {}).get("yield_pct", 100.0)
        
        yield_norm_str = ""
        if "fitted_models" in stats_dict and "norm" in stats_dict["fitted_models"]:
            yield_th = stats_dict["fitted_models"]["norm"]["yield_pct"]
            yield_norm_str = f"<br>Th(Gauss)= {yield_th:.2f} %"
            
        stats_text = (
            f"<b>{runs} běhů</b><br>"
            f"μ={mu:.3g} | σ={sigma:.3g}<br>"
            f"<b>Y={yield_emp:.2f} %</b>"
            f"{yield_norm_str}"
        )
        
        # Umístění relativně k aktuálnímu subplotu (xref="x domain", yref="y domain" vyžaduje zjištění správné osy z gridu)
        # Plotly generuje osy automaticky (x, x2, x3...), takže pro univerzálnost vložíme box pomocí Scatter textu do rohu grafu
        # Případně můžeme využít domain xref/yref, pokud chceme absolutní rohy
        
        # Lokální formátování os pro tuto buňku
        fig.update_xaxes(title_text=column_name, exponentformat="SI", showgrid=True, row=row, col=col)
        fig.update_yaxes(title_text="Count", secondary_y=False, showgrid=True, row=row, col=col)
        fig.update_yaxes(title_text="PDF", secondary_y=True, showgrid=False, row=row, col=col)

    def add_analysis_table(self, fig: go.Figure, analysis_data: list, row: int, col: int, 
                           dataset=None, meta_keys: list = None):
        """
        Vezme pole výsledků z analýzy (např. pole slovníků s parametry 'rise_time', 'overshoot' atd.), 
        přidá k nim metadata z datasetu a vykreslí je jako go.Table.
        Buňka musí být při tvorbě plátna inicializována s {"type": "table"}.
        """
        if not analysis_data:
            return
            
        df = pd.DataFrame(analysis_data)
        
        # Pokud máme dataset a chceme přidat kontext
        if dataset and meta_keys:
            runs = dataset.get_all_runs()
            if len(runs) == len(df):
                for key in reversed(meta_keys): # Přidáváme je na začátek tabulky
                    clean_key = self._clean_key(key)
                    vals = [r['params'].get(key) for r in runs]
                    df.insert(0, clean_key, vals)

        # Formátování čísel pro hezčí zobrazení (např. inženýrská notace 4 platné číslice)
        sloupce = []
        for c in df.columns:
            if pd.api.types.is_numeric_dtype(df[c]):
                sloupce.append(df[c].apply(lambda x: f"{x:.4g}" if pd.notnull(x) else ""))
            else:
                sloupce.append(df[c])

        # Sladění barev tabulky s vybraným tématem ("plotly_dark")
        is_dark = "dark" in self.theme
        barva_hlavicky = '#2c2c2c' if is_dark else '#e0e0e0'
        barva_bunek = '#1e1e1e' if is_dark else '#ffffff'
        font_hlavicka = '#ffffff' if is_dark else '#000000'
        font_bunky = 'lightgray' if is_dark else '#333333'

        fig.add_trace(
            go.Table(
                header=dict(
                    values=list(df.columns),
                    fill_color=barva_hlavicky,
                    align='left',
                    font=dict(color=font_hlavicka, size=12, family="Arial")
                ),
                cells=dict(
                    values=sloupce,
                    fill_color=barva_bunek,
                    align='left',
                    font=dict(color=font_bunky, size=11)
                )
            ),
            row=row, col=col
        )

    def add_mc_summary_table(self, fig: go.Figure, stats_dict: dict, row: int, col: int):
        """
        Automaticky převede statistický slovník z MC analýzy na čitelnou tabulku.
        Zcela skrývá Pandas před uživatelem.
        """
        if not stats_dict:
            return
            
        yield_emp = stats_dict.get("empirical", {}).get("yield_pct", 100.0)
        yield_norm = stats_dict.get("fitted_models", {}).get("norm", {}).get("yield_pct", float('nan'))
        
        # Interní sestavení tabulky
        summary_data = [
            {"Metrika": "Počet vzorků", "Hodnota": str(stats_dict.get("runs", 0))},
            {"Metrika": "Průměr (μ)", "Hodnota": f"{stats_dict.get('mu_standard', 0):.4g}"},
            {"Metrika": "Odchylka (σ)", "Hodnota": f"{stats_dict.get('sigma_standard', 0):.4g}"},
            {"Metrika": "Yield (Empirický)", "Hodnota": f"{yield_emp:.2f} %"},
            {"Metrika": "Yield (Teoretický Gauss)", "Hodnota": f"{yield_norm:.2f} %"}
        ]
        
        # Zavoláme naši již existující vykreslovací metodu
        self.add_analysis_table(fig, summary_data, row=row, col=col)