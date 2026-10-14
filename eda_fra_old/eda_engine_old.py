import shutil
import uuid
import subprocess
from pathlib import Path

class WorkspaceManager:
    """
    Spravuje běhové prostředí projektu (Runtime Workspace).
    Předpokládá, že základní strukturu již vytvořil generátor (init_eda.py).
    """
    def __init__(self, project_root: str):
        self.root = Path(project_root).resolve()
        
        # Tyto složky musí existovat
        self.dirs = {
            "schematics": self.root / "schematics",
            "netlists": self.root / "netlists",     # Xschem sem bude posílat netlisty díky xschemrc
            "simulations": self.root / "simulations",
            "work": self.root / "work",             # Dynamické pískoviště
            "reports": self.root / "reports"
        }
        self._verify_structure()

    def _verify_structure(self):
        """Ověří, zda pracujeme ve validním EDA projektu."""
        for name, path in self.dirs.items():
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True) # Fallback

    def clear_work_directory(self):
        """Smaže všechna pískoviště z předchozích běhů."""
        if self.dirs["work"].exists():
            shutil.rmtree(self.dirs["work"])
        self.dirs["work"].mkdir()
        print("[Workspace] Pracovní složka vyčištěna.")

    def create_sandbox(self, run_id: str = None) -> Path:
        """Vytvoří unikátní podsložku pro jeden běh Ngspice."""
        if not run_id:
            run_id = f"run_{uuid.uuid4().hex[:8]}"
            
        safe_run_id = "".join([c if c.isalnum() or c in "_-" else "_" for c in run_id])
        sandbox_path = self.dirs["work"] / safe_run_id
        sandbox_path.mkdir(parents=True, exist_ok=True)
        return sandbox_path

    def cleanup_sandbox(self, sandbox_path: Path):
        """Uklidí pískoviště (volá se typicky po extrakci dat)."""
        if sandbox_path.exists() and sandbox_path.is_dir():
            shutil.rmtree(sandbox_path)

class NgspiceRunner:
    """Simulační engine řešící spouštění procesů a netlist šablonování."""
    def __init__(self, workspace: WorkspaceManager):
        self.ws = workspace

    def run_simulation(self, run_id: str, template_name: str, params: dict, control_block: str) -> Path:
        """
        Vygeneruje finální netlist, spustí Ngspice v pískovišti a vrátí cestu k RAW/TXT souboru.
        """
        template_path = self.ws.dirs["netlists"] / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Šablona {template_name} nebyla nalezena ve složce netlists/")

        sandbox = self.ws.create_sandbox(run_id)
        
        run_spice = sandbox / f"{run_id}.spice"
        raw_output = sandbox / f"{run_id}.raw"
        log_output = sandbox / f"{run_id}.log"
        
        # Nahrazení parametrů
        with open(template_path, "r", encoding="utf-8") as f:
            netlist = f.read()
            
        for key, value in params.items():
            netlist = netlist.replace(key, str(value))
            
        # Formátování řídícího bloku ({RAW_OUT} -> jméno souboru)
        control_formatted = control_block.format(RAW_OUT=raw_output.name)
        
        with open(run_spice, "w", encoding="utf-8") as f:
            f.write(netlist)
            f.write("\n")
            f.write(control_formatted)
            
        # Bezpečné spuštění v uzamčeném CWD
        with open(log_output, "w") as log_file:
            result = subprocess.run(
                ["ngspice", "-b", run_spice.name], 
                cwd=sandbox,
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
            
        if result.returncode != 0 or not raw_output.exists():
            print(f"[Engine] ❌ Chyba při simulaci {run_id}. Zkontrolujte {log_output}")
            return None
            
        return raw_output