#!/usr/bin/env python3
import os
import argparse
from pathlib import Path

def create_project(project_name, init_sch=False):
    """
    Vygeneruje adresářovou strukturu a konfigurační soubory pro nový EDA projekt.
    """
    root = Path(project_name).resolve()
    
    # 1. Tvorba adresářové struktury
    folders = ['schematics', 'netlists', 'simulations', 'work', 'reports']
    for folder in folders:
        (root / folder).mkdir(parents=True, exist_ok=True)
        
    # 2. Generování ukázněného xschemrc
    # Tento soubor zajistí, že Xschem bude respektovat naši strukturu
    xschemrc_content = f"""
# Lokální konfigurace Xschem pro projekt {project_name}
# Vynucení ukládání netlistů do složky netlists/
set netlist_dir $env(PWD)/netlists
"""
    with open(root / 'xschemrc', 'w', encoding='utf-8') as f:
        f.write(xschemrc_content.strip() + "\n")
        
    # 3. Generování šablony simulačního skriptu v Pythonu
    # Skript bude ležet ve složce simulations/, takže project_root bude o patro výš ("..")
    run_sim_content = f"""
from eda_engine import WorkspaceManager, NgspiceRunner

# 1. Inicializace projektu (ukazujeme do kořenové složky projektu)
ws = WorkspaceManager(project_root="..")
ws.clear_work_directory()
engine = NgspiceRunner(ws)

print("EDA Workspace pro projekt {project_name} je připraven!")
print("1. Nakreslete schéma v ../schematics/")
print("2. Vygenerujte netlist (automaticky spadne do ../netlists/)")
print("3. Zde doplňte spouštěcí logiku a spusťte simulaci.")
"""
    with open(root / 'simulations' / f'run_{project_name}.py', 'w', encoding='utf-8') as f:
        f.write(run_sim_content.strip() + "\n")

    # 4. Volitelná tvorba prázdných Xschem schémat (přes modifikátor --sch)
    if init_sch:
        # Zcela minimální validní hlavička Xschem souboru
        blank_sch = "v {xschem version=3.4.0 file_version=1.2}\nG {}\n"
        
        # Schéma samotného bloku (DUT)
        with open(root / 'schematics' / f'{project_name}.sch', 'w', encoding='utf-8') as f:
            f.write(blank_sch)
            
        # Schéma testbenche
        with open(root / 'schematics' / f'tb_{project_name}.sch', 'w', encoding='utf-8') as f:
            f.write(blank_sch)
            
        print(f"[*] Byly vytvořeny prázdné šablony: {project_name}.sch a tb_{project_name}.sch")

    print(f"[✅] Projekt '{project_name}' byl úspěšně vygenerován!")
    print(f"     Přejděte do složky: cd {project_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generátor struktury pro EDA projekty (Xschem + Ngspice + Python)")
    parser.add_argument("project_name", help="Název nového projektu (např. LNA_130nm)")
    parser.add_argument("--sch", action="store_true", help="Vytvoří i počáteční prázdná schémata (.sch a tb_.sch)")
    
    args = parser.parse_args()
    create_project(args.project_name, args.sch)