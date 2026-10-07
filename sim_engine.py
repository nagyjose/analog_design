import subprocess
import os
import pandas as pd

class NgspiceRunner:
    """Univerzální třída pro řízení Ngspice a extrakci dat."""
    
    def __init__(self, tb_spice_path, work_dir="simulations"):
        self.tb_spice_path = tb_spice_path
        self.work_dir = work_dir
        
        # Přečteme si šablonu vygenerovanou z Xschemu
        with open(self.tb_spice_path, "r") as f:
            self.base_netlist = f.read()
            
        if not os.path.exists(self.work_dir):
            os.makedirs(self.work_dir)

    def run_simulation(self, sim_id, params, control_block):
        """
        Spustí simulaci s danými parametry a řídícím blokem.
        - params: slovník, např. {"{CORNER_MOS}": "mos_tt", "{TEMP_VAL}": "25"}
        - control_block: SPICE kód pro .control sekci
        """
        # 1. Nahrazení parametrů v základním netlistu
        netlist = self.base_netlist
        for key, value in params.items():
            netlist = netlist.replace(key, str(value))
            
        # 2. Definice pracovních souborů
        run_spice = os.path.join(self.work_dir, f"run_{sim_id}.spice")
        data_txt = os.path.join(self.work_dir, f"res_{sim_id}.txt")
        
        # Do řídícího bloku automaticky vložíme správnou cestu k výstupu
        control_block_formatted = control_block.format(DATA_TXT=data_txt)
        
        # 3. Složení finálního netlistu
        final_spice = f"{netlist}\n{control_block_formatted}"
        
        with open(run_spice, "w") as f:
            f.write(final_spice)
            
        # 4. Spuštění Ngspice (batch mode)
        # Používáme -b pro batch mode a skryjeme výstup jako ve vašem NMOS_lv_sim.py
        subprocess.run(["ngspice", "-b", run_spice], stdout=subprocess.DEVNULL)
        
        return data_txt

    def load_wrdata(self, txt_path, columns):
        """Načte wrdata textový výstup do Pandas DataFrame."""
        if not os.path.exists(txt_path):
            raise FileNotFoundError(f"Soubor s daty {txt_path} nebyl vytvořen.")
            
        # Odpovídá vašemu kódu: df = pd.read_csv(DATA_TXT, sep=r'\s+', header=None, names=sloupce)
        df = pd.read_csv(txt_path, sep=r'\s+', header=None, names=columns)
        return df