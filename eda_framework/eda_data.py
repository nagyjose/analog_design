import os
import copy
import pandas as pd
import numpy as np
import scipy.stats as st

# Oprava zpětné kompatibility pro knihovnu spyci v NumPy 2.0+
np.complex_ = np.complex128
np.float_ = np.float64

from spyci import spyci
from typing import List, Dict, Any, Callable

class NgspiceParser:
    """
    Nativní parser pro převod Ngspice ASCII .raw souborů do Pandas DataFrame.
    Podporuje single-run (DC/AC/Tran) i multi-run (Monte Carlo) .raw soubory
    a automaticky vytváří aliasy pro proudy (v2#branch <-> i(v2)) i napětí (vg <-> v(vg)).
    """

    @staticmethod
    def _add_column_with_aliases(df: pd.DataFrame, col_name: str, var_type: str, val_array: np.ndarray):
        """Uloží vektor do DataFramu a vytvoří standardní SPICE aliasy."""
        clean_col = col_name.lower().strip()
        var_type = var_type.lower().strip()

        # Rozklad pro komplexní čísla (AC analýza) nebo reálná čísla (DC, Tran)
        def store(name: str, arr: np.ndarray):
            if np.iscomplexobj(arr):
                df[f"{name}_mag"] = np.abs(arr)
                with np.errstate(divide='ignore', invalid='ignore'):
                    df[f"{name}_dB"] = 20 * np.log10(np.abs(arr))
                df[f"{name}_phase"] = np.angle(arr, deg=True)
            else:
                df[name] = np.real(arr)

        # 1. Uložení pod původním názvem z .raw souboru
        store(clean_col, val_array)

        # 2. Automatické aliasy pro proudy: 'v2#branch' <-> 'i(v2)'
        if clean_col.endswith("#branch"):
            src_name = clean_col[:-7]  # odstraní '#branch'
            store(f"i({src_name})", val_array)
        elif clean_col.startswith("i(") and clean_col.endswith(")"):
            src_name = clean_col[2:-1]
            store(f"{src_name}#branch", val_array)

        # 3. Automatické aliasy pro napětí: 'vg' <-> 'v(vg)' a 'v(v-sweep)' <-> 'v-sweep'
        elif "voltage" in var_type or clean_col.startswith("v("):
            if clean_col.startswith("v(") and clean_col.endswith(")"):
                inner = clean_col[2:-1]
                store(inner, val_array)
            elif clean_col not in ("time", "frequency", "v-sweep", "i-sweep"):
                store(f"v({clean_col})", val_array)

    @staticmethod
    def read_raw(filepath: str) -> List[pd.DataFrame]:
        """
        Načte .raw soubor. Automaticky detekuje, zda obsahuje jeden běh (PVT) 
        nebo více běhů (Monte Carlo), a vždy vrátí pole DataFramů.
        Komplexní data (AC analýza) automaticky rozkládá na magnitudu, dB a fázi.
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"RAW soubor {filepath} neexistuje.")
            
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        dataframes = []
        n_lines = len(lines)
        idx = 0

        while idx < n_lines:
            line = lines[idx].strip()

            # Hledáme začátek bloku (Plotname:)
            if line.startswith("Plotname:"):
                plotname = line.split(":", 1)[1].strip()
                is_complex = False
                no_vars = 0
                no_points = 0
                variables = []

                idx += 1
                # Čtení hlavičky plotu
                while idx < n_lines:
                    hline = lines[idx].strip()
                    if hline.startswith("Flags:"):
                        is_complex = "complex" in hline.lower()
                    elif hline.startswith("No. Variables:"):
                        no_vars = int(hline.split(":", 1)[1].strip())
                    elif hline.startswith("No. Points:"):
                        no_points = int(hline.split(":", 1)[1].strip())
                    elif hline.startswith("Variables:"):
                        idx += 1
                        for _ in range(no_vars):
                            parts = lines[idx].strip().split()
                            # Formát řádku: <index> <name> <type>
                            var_name = parts[1]
                            var_type = parts[2] if len(parts) > 2 else ""
                            variables.append((var_name, var_type))
                            idx += 1
                        continue
                    elif hline.startswith("Values:"):
                        idx += 1
                        break
                    idx += 1

                # Čtení samotných číselných hodnot (Values:)
                raw_tokens = []
                expected_tokens = no_points * no_vars
                while idx < n_lines and len(raw_tokens) < expected_tokens:
                    vline = lines[idx].strip()
                    if vline:
                        # Poslední položka na řádku je vždy hodnota (na 1. řádku bodu předchází index bodu)
                        raw_tokens.append(vline.split()[-1])
                    idx += 1

                # Přeskočíme interní tabulku konstant Ngspice ('Constants')
                if "constant" in plotname.lower() or len(raw_tokens) < expected_tokens:
                    continue

                # Převod na matici (no_points x no_vars)
                if is_complex:
                    complex_vals = [
                        complex(float( p[0] ), float( p[1] ))
                        for token in raw_tokens
                        for p in [token.split(",")]
                    ]
                    data_matrix = np.array(complex_vals, dtype=np.complex128).reshape((no_points, no_vars))
                else:
                    data_matrix = np.array(raw_tokens, dtype=np.float64).reshape((no_points, no_vars))

                # Sestavení DataFramu s aliasy
                df = pd.DataFrame()
                for v_i, (var_name, var_type) in enumerate(variables):
                    NgspiceParser._add_column_with_aliases(df, var_name, var_type, data_matrix[:, v_i])

                dataframes.append(df)
            else:
                idx += 1

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
            except KeyError as e:
                dostupne = list(df.columns)
                error_msgs.add(f"Chybí sloupec {e} (Dostupné sloupce: {dostupne})")
            except Exception as e:
                error_msgs.add(f"Chyba výpočtu: {e}")

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

    def get_signal(self, signal_name: str) -> list:
        """
        Vrátí dávku (batch) 1D Numpy polí pro daný signál napříč všemi běhy.
        Extrémně zjednodušuje předávání dat do SignalAnalyzeru.
        """
        batch = []
        for run in self.runs:
            if signal_name in run['data']:
                # Využije to numpy pro bezpečný převod
                batch.append(run['data'][signal_name].to_numpy())
        return batch

    @staticmethod
    def analyze_monte_carlo_distribution(df: pd.DataFrame, column_name: str, 
                                        lsl: float = None, usl: float = None,
                                        fit_dists: list = ["norm"], 
                                        use_kde: bool = True) -> dict:
        """
        Statistická analýza dat s integrací limitů pro výpočet výtěžnosti (Yield).
        Vrací jak empirickou výtěžnost (z hrubých dat), tak teoretickou pro každé zvolené rozdělení.
        """
        # 1. Extrakce a očištění dat
        data = df[column_name].dropna().values
        celkem_behu = len(data)
        
        if celkem_behu == 0:
            raise ValueError(f"Sloupec '{column_name}' je prázdný.")

        # 2. Základní momenty
        mu_standard = np.mean(data)
        sigma_standard = np.std(data, ddof=1)
        
        # 3. Nastavení univerzální osy X
        x_min, x_max = np.min(data), np.max(data)
        rozptyl = x_max - x_min
        x_curve = np.linspace(x_min - 0.1*rozptyl, x_max + 0.1*rozptyl, 200)
        
        curve_df = pd.DataFrame({"x": x_curve})
        
        # ==========================================
        # A) EMPIRICKÝ YIELD (Přímo z hrubých dat)
        # ==========================================
        passed_empirical = celkem_behu
        if lsl is not None or usl is not None:
            valid_mask = np.ones(celkem_behu, dtype=bool)
            if lsl is not None:
                valid_mask &= (data >= lsl)
            if usl is not None:
                valid_mask &= (data <= usl)
            passed_empirical = np.sum(valid_mask)
        
        yield_empirical_pct = (passed_empirical / celkem_behu) * 100.0

        # Inicializace výstupního slovníku
        results = {
            "runs": celkem_behu,
            "mu_standard": mu_standard,
            "sigma_standard": sigma_standard,
            "empirical": {
                "passed": passed_empirical,
                "yield_pct": yield_empirical_pct
            },
            "fitted_models": {},
            "curve_data": None
        }

        # ==========================================
        # B) KŘIVKA KDE (Vizuální reprezentace)
        # ==========================================
        if use_kde:
            kde_estimator = st.gaussian_kde(data)
            curve_df["pdf_kde"] = kde_estimator(x_curve)
            
        # ==========================================
        # C) TEORETICKÝ YIELD PRO ZVOLENÁ ROZDĚLENÍ
        # ==========================================
        for dist_name in fit_dists:
            try:
                distribution = getattr(st, dist_name)
                params = distribution.fit(data)
                
                # 1. Křivka pro zobrazení
                curve_df[f"pdf_{dist_name}"] = distribution.pdf(x_curve, *params)
                
                # 2. Výpočet plochy pod křivkou pomocí CDF
                theoretical_yield = 1.0
                if lsl is not None or usl is not None:
                    prob_upper = distribution.cdf(usl, *params) if usl is not None else 1.0
                    prob_lower = distribution.cdf(lsl, *params) if lsl is not None else 0.0
                    theoretical_yield = prob_upper - prob_lower
                
                # Uložení výsledků pro toto konkrétní rozdělení
                results["fitted_models"][dist_name] = {
                    "params": params, # Např. mu a sigma pro normální rozdělení
                    "yield_pct": theoretical_yield * 100.0
                }
                
            except AttributeError:
                print(f"⚠️ SciPy rozdělení '{dist_name}' neexistuje.")
            except Exception as e:
                print(f"⚠️ Nelze analyzovat rozdělení '{dist_name}': {e}")

        results["curve_data"] = curve_df
        return results