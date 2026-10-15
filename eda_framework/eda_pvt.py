import copy
from typing import Union, List, Dict, Any

class PVTBuilder:
    """
    Továrna na simulační scénáře přesně kalibrovaná podle corner*.lib v IHP SG13G2 PDK.
    Podporuje deterministické PVT rohy, plné statistické Monte Carlo (stat) i lokální párování (mismatch).
    """
    def __init__(self, vdd_nom: float = 1.2, vdd_tol_pct: float = 10.0, temp_nom: float = 25.0):
        self.vdd_nom = vdd_nom
        self.vdd_min = round(vdd_nom * (1 - vdd_tol_pct / 100.0), 3)
        self.vdd_max = round(vdd_nom * (1 + vdd_tol_pct / 100.0), 3)
        self.temp_nom = temp_nom
        
# Zlatý standard (Typické podmínky přesně podle IHP SG13G2 corner*.lib)
        self.default_state = {
            "{VDD}": self.vdd_nom,
            "{TEMP}": self.temp_nom,
            "{C_MOS_LV}": "mos_tt",
            "{C_MOS_HV}": "mos_tt",
            "{C_HBT}": "hbt_typ",
            "{C_RES}": "res_typ",
            "{C_CAP}": "cap_typ",
            "{C_DIO}": "dio_tt",
            "{C_MOSCAP}": "moscap_tt"
        }

    @staticmethod
    def _normalize_corner(tag: str, val: Any) -> Any:
        """
        Přeloží zkrácené zadání (např. 'tt', 'ss_mismatch', 'min', 'stat') 
        na přesný název sekce vyžadovaný soubory corner*.lib v IHP SG13G2.
        """
        if isinstance(val, list):
            return [PVTBuilder._normalize_corner(tag, v) for v in val]
        if not isinstance(val, str):
            return val

        prefix_map = {
            "{C_MOS_LV}": ("mos_", {
                "stat": "mos_tt_stat", "mismatch": "mos_tt_mismatch"
            }),
            "{C_MOS_HV}": ("mos_", {
                "stat": "mos_tt_stat", "mismatch": "mos_tt_mismatch"
            }),
            "{C_HBT}": ("hbt_", {
                "min": "hbt_wcs", "max": "hbt_bcs", 
                "stat": "hbt_typ_stat", "mismatch": "hbt_typ_mismatch"
            }),
            "{C_RES}": ("res_", {
                "min": "res_bcs", "max": "res_wcs", 
                "stat": "res_stat_mismatch", "process": "res_stat", "mismatch": "res_typ_mismatch"
            }),
            "{C_CAP}": ("cap_", {
                "min": "cap_bcs", "max": "cap_wcs", 
                "stat": "cap_typ_stat", "mismatch": "cap_typ_mismatch"
            }),
            "{C_DIO}": ("dio_", {
                "stat": "dio_tt_stat"
            }),
            "{C_MOSCAP}": ("moscap_", {
                "stat": "moscap_tt_stat", "mismatch": "moscap_tt_mismatch"
            })
        }

        if tag not in prefix_map:
            return val

        prefix, aliases = prefix_map[tag]
        if val in aliases:
            return aliases[val]
        if not val.startswith(prefix):
            return f"{prefix}{val}"
        return val

    def _build(self, **overrides) -> Dict[str, Any]:
        """Interní pomocník pro sloučení defaultu s požadovanými změnami."""
        state = copy.deepcopy(self.default_state)
        for k, v in overrides.items():
            state[k] = self._normalize_corner(k, v)
        return state

    def _apply(self, base_scenario: dict, user_kwargs: dict) -> Dict[str, Any]:
        """Přeloží uživatelské kwargs a aplikuje je na základní scénář s nejvyšší prioritou."""
        mapping = {
            "temp": "{TEMP}", "vdd": "{VDD}", 
            "mos_lv": "{C_MOS_LV}", "mos_hv": "{C_MOS_HV}", 
            "hbt": "{C_HBT}", "res": "{C_RES}", "cap": "{C_CAP}",
            "dio": "{C_DIO}", "moscap": "{C_MOSCAP}"
        }

        # Povolíme také přímé zadání libovolného vlastního tagu (např. "{L_n}")
        overrides = {}
        for k, v in user_kwargs.items():
            if k in mapping:
                overrides[mapping[k]] = v
            else:
                overrides[k if k.startswith("{") else f"{{{k}}}"] = v
        
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

    def get_monte_carlo(self, mode: str = "all", **kwargs) -> Dict[str, Any]:
        """
        Připraví scénář pro Monte Carlo analýzu v IHP SG13G2.
        
        :param mode: 
            - "all" (výchozí): Globální proces + lokální mismatch (*_stat / res_stat_mismatch)
            - "mismatch": Pouze lokální mismatch kolem zvoleného rohu (*_mismatch).
                          Pokud zadáte např. mos_lv="ss", automaticky vytvoří "mos_ss_mismatch"!
        """
        if mode == "all":
            base = {
                "{C_MOS_LV}": "mos_tt_stat",
                "{C_MOS_HV}": "mos_tt_stat",
                "{C_HBT}": "hbt_typ_stat",
                "{C_RES}": "res_stat_mismatch",
                "{C_CAP}": "cap_typ_stat",
                "{C_DIO}": "dio_tt_stat",
                "{C_MOSCAP}": "moscap_tt_stat"
            }
            return self._apply(base, kwargs)

        elif mode == "mismatch":
            # Nejprve sestavíme deterministický roh (výchozí tt/typ, nebo to co uživatel zadal v kwargs)
            det_state = self._apply({}, kwargs)
            # Následně ke všem součástkám, které podporují mismatch, připojíme příponu '_mismatch'
            mismatch_tags = ["{C_MOS_LV}", "{C_MOS_HV}", "{C_HBT}", "{C_RES}", "{C_CAP}", "{C_MOSCAP}"]
            for tag in mismatch_tags:
                val = det_state.get(tag, "")
                if isinstance(val, str) and not val.endswith("_mismatch") and not val.endswith("_stat"):
                    det_state[tag] = f"{val}_mismatch"
            return det_state

        else:
            raise ValueError("Neznámý režim Monte Carlo! Použijte mode='all' nebo mode='mismatch'.")


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

    def sweep_mos_hv(self, corners=["mos_tt", "mos_ss", "mos_ff", "mos_sf", "mos_fs"], **kwargs):
        """Sweepuje kouty pro tlustookrajové (I/O) MOS tranzistory."""
        return self._apply({"{C_MOS_HV}": corners}, kwargs)

    def sweep_bipolar(self, corners=["hbt_typ", "hbt_bcs", "hbt_wcs"], **kwargs):
        """Sweepuje heteropřechodové bipoláry (SiGe HBT)."""
        return self._apply({"{C_HBT}": corners}, kwargs)

    def sweep_res(self, corners=["res_typ", "res_bcs", "res_wcs"], **kwargs):
        """Sweepuje odděleně pouze rezistory."""
        return self._apply({"{C_RES}": corners}, kwargs)

    def sweep_cap(self, corners=["cap_typ", "cap_bcs", "cap_wcs"], **kwargs):
        """Sweepuje odděleně pouze kapacity."""
        return self._apply({"{C_CAP}": corners}, kwargs)

    def sweep_passives_combined(self, corners=["typ", "bcs", "wcs"], **kwargs) -> List[Dict[str, Any]]:
        """Synchronní sweep (odpory i kapacity se mění stejným směrem)."""
        # Musíme vracet pole slovníků, aby se to nekřížilo "každý s každým"
        return [self._apply({"{C_RES}": f"res_{c}", "{C_CAP}": f"cap_{c}"}, kwargs) for c in corners]


    # ==========================================
    # 3. CÍLENÉ WORST-CASE SCÉNÁŘE
    # ==========================================

    def wc_digital_speed(self, **kwargs):
        """Nejhorší rychlost logiky. Zima nebo horko (zvoleno 125), pomalé tranzistory, podpětí."""
        base = {"{C_MOS_LV}": "mos_ss", "{C_MOS_HV}": "mos_ss", "{TEMP}": 125, "{VDD}": self.vdd_min}
        return self._apply(base, kwargs)

    def wc_rc_delay(self, **kwargs):
        """Maximalizace časové konstanty tau = R*C. Zásadní pro analogové filtry."""
        base = {"{C_RES}": "res_wcs", "{C_CAP}": "cap_wcs"}
        return self._apply(base, kwargs)

    def wc_power_leakage(self, **kwargs):
        """Největší únikový (statický) proud. Rychlé (low Vth) tranzistory, horko, přepětí."""
        base = {"{C_MOS_LV}": "mos_ff", "{C_MOS_HV}": "mos_ff", "{C_RES}": "res_bcs", "{TEMP}": 125, "{VDD}": self.vdd_max}
        return self._apply(base, kwargs)

    def wc_analog_gain(self, **kwargs):
        """Minimální zisk analogových zesilovačů (gm/gds degradace)."""
        # Tranzistory s krátkým kanálem při vysoké teplotě a nízkém napájení trpí nejvíce.
        base = {"{C_MOS_LV}": "mos_fs", "{TEMP}": 125, "{VDD}": self.vdd_min}
        return self._apply(base, kwargs)

    def wc_noise_rf(self, **kwargs):
        """Maximalizace tepelného a 1/f šumu. Pomalé aktivní prvky a velké odpory."""
        base = {"{C_MOS_LV}": "mos_ss", "{C_HBT}": "hbt_wcs", "{C_RES}": "res_wcs", "{TEMP}": 125}
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
            "{C_RES}": ["res_typ", "res_bcs", "res_wcs"],
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
            "{C_HBT}": ["hbt_typ", "hbt_bcs", "hbt_wcs"],
            "{C_RES}": ["res_typ", "res_bcs", "res_wcs"],
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
            "{C_HBT}": ["hbt_typ", "hbt_bcs", "hbt_wcs"],
            "{C_RES}": ["res_typ", "res_bcs", "res_wcs"],
            "{TEMP}": [-40, 25, 125],
            "{VDD}": [self.vdd_min, self.vdd_nom, self.vdd_max]
        }
        return self._apply(base, kwargs)