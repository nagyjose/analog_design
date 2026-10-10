import itertools
import copy
import uuid
import subprocess
import concurrent.futures
from dataclasses import dataclass
from typing import Tuple, Optional, List, Dict, Any, Union
from pathlib import Path

class BaseAnalysis:
    """Základní třída pro všechny typy Ngspice simulací."""
    def get_control_block(self, raw_filename: str) -> str:
        raise NotImplementedError("Metoda get_control_block musí být implementována v potomkovi.")

@dataclass
class DCAnalysis(BaseAnalysis):
    """
    Generátor pro DC Sweep.
    Příklad: sweep1=("vds", 0, 1.8, 0.01)
    """
    sweep1: Tuple[str, float, float, float]  # (zdroj, start, stop, krok)
    sweep2: Optional[Tuple[str, float, float, float]] = None # Volitelný sekundární sweep

    def get_control_block(self, raw_filename: str) -> str:
        # Sestavení příkazu pro první parametr
        cmd = f"dc {self.sweep1[0]} {self.sweep1[1]} {self.sweep1[2]} {self.sweep1[3]}"
        
        # Přidání druhého parametru, pokud je definován
        if self.sweep2:
            cmd += f" {self.sweep2[0]} {self.sweep2[1]} {self.sweep2[2]} {self.sweep2[3]}"
            
        return f"""
                .control
                {cmd}
                write {raw_filename} all
                .endc
                """

@dataclass
class ACAnalysis(BaseAnalysis):
    """
    Generátor pro AC frekvenční analýzu (Bode plot).
    Příklad: sweep_type="dec", points=10, f_start=1, f_stop=1e9
    """
    sweep_type: str  # "dec", "oct", "lin"
    points: int
    f_start: float
    f_stop: float

    def get_control_block(self, raw_filename: str) -> str:
        return f"""
                .control
                ac {self.sweep_type} {self.points} {self.f_start} {self.f_stop}
                write {raw_filename} all
                .endc
                """

@dataclass
class TranAnalysis(BaseAnalysis):
    """
    Generátor pro Transientní (časovou) analýzu.
    """
    t_step: float
    t_stop: float
    t_start: float = 0.0

    def get_control_block(self, raw_filename: str) -> str:
        return f"""
                .control
                tran {self.t_step} {self.t_stop} {self.t_start}
                write {raw_filename} all
                .endc
                """

@dataclass
class CustomAnalysis(BaseAnalysis):
    """
    Úniková cesta (Escape hatch) pro velmi specifické simulace (např. Monte Carlo, 
    S-parametry), kde si uživatel chce napsat .control blok ručně.
    """
    control_script: str

    def get_control_block(self, raw_filename: str) -> str:
        # Očekává se, že uživatel ve svém skriptu použije zástupný text {RAW_OUT}
        return self.control_script.format(RAW_OUT=raw_filename)


