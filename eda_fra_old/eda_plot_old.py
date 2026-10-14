import plotly.graph_objects as go
from plotly.subplots import make_subplots

class AutoPlotter:
    """
    Automatický generátor interaktivních reportů z objektů SimulationDataSet.
    Řeší konzistenci barev, legend a formátování na SI jednotky.
    """
    def __init__(self, theme="plotly_dark"):
        self.theme = theme
        
        # 1. Inteligentní paleta
        # Pokud skript narazí na standardní názvy rohů, vynutí průmyslové barvy
        self.corner_colors = {
            "mos_tt": "#2ca02c", # Zelená (Typický ideál)
            "mos_ss": "#d62728", # Červená (Pomalý roh - limitní)
            "mos_ff": "#1f77b4", # Modrá (Rychlý roh)
        }
        
        # Paleta pro případ, že simulujeme něco jiného (např. Monte Carlo, nebo parametrický sweep)
        self.default_palette = [
            "#ff7f0e", "#9467bd", "#8c564b", "#e377c2", 
            "#7f7f7f", "#bcbd22", "#17becf", "#f1c40f"
        ]

    def _get_color(self, params: dict, run_index: int) -> str:
        """Přiřadí barvu na základě rohu, případně vytáhne barvu z palety."""
        # Podpora pro různé formáty klíče, např. '{CORNER}' nebo 'CORNER'
        corner = params.get("{CORNER}") or params.get("CORNER") or params.get("{CORNER_MOS}")
        
        if corner and corner in self.corner_colors:
            return self.corner_colors[corner]
            
        return self.default_palette[run_index % len(self.default_palette)]

    def plot_signals(self, dataset, signals: list, x_axis: str = "time", title: str = "Výsledky simulace") -> go.Figure:
        """
        Vykreslí seznam signálů z datasetu do podgrafů.
        
        :param dataset: Instance SimulationDataSet (z eda_data.py)
        :param signals: Seznam sloupců k vykreslení, např. ['v(out)', 'v(out)_dB']
        :param x_axis: Sloupec použitý jako osa X (typicky 'time' pro .tran, nebo 'v-sweep' pro .dc)
        """
        num_plots = len(signals)
        
        # Automatické vytvoření mřížky (řádky podle počtu signálů)
        fig = make_subplots(
            rows=num_plots, cols=1, 
            shared_xaxes=True, 
            vertical_spacing=0.05,
            subplot_titles=signals
        )
        
        runs = dataset.get_all_runs()
        
        for run_index, run in enumerate(runs):
            df = run['data']
            run_id = run['run_id']
            params = run['params']
            
            # Název pro legendu vytvoříme chytře (např. "mos_tt | 125C")
            legend_name = run_id
            
            # Zjištění barvy
            color = self._get_color(params, run_index)
            
            # Kontrola existence osy X
            if x_axis not in df.columns:
                # Ngspice někdy DC osu pojmenuje podle zdroje, např. 'v1' místo 'v-sweep'
                # Zkusíme fallback na první sloupec z DF, pokud uživatel zadal špatnou osu
                x_axis = df.columns[0]
                
            # --- Vykreslení všech signálů pro aktuální běh ---
            for plot_index, signal in enumerate(signals):
                if signal not in df.columns:
                    print(f"Varování: Signál '{signal}' v běhu {run_id} chybí.")
                    continue
                    
                # Do legendy se zapíšeme JEN u prvního grafu (aby tam roh 'mos_tt' nebyl 3x)
                show_legend = True if plot_index == 0 else False
                
                fig.add_trace(
                    go.Scatter(
                        x=df[x_axis], 
                        y=df[signal], 
                        mode='lines', 
                        name=legend_name,
                        legendgroup=run_id, # MAGIE: Spojí tento běh přes všechny podgrafy!
                        line=dict(color=color, width=2),
                        showlegend=show_legend
                    ),
                    row=plot_index + 1, col=1
                )
                
                # Automatické SI formátování pro osu Y (V, A, S atd.)
                fig.update_yaxes(exponentformat="SI", row=plot_index + 1, col=1)

        # Automatické SI formátování pro osu X (nastavuje se jen u nejspodnějšího grafu)
        fig.update_xaxes(title_text=x_axis, exponentformat="SI", row=num_plots, col=1)
        
        # Globální layout
        fig.update_layout(
            title=title,
            height=300 * num_plots + 100, # Výška se přizpůsobí počtu grafů
            template=self.theme,
            hovermode="x unified" # Zapne vertikální čáru odečítající vše naráz
        )
        
        return fig