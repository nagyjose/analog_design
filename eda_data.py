import os
import copy
import pandas as pd
import numpy as np
from spyci import spyci
from typing import List, Dict, Any, Callable

class NgspiceParser:
    """Parser pro spolehlivý převod Ngspice .raw souborů do Pandas DataFrame."""
    
    @staticmethod
    def read_raw(filepath: str) -> List[pd.DataFrame]:
        """
        Načte .raw soubor. Automaticky detekuje, zda obsahuje jeden běh (PVT) 
        nebo více běhů (Monte Carlo), a vždy vrátí pole DataFramů.
        Komplexní data (AC analýza) automaticky rozkládá na magnitudu, dB a fázi.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"RAW soubor {filepath} neexistuje.")
            
        # 1. Načtení hrubých dat přes spyci
        raw_data = spyci.load_raw(filepath)
        
        # 2. Normalizace struktury spyci do iterovatelného pole
        plots = []
        if isinstance(raw_data, dict):
            if 'plots' in raw_data:
                plots = raw_data['plots']
            else:
                plots = [raw_data]
        elif isinstance(raw_data, list):
            plots = raw_data
            
        dataframes = []
        
        # 3. Iterativní převod každého plotu (iterace) na DataFrame
        for plot in plots:
            df = pd.DataFrame()
            values = plot.get('values', {})
            
            for col_name, val_array in values.items():
                if np.iscomplexobj(val_array):
                    # Rozklad pro frekvenční charakteristiky
                    df[f"{col_name}_mag"] = np.abs(val_array)
                    
                    with np.errstate(divide='ignore', invalid='ignore'):
                        df[f"{col_name}_dB"] = 20 * np.log10(np.abs(val_array))
                        
                    df[f"{col_name}_phase"] = np.angle(val_array, deg=True)
                else:
                    # Standardní reálná čísla (DC, Transient)
                    df[col_name] = val_array.real
                    
            dataframes.append(df)
            
        return dataframes


class SimulationDataSet:
    """
    Strukturovaný datový sklad pro výsledky vícenásobných běhů.
    Připravuje kategorizovaná data pro vykreslování v eda_plot.
    """
    def __init__(self):
        # Interně ukládáme jako seznam slovníků. Každý slovník = 1 dokončená křivka/iterace.
        self.runs: List[Dict[str, Any]] = [] 
        
    def add_run(self, run_id: str, params: dict, dfs: List[pd.DataFrame]):
        """
        Uloží data z jednoho běhu enginu. Pokud engine vyprodukoval více grafů 
        (Monte Carlo), rozbalí je do nezávislých záznamů pro snadné filtrování.
        """
        is_monte_carlo = len(dfs) > 1
        
        for i, df in enumerate(dfs):
            # Pro Monte Carlo vytvoříme sub-ID (např. run_0012_mc_0)
            iter_run_id = f"{run_id}_mc_{i}" if is_monte_carlo else run_id
            
            self.runs.append({
                'run_id': iter_run_id,
                'params': copy.deepcopy(params),
                'is_mc': is_monte_carlo,
                'mc_iteration': i if is_monte_carlo else 0,
                'data': df
            })
            
    def load_engine_results(self, engine_results: List[Dict[str, Any]]):
        """
        Dávkové načtení všech výsledků vygenerovaných třídou NgspiceRunner (eda_engine).
        Očekává pole slovníků obsahujících 'status', 'raw_path' a 'params'.
        """
        for result in engine_results:
            if result.get("status") == "OK" and result.get("raw_path"):
                raw_path = str(result["raw_path"])
                try:
                    # Zpracování přes normalizovaný parser
                    dfs = NgspiceParser.read_raw(raw_path)
                    self.add_run(run_id=f"run_{result['task_idx']:04d}", params=result["params"], dfs=dfs)
                except Exception as e:
                    print(f"⚠️ Chyba při parsování {raw_path}: {e}")
        
    def filter_runs(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Databázový dotaz nad simulacemi[cite: 3]. 
        Vrátí seznam běhů, které odpovídají zadaným kritériím.
        """
        filtered = []
        for run in self.runs:
            match = True
            for klíč, požadovaná_hodnota in kwargs.items():
                # Kontrola čistého klíče i Ngspice tagu
                skutecna_hodnota = run['params'].get(klíč) or run['params'].get(f"{{{klíč}}}")
                
                if str(skutecna_hodnota) != str(požadovaná_hodnota):
                    match = False
                    break
                    
            if match:
                filtered.append(run)
                
        return filtered

    def get_all_runs(self) -> List[Dict[str, Any]]:
        """Vrátí všechny běhy[cite: 3]. Vhodné pro hromadné vykreslování v eda_plot.py."""
        return self.runs

    def add_derived_vector(self, new_column_name: str, func: Callable[[pd.DataFrame], pd.Series]) -> None:
        """
        Dynamicky vypočítá nový signál (vektor) napříč všemi běhy v datasetu.
        Využívá Pandas vektorizaci pro extrémní rychlost.
        
        Příklad: dataset.add_derived_vector("gm", lambda df: np.gradient(df["i(vdd)"], df["vgs"]))
        """
        success_count = 0
        error_msgs = set()

        for run in self.runs:
            df = run['data']
            try:
                run['data'][new_column_name] = func(df)
                success_count += 1
            except Exception as e:
                error_msgs.add(f"Chyba výpočtu v runu {run['run_id']}: {e}")

        if error_msgs:
            print(f"⚠️ Výpočet '{new_column_name}' se nezdařil:")
            for msg in error_msgs:
                print(f"  - {msg}")
        else:
            print(f"✅ Odvozený vektor '{new_column_name}' úspěšně přidán do {success_count} běhů.")

    def extract_metrics(self, metrics: Dict[str, Callable[[pd.DataFrame], float]]) -> pd.DataFrame:
        """
        Aplikuje extrakční funkce na každý běh a spojí výsledky s parametry (metadaty).
        Vrací čistou 2D tabulku (Pandas DataFrame) připravenou pro vykreslení.
        
        :param metrics: Slovník, kde klíč je název metriky a hodnota je Lambda funkce vracející skalár.
        """
        extracted_data = []
        
        for run in self.runs:
            # 1. Zkopírování metadat (PVT parametry, Sweep parametry)
            row_data = {}
            
            # Očistíme názvy parametrů od Ngspice tagů pro hezčí tabulku (např. "{W}" -> "W")
            for param_key, param_value in run['params'].items():
                clean_key = param_key.strip("{}")
                row_data[clean_key] = param_value
                
            # Přidání Monte Carlo identifikátorů, pokud existují
            if run.get('is_mc'):
                row_data['mc_iteration'] = run.get('mc_iteration', 0)
                
            # 2. Extrakce skalárních metrik z naměřených vektorů
            df = run['data']
            for metric_name, metric_func in metrics.items():
                try:
                    # Funkce musí vrátit jedno číslo (skalár)
                    row_data[metric_name] = metric_func(df)
                except Exception:
                    # Pokud se něco pokazí (např. křivka neprotnula osu), vložíme NaN (Not a Number)
                    row_data[metric_name] = np.nan
                    
            extracted_data.append(row_data)
            
        # 3. Sloučení do jediné mocné Pandas tabulky
        return pd.DataFrame(extracted_data)