import shutil
import uuid
import subprocess
from pathlib import Path

class WorkspaceManager:
    """
    Spravuje adresářovou strukturu projektu a izolovaná pískoviště (sandboxy) pro běh Ngspice.
    Zajišťuje, že se paralelní nebo po sobě jdoucí simulace nepřepíší.
    """
    
    def __init__(self, project_root: str):
        """
        Inicializuje správce pro danou kořenovou složku hardwarového projektu.
        """
        self.root = Path(project_root).resolve()
        
        # Definice klíčových složek
        self.dirs = {
            "schematics": self.root / "schematics", # Zde ukládá uživatel Xschem data
            "netlists": self.root / "netlists",     # Zde exportuje Xschem zlaté šablony
            "work": self.root / "work",             # Zde se děje špinavá práce (Sandboxy)
            "reports": self.root / "reports"        # Zde končí finální grafy a CSV
        }
        
        # Automatické vytvoření základní struktury
        self._init_structure()

    def _init_structure(self):
        """Vytvoří chybějící složky stromu, pokud neexistují."""
        for name, path in self.dirs.items():
            path.mkdir(parents=True, exist_ok=True)
            
    def clear_work_directory(self):
        """
        Kompletně vymaže a znovu vytvoří pracovní složku.
        Vhodné zavolat na začátku velkého PVT skenování.
        """
        if self.dirs["work"].exists():
            shutil.rmtree(self.dirs["work"])
        self.dirs["work"].mkdir()
        print(f"[Workspace] Pracovní složka {self.dirs['work'].name}/ byla vyčištěna.")

    def create_sandbox(self, run_id: str = None) -> Path:
        """
        Vytvoří unikátní podsložku (pískoviště) pro jeden konkrétní běh simulace.
        Pokud není zadán run_id, vygeneruje se náhodné UUID.
        
        Vrací objekt Path odkazující na vytvořenou složku.
        """
        if not run_id:
            # Vygenerujeme krátké unikátní ID (prvních 8 znaků z UUID)
            run_id = f"run_{uuid.uuid4().hex[:8]}"
            
        # Zabezpečení proti neplatným znakům ve jméně složky (mezery, lomenítka)
        safe_run_id = "".join([c if c.isalnum() or c in "_-" else "_" for c in run_id])
        
        sandbox_path = self.dirs["work"] / safe_run_id
        sandbox_path.mkdir(parents=True, exist_ok=True)
        
        return sandbox_path

    def cleanup_sandbox(self, sandbox_path: Path):
        """
        Smaže konkrétní pískoviště. Volá se typicky poté, co eda_data.py extrahuje RAW soubor.
        """
        if sandbox_path.exists() and sandbox_path.is_dir():
            shutil.rmtree(sandbox_path)

class NgspiceRunner:
    """
    Simulační engine. Dynamicky nahrazuje parametry ve SPICE šablonách,
    spouští Ngspice proces v izolovaném pískovišti a odchytává jeho výstupy.
    """
    
    def __init__(self, workspace: WorkspaceManager):
        """Vyžaduje existující WorkspaceManager pro přístup ke stromu složek."""
        self.ws = workspace

    def run_simulation(self, run_id: str, template_name: str, params: dict, control_block: str) -> Path:
        """
        Vygeneruje netlist z šablony, spustí Ngspice a vrátí cestu k vygenerovanému RAW souboru.
        
        :param run_id: Unikátní identifikátor simulace (např. 'mos_tt_125C').
        :param template_name: Název šablony v netlists/ (např. 'tb_ota_template.spice').
        :param params: Slovník nahrazovaných parametrů (např. {"{TEMP}": "125"}).
        :param control_block: SPICE .control skript obsahující tag {RAW_OUT}.
        """
        # 1. Cesta k "zlaté šabloně" z Xschemu
        template_path = self.ws.dirs["netlists"] / template_name
        if not template_path.exists():
            raise FileNotFoundError(f"Šablona {template_path} neexistuje! Vygenerujte ji v Xschemu do složky netlists/.")

        # 2. Vytvoření izolačního pískoviště
        sandbox = self.ws.create_sandbox(run_id)
        
        # Soubory, které vzniknou v pískovišti
        run_spice = sandbox / f"{run_id}.spice"
        raw_output = sandbox / f"{run_id}.raw"
        log_output = sandbox / f"{run_id}.log"
        
        # 3. Načtení šablony a nahrazení rohových/Sweep parametrů
        with open(template_path, "r", encoding="utf-8") as f:
            netlist = f.read()
            
        for key, value in params.items():
            netlist = netlist.replace(key, str(value))
            
        # 4. Formátování řídícího bloku
        # Uživatel použije tag {RAW_OUT}, skript ho nahradí jménem RAW souboru.
        # Použijeme .name (jen jméno souboru), protože ngspice pustíme s pracovním adresářem uvnitř pískoviště.
        control_formatted = control_block.format(RAW_OUT=raw_output.name)
        
        # 5. Sestavení finálního spustitelného SPICE souboru
        with open(run_spice, "w", encoding="utf-8") as f:
            f.write(netlist)
            f.write("\n")
            f.write(control_formatted)
            
        # 6. Bezpečné spuštění Ngspice
        # stdout přesměrujeme do textového logu. Ngspice tak nebude spamovat Python terminál, 
        # ale v případě chyby si log můžete vždy zpětně přečíst.
        with open(log_output, "w") as log_file:
            result = subprocess.run(
                ["ngspice", "-b", run_spice.name], 
                cwd=sandbox,  # MAGIE: Python uzamkne Ngspice jen do této složky!
                stdout=log_file,
                stderr=subprocess.STDOUT
            )
            
        if result.returncode != 0:
            print(f"[Engine] ❌ CHYBA: Simulace '{run_id}' selhala! Zkontrolujte log: {log_output}")
            return None
            
        if not raw_output.exists():
            print(f"[Engine] ❌ CHYBA: Simulace doběhla, ale soubor {raw_output.name} se nevygeneroval.")
            return None
            
        print(f"[Engine] ✅ Simulace '{run_id}' úspěšně dokončena.")
        return raw_output        