class ParameterExpander:
    """
    Utility třída pro rozbalování asymetrických a hybridních parametrů.
    Zajistí převod uživatelského zadání do plochého seznamu (Fronty úloh).
    """
    
    @staticmethod
    def _expand_single_dict(param_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Zpracuje jeden slovník. Pokud obsahuje pole (list), vytvoří všechny 
        možné kombinace. Pokud obsahuje jen skaláry, vrátí pole o jednom prvku.
        """
        if not param_dict:
            return [{}]

        keys = list(param_dict.keys())
        values_lists = []
        
        for key in keys:
            val = param_dict[key]
            # Pokud je hodnota list (např. [0.13, 0.26]), použijeme ho
            if isinstance(val, list):
                values_lists.append(val)
            # Pokud je to skalár (číslo, string), uměle ho zabalíme do listu
            else:
                values_lists.append([val])
                
        # itertools.product udělá křížení "každý s každým" napříč všemi argumenty
        combinations = itertools.product(*values_lists)
        
        # Složení zpět do pole slovníků
        expanded = [dict(zip(keys, combo)) for combo in combinations]
        return expanded

    @classmethod
    def expand(cls, params: Union[Dict[str, Any], List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """
        Hlavní vstupní bod. Přijme slovník nebo pole slovníků a vrátí 
        1D pole připravené k sekvenčnímu nebo paralelnímu zpracování.
        """
        if params is None:
            return [{}]

        # Pokud uživatel poslal jen jeden slovník (Single run nebo jednoduchý Sweep),
        # zabalíme ho pro sjednocení smyčky do pole
        if isinstance(params, dict):
            params_list = [params]
        elif isinstance(params, list):
            params_list = params
        else:
            raise ValueError("Parametry musí být slovník nebo seznam slovníků.")
            
        # Projdeme všechny bloky a postupně je "rozbalíme"
        flat_list = []
        for p_dict in params_list:
            flat_list.extend(cls._expand_single_dict(p_dict))
            
        return flat_list

class NgspiceRunner:
    """Paralelní simulační engine vysoce optimalizovaný pro vícenásobné běhy."""
    def __init__(self, workspace):
        # Objekt WorkspaceManager z vaší původní implementace
        self.ws = workspace

    def _run_single_task(self, task_idx: int, params: Dict[str, Any], template_path: Path, control_block: str) -> Dict[str, Any]:
        """
        Izolovaná úloha, která poběží ve zcela nezávislém procesu OS.
        Obsahuje vytvoření vlastního pískoviště a bezpečný zápis dat.
        """
        # 1. Vytvoření striktně unikátního pískoviště pro tento jeden běh
        run_id = f"run_{task_idx:04d}_{uuid.uuid4().hex[:6]}"
        sandbox = self.ws.create_sandbox(run_id)
        
        run_spice = sandbox / f"{run_id}.spice"
        raw_output = sandbox / f"{run_id}.raw"
        log_output = sandbox / f"{run_id}.log"
        
        try:
            # 2. Nahrazení parametrů "on-the-fly"
            with open(template_path, "r", encoding="utf-8") as f:
                netlist = f.read()
                
            for key, value in params.items():
                netlist = netlist.replace(key, str(value))
                
            # Vložení konkrétního control bloku s nasměrováním na lokální RAW soubor
            control_formatted = control_block.format(RAW_OUT=raw_output.name)
            
            with open(run_spice, "w", encoding="utf-8") as f:
                f.write(netlist)
                f.write("\n")
                f.write(control_formatted)
                
            # 3. Synchronní spuštění izolovaného Ngspice procesu (stdout teče do logu)
            with open(log_output, "w") as log_file:
                result = subprocess.run(
                    ["ngspice", "-b", run_spice.name], 
                    cwd=sandbox,
                    stdout=log_file,
                    stderr=subprocess.STDOUT
                )
            
            # Validační pojistka, zda simulátor nespadl
            status = "OK" if result.returncode == 0 and raw_output.exists() else "ERROR"
            
        except Exception as e:
            status = f"EXCEPTION: {str(e)}"
        
        # 4. Vrácení strukturovaného datového balíčku zpět do nadřazeného skriptu
        return {
            "task_idx": task_idx,
            "params": params,
            "raw_path": raw_output if status == "OK" else None,
            "log_path": log_output,
            "sandbox_dir": sandbox,
            "status": status
        }

    def run_batch(self, template_name: str, flat_params_list: List[Dict[str, Any]], control_block: str, max_workers: int = None) -> List[Dict[str, Any]]:
        """
        Rozdělí plochý seznam úloh mezi volná jádra procesoru a posbírá výsledky.
        """
        template_path = self.ws.dirs["netlists"] / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Šablona {template_name} nebyla nalezena ve složce netlists/")

        total_tasks = len(flat_params_list)
        results = []
        
        if total_tasks == 0:
            return results

        print(f"[Engine] Spouštím {total_tasks} simulací paralelně (Jádra: {max_workers or 'Maximum'})...")
        
        # Využití ProcessPoolExecutoru pro úplné obejití Python GIL
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            # 1. Fáze: Odeslání všech úloh do poolu
            futures = []
            for idx, params in enumerate(flat_params_list):
                future = executor.submit(
                    self._run_single_task, 
                    idx, params, template_path, control_block
                )
                futures.append(future)
            
            # 2. Fáze: Sběr výsledků tak, jak iterativně dobíhají (as_completed)
            for future in concurrent.futures.as_completed(futures):
                results.append(future.result())

        # Vlákna dokončují práci v náhodném pořadí, proto musíme výsledky seřadit 
        # zpět podle původního indexu, aby matice dat v dalším kroku seděla k zadání
        results.sort(key=lambda x: x["task_idx"])
        
        fail_count = sum(1 for r in results if r["status"] != "OK")
        if fail_count > 0:
            print(f"[Engine] ⚠️ Dokončeno s chybami. Počet selhání: {fail_count}/{total_tasks}")
        else:
            print(f"[Engine] ✅ Všech {total_tasks} simulací úspěšně dokončeno.")
            
        return results

class Testbench:
    """
    Zastřešující stavové API (Stateful API) pro řízení simulací.
    Pamatuje si nastavení parametrů jako reálný laboratorní stůl a chytře 
    slučuje nové parametry s předchozími.
    """
    def __init__(self, engine, template: str, default_params: Dict[str, Any] = None):
        self.engine = engine
        self.template = template
        # Vnitřní stav "laboratorního stolu"
        self.saved_params: Union[Dict[str, Any], List[Dict[str, Any]]] = default_params or {}

    def set_parameters(self, params: Union[Dict[str, Any], List[Dict[str, Any]]], keep_previous: bool = False):
        """
        Nastaví parametry pro další simulace. Podporuje jednorázové běhy, 
        parametrické sweepy i asymetrické PVT matice.
        """
        if not keep_previous:
            # RESET: Smaže předchozí stav a nahradí ho novým
            # Používáme deepcopy, abychom zamezili nechtěnému přepisu reference
            self.saved_params = copy.deepcopy(params)
        else:
            # UPDATE: Pokusíme se chytře sloučit nové parametry s předchozím stavem
            if isinstance(self.saved_params, dict) and isinstance(params, dict):
                # Stav: Slovník + Nové: Slovník -> Jednoduchý update
                self.saved_params.update(copy.deepcopy(params))
                
            elif isinstance(self.saved_params, dict) and isinstance(params, list):
                # Stav: Slovník (základ) + Nové: Pole (např. PVT kouty)
                # Vytvoříme pole, kde každý prvek obsahuje náš základ + specifika koutu
                merged_list = []
                for p_dict in params:
                    merged = copy.deepcopy(self.saved_params)
                    merged.update(p_dict)
                    merged_list.append(merged)
                self.saved_params = merged_list
                
            elif isinstance(self.saved_params, list) and isinstance(params, dict):
                # Stav: Pole (PVT kouty) + Nové: Slovník (např. plošná změna VDD)
                # Přidáme/přepíšeme novou hodnotu plošně ve všech existujících úlohách
                for p_dict in self.saved_params:
                    p_dict.update(copy.deepcopy(params))
            else:
                # Stav: Pole + Nové: Pole -> Vyměníme matici (např. jedna PVT za druhou PVT)
                self.saved_params = copy.deepcopy(params)
                
    def run(self, analysis, max_workers: int = None) -> List[Dict[str, Any]]:
        """
        Vygeneruje control blok z analýzy, rozbalí parametry do ploché fronty
        a odešle je enginu k paralelnímu zpracování.
        """
        # 1. Rozbalení hybridních a asymetrických parametrů do plochého seznamu (Krok 2)
        flat_tasks = ParameterExpander.expand(self.saved_params)
        
        # 2. Získání řídícího bloku z objektu analýzy (Krok 1)
        control_block = analysis.get_control_block(raw_filename="{RAW_OUT}")
        
        # 3. Předání práce paralelnímu Enginu (Krok 3)
        print(f"\n[Testbench] Spouštím analýzu: {analysis.__class__.__name__}")
        results = self.engine.run_batch(
            template_name=self.template,
            flat_params_list=flat_tasks,
            control_block=control_block,
            max_workers=max_workers
        )
        
        return results