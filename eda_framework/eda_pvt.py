import copy
from typing import Union, List, Dict, Any

class PVTBuilder:
    """
    Továrna na simulační scénáře pro IHP SG13G2 PDK.
    Poskytuje předdefinované i vlastní kombinace PVT rohů pro Testbench.
    """
    def __init__(self, vdd_nom: float = 1.2, vdd_tol_pct: float = 10.0, temp_nom: float = 25.0):
        self.vdd_nom = vdd_nom
        self.vdd_min = round(vdd_nom * (1 - vdd_tol_pct / 100.0), 3)
        self.vdd_max = round(vdd_nom * (1 + vdd_tol_pct / 100.0), 3)
        self.temp_nom = temp_nom
        
        # Zlatý standard (Typické podmínky pro IHP SG13G2)
        self.default_state = {
            "{VDD}": self.vdd_nom,
            "{TEMP}": self.temp_nom,
            "{C_MOS_LV}": "mos_tt",
            "{C_MOS_HV}": "mos_tt",
            "{C_HBT}": "hbt_typ",
            "{C_RES}": "res_typ",
            "{C_CAP}": "cap_typ"
        }

    def _build(self, **overrides) -> Dict[str, Any]:
        """Interní pomocník pro sloučení defaultu s požadovanými změnami."""
        state = copy.deepcopy(self.default_state)
        state.update(overrides)
        return state

    def _apply(self, base_scenario: dict, user_kwargs: dict) -> Dict[str, Any]:
        """Přeloží uživatelské kwargs a aplikuje je na základní scénář s nejvyšší prioritou."""
        mapping = {
            "temp": "{TEMP}", "vdd": "{VDD}", 
            "mos_lv": "{C_MOS_LV}", "mos_hv": "{C_MOS_HV}", 
            "hbt": "{C_HBT}", "res": "{C_RES}", "cap": "{C_CAP}"
        }
        # Překlad lidských názvů na Ngspice tagy
        overrides = {mapping[k]: v for k, v in user_kwargs.items() if k in mapping}
        
        # Aplikace uživatelských změn na base_scenario (lokální override)
        final_scenario = copy.deepcopy(base_scenario)
        final_scenario.update(overrides)
        
        # Odeslání do hlavního builderu pro doplnění zbytku na typické hodnoty
        return self._build(**final_scenario)


    # ==========================================
    # 1. VOLNÁ SKLÁDAČKA A UTILITY
    # ==========================================

    def get_nominal(self, **kwargs):
        """Vrátí absolutní střed (ideální pro první kontrolu obvodu)."""
        return self._apply({}, kwargs)

    def custom_matrix(self, **kwargs):
        """
        Uživatelsky přívětivá volná skládačka. Uživatel zadá jen to, co chce měnit.
        Lze zadat pole (např. temp=[-40, 125]) pro vytvoření matice.
        """
        return self._apply({}, kwargs)

    @staticmethod
    def combine_scenarios(*scenarios) -> List[Dict[str, Any]]:
        """
        Slepí libovolné množství scénářů (slovníků nebo polí slovníků) do jedné fronty.
        Příklad: pvt.combine_scenarios(pvt.wc_rc_delay(), pvt.wc_leakage())
        """
        combined = []
        for s in scenarios:
            if isinstance(s, list):
                combined.extend(s)
            else:
                combined.append(s)
        return combined

    def get_monte_carlo(self, mismatch_en=True, process_en=True, **kwargs):
        """
        Připraví scénář pro statistickou MC analýzu.
        Napětí a teplota zůstávají deterministické (lze je přepsat přes kwargs).
        Knihovny PDK se přepnou na statistické modely (pro SG13G2 je to 'stat').
        """
        base = {
            "{C_MOS_LV}": "stat",
            "{C_MOS_HV}": "stat",
            "{C_HBT}": "stat",
            "{C_RES}": "stat",
            "{C_CAP}": "stat",
            # Speciální vlajky (flags), které vložíme do netlistu k zapnutí/vypnutí
            # Pelgromova mismatch modelu nebo globálních procesních variací
            "{MC_PROCESS}": 1 if process_en else 0,
            "{MC_MISMATCH}": 1 if mismatch_en else 0
        }
        return self._apply(base, kwargs)


    # ==========================================
    # 2. IZOLOVANÉ 1D STAVEBNÍ BLOKY
    # ==========================================

    def sweep_temperature(self, temps=[-40, 0, 25, 85, 125], **kwargs):
        """Kříží pouze teploty."""
        return self._apply({"{TEMP}": temps}, kwargs)
        
    def sweep_voltage(self, vdds=None, **kwargs):
        """Kříží pouze napájecí napětí (Min, Nom, Max)."""
        vdds = vdds or [self.vdd_min, self.vdd_nom, self.vdd_max]
        return self._apply({"{VDD}": vdds}, kwargs)

    def sweep_mos_lv(self, corners=["mos_tt", "mos_ss", "mos_ff", "mos_sf", "mos_fs"], **kwargs):
        """Sweepuje všechny kouty pro nízkonapěťové (core) MOS tranzistory."""
        return self._apply({"{C_MOS_LV}": corners}, kwargs)

    def sweep_mos_hv(self, corners=["mos_tt", "mos_ss", "mos_ff"], **kwargs):
        """Sweepuje kouty pro tlustookrajové (I/O) MOS tranzistory."""
        return self._apply({"{C_MOS_HV}": corners}, kwargs)

    def sweep_bipolar(self, corners=["hbt_typ", "hbt_min", "hbt_max"], **kwargs):
        """Sweepuje heteropřechodové bipoláry (SiGe HBT)."""
        return self._apply({"{C_HBT}": corners}, kwargs)

    def sweep_res(self, corners=["res_typ", "res_min", "res_max"], **kwargs):
        """Sweepuje odděleně pouze rezistory."""
        return self._apply({"{C_RES}": corners}, kwargs)

    def sweep_cap(self, corners=["cap_typ", "cap_min", "cap_max"], **kwargs):
        """Sweepuje odděleně pouze kapacity."""
        return self._apply({"{C_CAP}": corners}, kwargs)

    def sweep_passives_combined(self, corners=["typ", "min", "max"], **kwargs) -> List[Dict[str, Any]]:
        """Synchronní sweep (odpory i kapacity se mění stejným směrem)."""
        # Musíme vracet pole slovníků, aby se to nekřížilo "každý s každým"
        return [self._apply({"{C_RES}": c, "{C_CAP}": c}, kwargs) for c in corners]


    # ==========================================
    # 3. CÍLENÉ WORST-CASE SCÉNÁŘE
    # ==========================================

    def wc_digital_speed(self, **kwargs):
        """Nejhorší rychlost logiky. Zima nebo horko (zvoleno 125), pomalé tranzistory, podpětí."""
        base = {"{C_MOS_LV}": "mos_ss", "{C_MOS_HV}": "mos_ss", "{TEMP}": 125, "{VDD}": self.vdd_min}
        return self._apply(base, kwargs)

    def wc_rc_delay(self, **kwargs):
        """Maximalizace časové konstanty tau = R*C. Zásadní pro analogové filtry."""
        base = {"{C_RES}": "res_max", "{C_CAP}": "cap_max"}
        return self._apply(base, kwargs)

    def wc_power_leakage(self, **kwargs):
        """Největší únikový (statický) proud. Rychlé (low Vth) tranzistory, horko, přepětí."""
        base = {"{C_MOS_LV}": "mos_ff", "{C_MOS_HV}": "mos_ff", "{C_RES}": "res_min", "{TEMP}": 125, "{VDD}": self.vdd_max}
        return self._apply(base, kwargs)

    def wc_analog_gain(self, **kwargs):
        """Minimální zisk analogových zesilovačů (gm/gds degradace)."""
        # Tranzistory s krátkým kanálem při vysoké teplotě a nízkém napájení trpí nejvíce.
        base = {"{C_MOS_LV}": "mos_fs", "{TEMP}": 125, "{VDD}": self.vdd_min}
        return self._apply(base, kwargs)

    def wc_noise_rf(self, **kwargs):
        """Maximalizace tepelného a 1/f šumu. Pomalé aktivní prvky a velké odpory."""
        base = {"{C_MOS_LV}": "mos_ss", "{C_HBT}": "hbt_min", "{C_RES}": "res_max", "{TEMP}": 125}
        return self._apply(base, kwargs)


    # ==========================================
    # 4. KOMPLEXNÍ SIGN-OFF MATICE
    # ==========================================

    def matrix_standard_digital(self, **kwargs):
        """Klasických 27 rohů (3 VDD x 3 TEMP x 3 MOS). Ostatní typické."""
        base = {
            "{C_MOS_LV}": ["mos_tt", "mos_ss", "mos_ff"], 
            "{TEMP}": [-40, 25, 125], 
            "{VDD}": [self.vdd_min, self.vdd_nom, self.vdd_max]
        }
        return self._apply(base, kwargs)

    def matrix_full_digital(self, **kwargs):
        """Plná matice logiky pokrývající i křížové rohy (45 běhů)."""
        base = {
            "{C_MOS_LV}": ["mos_tt", "mos_ss", "mos_ff", "mos_sf", "mos_fs"], 
            "{TEMP}": [-40, 25, 125], 
            "{VDD}": [self.vdd_min, self.vdd_nom, self.vdd_max]
        }
        return self._apply(base, kwargs)

    def matrix_analog_base(self, **kwargs):
        """
        Základní analogová verifikace (81 běhů).
        VDD (3) x TEMP (3) x MOS_LV (3) x RES (3) -> CAP necháváme na typ, ať matice neexploduje.
        Pokud by se přidal CAP, bylo by to 243 běhů. Lze to ale snadno upravit.
        """
        base = {
            "{C_MOS_LV}": ["mos_tt", "mos_ss", "mos_ff"],
            "{C_RES}": ["res_typ", "res_min", "res_max"],
            "{TEMP}": [-40, 25, 125], 
            "{VDD}": [self.vdd_min, self.vdd_nom, self.vdd_max]
        }
        return self._apply(base, kwargs)

    def matrix_bicmos_analog(self, **kwargs):
        """
        Plná BiCMOS matice pro obvody jako Bandgap reference nebo RF LNA.
        (MOS + HBT + RES) - 81 běhů (HBT má 3 rohy, RES 3, MOS 3, TEMP 3, ale my omezíme VDD na Nom, 
        aby to nebylo 243 běhů - v případě potřeby napětí přidáme do pole).
        """
        base = {
            "{C_MOS_LV}": ["mos_tt", "mos_ss", "mos_ff"],
            "{C_HBT}": ["hbt_typ", "hbt_min", "hbt_max"],
            "{C_RES}": ["res_typ", "res_min", "res_max"],
            "{TEMP}": [-40, 25, 125]
        }
        return self._apply(base, kwargs)

    def matrix_bicmos_analog_full(self, **kwargs):
        """
        Extrémní BiCMOS matice pokrývající všechny klíčové analogové jevy.
        MOS_LV (3) × HBT (3) × RES (3) × TEMP (3) × VDD (3) = 243 běhů.
        """
        base = {
            "{C_MOS_LV}": ["mos_tt", "mos_ss", "mos_ff"],
            "{C_HBT}": ["hbt_typ", "hbt_min", "hbt_max"],
            "{C_RES}": ["res_typ", "res_min", "res_max"],
            "{TEMP}": [-40, 25, 125],
            "{VDD}": [self.vdd_min, self.vdd_nom, self.vdd_max]
        }
        return self._apply(base, kwargs)