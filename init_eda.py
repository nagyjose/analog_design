#!/usr/bin/env python3
import argparse
from pathlib import Path

def create_project(project_name, init_sch=False):
    """
    Vygeneruje adresářovou strukturu a konfigurační soubory pro nový EDA projekt.
    Bezpečně propojí lokální xschemrc s globální konfigurací IHP PDK.
    """
    workspace_root = Path(__file__).resolve().parent
    root = (workspace_root / project_name).resolve()
    
    # 1. Tvorba adresářové struktury
    folders = ['schematics', 'netlists', 'simulations', 'work', 'reports']
    for folder in folders:
        (root / folder).mkdir(parents=True, exist_ok=True)
        
    # 2. Generování hlavního projektového xschemrc (v kořeni projektu)
    # Nejprve načte hlavní xschemrc z ihp_designs (nebo z PDK) a poté přesměruje netlist_dir
    xschemrc_content = """# Lokální konfigurace Xschem pro projekt
set PROJ_DIR [file dirname [file normalize [info script]]]
set WORKSPACE_RC [file normalize "${PROJ_DIR}/../xschemrc"]

# 1. Načtení globální IHP PDK konfigurace
if {[file exists $WORKSPACE_RC]} {
    source $WORKSPACE_RC
} elseif {[info exists env(PDK_ROOT)]} {
    source "$env(PDK_ROOT)/ihp-sg13g2/libs.tech/xschem/xschemrc"
}

# 2. Vynucení ukládání netlistů vždy do složky netlists/ tohoto projektu
set netlist_dir "${PROJ_DIR}/netlists"

# 3. Přidání složky schematics/ projektu do knihoven (pro hierarchické bloky)
append XSCHEM_LIBRARY_PATH ":${PROJ_DIR}/schematics"
"""
    with open(root / 'xschemrc', 'w', encoding='utf-8') as f:
        f.write(xschemrc_content.strip() + "\n")
        
    # 3. Přesměrovávací xschemrc přímo do složky schematics/
    # Umožní spouštět příkaz 'xschem' přímo ze složky schematics/ se stejným výsledkem
    sub_xschemrc_content = """# Přesměrování na hlavní xschemrc projektu
source "[file dirname [file normalize [info script]]]/../xschemrc"
"""
    with open(root / 'schematics' / 'xschemrc', 'w', encoding='utf-8') as f:
        f.write(sub_xschemrc_content)
        
    # 4. Generování šablony simulačního skriptu (pouze pokud ještě neexistuje)
    sim_script_path = root / 'simulations' / f'run_{project_name}.py'
    if not sim_script_path.exists():
        run_sim_content = f"""import sys
from pathlib import Path

# Automatické nalezení kořene projektu a složky eda_framework (nezávisle na CWD)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(WORKSPACE_ROOT / "eda_framework"))

from eda_engine import WorkspaceManager, NgspiceRunner, Testbench
from eda_data import SimulationDataSet
from eda_plot import EDAPlotter
from eda_analysis import SignalAnalyzer
from eda_pvt import PVTBuilder

# 1. Inicializace projektu
ws = WorkspaceManager(project_root=PROJECT_ROOT)
ws.clear_work_directory()
engine = NgspiceRunner(ws)

print(f"EDA Workspace pro projekt '{project_name}' je připraven v: {{PROJECT_ROOT}}")
"""
        with open(sim_script_path, 'w', encoding='utf-8') as f:
                    f.write(run_sim_content)

    # 4. Volitelná tvorba prázdných Xschem schémat (přes modifikátor --sch)
    if init_sch:
        # Zcela minimální validní hlavička Xschem souboru
        blank_sch = "v {xschem version=3.4.0 file_version=1.2}\nG {}\n"
        
        for sch_name in [f'{project_name}.sch', f'tb_{project_name}.sch']:
            sch_path = root / 'schematics' / sch_name
            if not sch_path.exists():
                with open(sch_path, 'w', encoding='utf-8') as f:
                    f.write(blank_sch)
        print(f"[*] Zkontrolovány/vytvořeny šablony schémat ve složce schematics/")

    print(f"[✅] Projekt '{project_name}' je plně nakonfigurován!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generátor struktury pro EDA projekty (Xschem + Ngspice + Python)")
    parser.add_argument("project_name", help="Název nového projektu (např. LNA_130nm)")
    parser.add_argument("--sch", action="store_true", help="Vytvoří i počáteční prázdná schémata (.sch a tb_.sch)")
    
    args = parser.parse_args()
    create_project(args.project_name, args.sch)