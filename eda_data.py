import os
import pandas as pd
import numpy as np
from spyci import spyci

class NgspiceParser:
    """Parser pro bleskový převod Ngspice .raw souborů do Pandas DataFrame."""
    
    @staticmethod
    def read_raw(filepath: str) -> pd.DataFrame:
        """
        Načte .raw soubor. Pokud detekuje AC analýzu (komplexní čísla),
        automaticky vygeneruje sloupce pro Decibely (_dB) a Fázi ve stupních (_phase).
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"RAW soubor {filepath} neexistuje.")
            
        # spyci načte raw soubor do slovníku
        data = spyci.load_raw(filepath)
        df = pd.DataFrame()
        
        # Iterujeme přes všechny uložené vektory (např. 'time', 'v(out)', 'i(vdd)')
        for col_name, values in data['values'].items():
            
            # Detekce AC analýzy (Ngspice ukládá AC výstupy jako komplexní pole)
            if np.iscomplexobj(values):
                # Absolutní hodnota (Volt / Ampér)
                df[f"{col_name}_mag"] = np.abs(values)
                
                # Zisk v dB (s ochranou proti log(0))
                with np.errstate(divide='ignore', invalid='ignore'):
                    df[f"{col_name}_dB"] = 20 * np.log10(np.abs(values))
                    
                # Fáze ve stupních (příprava pro Bode Plot)
                df[f"{col_name}_phase"] = np.angle(values, deg=True)
            else:
                # Standardní reálná čísla pro Transient (DC / TRAN)
                df[col_name] = values.real
                
        return df


class SimulationDataSet:
    """
    Strukturovaný datový sklad pro výsledky vícenásobných běhů (PVT, Monte Carlo, Sweeps).
    Umožňuje snadné dotazování a hromadné zpracování.
    """
    
    def __init__(self):
        # Interně ukládáme jako seznam slovníků. Každý slovník = 1 dokončená simulace.
        self.runs = [] 
        
    def add_run(self, run_id: str, params: dict, df: pd.DataFrame):
        """
        Uloží data z jednoho běhu včetně jeho kontextu (např. teploty, modelu).
        :param params: Původní slovník proměnných z eda_engine (např. {'{TEMP}': '125', '{CORNER}': 'mos_ff'})
        """
        self.runs.append({
            'run_id': run_id,
            'params': params,
            'data': df
        })
        
    def filter_runs(self, **kwargs) -> list:
        """
        Databázový dotaz nad simulacemi. 
        Vrátí seznam běhů, které odpovídají zadaným kritériím.
        
        Příklad: dataset.filter_runs(TEMP=125, CORNER="mos_tt")
        """
        filtered = []
        for run in self.runs:
            match = True
            for klíč, požadovaná_hodnota in kwargs.items():
                
                # Hledáme, jak je klíč uložen. Může to být čistý "TEMP" nebo spice tag "{TEMP}".
                # Zkusíme obě varianty.
                skutecna_hodnota = run['params'].get(klíč) or run['params'].get(f"{{{klíč}}}")
                
                # Převedeme na string pro bezpečné porovnání (např. int 125 vs str "125")
                if str(skutecna_hodnota) != str(požadovaná_hodnota):
                    match = False
                    break
                    
            if match:
                filtered.append(run)
                
        return filtered

    def get_all_runs(self) -> list:
        """Vrátí všechny běhy. Vhodné pro hromadné vykreslování v eda_plot.py."""
        return self.runs