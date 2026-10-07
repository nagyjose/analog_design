Tento architektonický rozpad je naprosto ukázkový. V podstatě jste právě koncepčně navrhl architekturu nástroje typu **Cadence ADE Assembler**, jen v moderním Python kabátu. Rozdělení na tyto 4 pilíře je logické, protože každý typ analýzy vyžaduje jiný přístup k datům a k samotnému enginu Ngspice.

Pojďme to rozebrat čistě koncepčně, bez psaní kódu, abychom viděli, jaké výzvy a možnosti se před námi otevírají.

### 1. Architektura Simulačního Enginu (4 pilíře)

Abyste nemusel pro každou simulaci psát specifický kód, framework by měl mít jednu společnou "páteř" a čtyři různé "manažery" (Runners).

* **Obyčejná (Single Run) analýza:**
Toto je nejjednodušší případ, který už máte vyřešený. Předáte jeden stav parametrů, simulátor jednou proběhne, vrátí jeden datový set. Slouží pro rychlé ověření topologie.
* **Parametrická analýza (Sweep):**
Konceptuálně jde o vytvoření N-dimenzionální mřížky (Cartesian product). Pokud řeknete $W = [1, 2, 3]\ \mu\text{m}$ a $L = [0.1, 0.2]\ \mu\text{m}$, framework automaticky vygeneruje matici 6 simulací. Klíčové zde bude vymyslet, zda je pustit sériově (v jednom vlákně) nebo přidat *Multiprocessing* a pustit jich 6 naráz na různých jádrech procesoru.
* **PVT (Corner) analýza:**
Máte pravdu, že nemá smysl to programovat pokaždé znovu. PVT je vlastně jen "vylepšená" parametrická analýza s pevně danými pravidly. Framework by měl mít předdefinované slovníky: např. že kout `FF` (Fast-Fast) se vždy kombinuje s napětím $+10\ \%$ a teplotou $-40\ ^\circ\text{C}$ (tzv. Best-Case) a $125\ ^\circ\text{C}$ (High-Leakage). Vy byste enginu řekl pouze `spust_pvt(druh="full")` a on by už sám věděl, že má vygenerovat matici 27, 45 nebo více extrémních stavů.
* **Monte Carlo (MC):**
Zde leží největší architektonická past. Pokud by Python restartoval program Ngspice 1000x za sebou, trvalo by to věčnost kvůli režii spouštění procesu. Koncept pro Monte Carlo by měl vypadat tak, že Python pouze dynamicky napíše obrovský `.control` blok, který udělá 1000 smyček *přímo uvnitř* paměti Ngspice. Python pak načte až jeden finální, gigantický RAW soubor obsahující všech 1000 běhů a provede nad ním statistiku.

### 2. Datový Sklad (Jak udržet pořádek ve výsledcích)

Když pustíte PVT analýzu o 45 stavech, vrátí se vám obrovské množství dat. Náš současný přístup (kde každá křivka je samostatná proměnná) by zkolaboval.
Bude potřeba koncept "Datového repozitáře". Výsledkem jakékoliv z těch 4 analýz by měl být jeden standardizovaný objekt (např. slovník Pandas DataFramů), kde metadata (hodnoty $W$, $L$, Teploty a Rohu) budou fungovat jako klíče (štítky). Vaše analytické nástroje z `eda_tools.py` se pak nebudou volat na jednu proměnnou, ale aplikují se hromadně (map-reduce) na celý tento repozitář.

### 3. Koncepce automatického vizualizéru (Auto-Plotter)

Tohle je přesně ta část, kde se návrháři nejvíce nadřou, a kterou zmiňujete jako první cíl optimalizace. Dosud jste musel každou čáru (`add_trace`) a její barvu psát ručně. Profesionální framework by měl mít třídu `AutoPlotter`, která řeší následující problémy:

* **Chytré palety a Cyklování:** Pokud do grafu posíláte 10 křivek pro různé $W$, vizualizér si automaticky vezme předdefinovanou vizuální paletu (např. gradient od modré po červenou) a rozdělí ji na 10 kroků. Nemusíte definovat barvy ručně.
* **Konzistence barev (Color Mapping):** Tohle je kritické pro PVT. Pokud je roh `mos_tt` zelený a `mos_ff` modrý v grafu pro $I_{drain}$, framework musí zajistit, že i v grafu pro $g_m$ (nebo v úplně jiném okně simulace) zůstanou tyto barvy stejné. Lidé mají vizuální paměť.
* **Hierarchická legenda (Grouping):** V interaktivních grafech Plotly se dá využít `legendgroup`. Pokud máte 27 rohů PVT, nechcete legendu se 27 položkami, které musíte vyklikávat po jedné. Vizualizér je musí seskupit. Kliknete na "Teplota 125", a v grafu okamžitě zmizí (nebo se objeví) všechny křivky (SS, TT, FF), které byly měřeny při této teplotě.
* **Řízení průhlednosti (Alpha Channel):** Pro Monte Carlo s 1000 běhy by neprůhledné čáry vytvořily jednolitou černou skvrnu a shodily prohlížeč. Auto-Plotter musí rozeznat, že jde o MC data, vykreslit oněch 1000 běhů např. s 2% průhledností a *přes ně* automaticky vynesit tučnou bílou čáru průměru ($\mu$) a červené hranice ($\pm 3\sigma$).
* **Auto-Subplots:** Místo abyste ručně definoval řádky a sloupce `row=1, col=1`, předáte vizualizéru jen seznam signálů (např. `["Idrain", "gm", "Vout"]`) a on si sám spočítá, že potřebuje vytvořit mřížku 3x1, a křivky tam inteligentně rozhodí.



### Kudy dál?

Tato architektura by z vašeho řešení udělala komerčně konkurenceschopný nástroj. Základem úspěchu bude postavit pevné rozhraní mezi enginem (Ngspice) a daty (Pandas), protože grafika i analytické markery z `eda_tools.py` pak budou fungovat automaticky.

Máme začít návrhem **Třídy pro automatický Plotting** (řešení barev, legend a subplotů), nebo navrhneme hierarchii **Simulačních Runnerů** (Parametric/PVT/Monte Carlo)?

###

Tohle je přesně ten moment, kdy přecházíte od „psaní skriptů“ k „softwarovému inženýrství“. Váš návrh modulární architektury naprosto přesně kopíruje to, jak jsou uvnitř postaveny obří komerční frameworky. Rozdělení na Engine, Data, Plot a Analysis (Markery) je logicky čisté, protože odděluje získávání dat od jejich zpracování a vizualizace (princip MVC - Model-View-Controller).

Zde je koncepční analýza vašeho návrhu a protinávrhy k adresářové struktuře a datovým tokům.

### 1. Architektura knihovny `eda_tools` (Python Package)

Pokud uděláme z `eda_tools` plnohodnotný Python balíček (složku s podmoduly), získáte obrovskou svobodu. Ve vašem hlavním simulačním skriptu pak opravdu jen zavoláte např. `from eda_tools import SimEngine, Plotter, Analyzer`.

Zde je rozpad zodpovědností jednotlivých modulů:

* **`eda_engine.py` (Řadič a Spouštěč):**
Tento modul vůbec neví, co je to graf nebo napětí. Jeho jedinou starostí je vzít textovou šablonu (SPICE netlist), nahradit v ní proměnné (teploty, rozměry, kouty), vytvořit dočasný soubor, spustit Ngspice na pozadí, pohlídat, jestli simulace nespadla (error handling), a vrátit cestu k vygenerovanému RAW nebo TXT souboru.
* **`eda_data.py` (Datový Sklad a Parser):**
Zde se surová binární nebo textová data z Ngspice načtou do paměti. Modul bude obsahovat funkce pro "čištění" dat, sjednocování časových os (pokud má každá simulace jiný časový krok) a především **strukturování pro vícenásobné běhy (PVT / Sweep)**. Bude uchovávat data v hierarchických strukturách, abyste se později mohl jednoduše zeptat: *"Dej mi Vout pro TT roh při 125 °C"*.
* **`eda_plot.py` (Automatický Vizualizér):**
Obal (wrapper) nad knihovnou Plotly. Bude obsahovat logiku pro automatické rozvržení podgrafů, chytré cyklování barev (aby stejné rohy měly vždy stejnou barvu napříč grafy), formátování os na SI jednotky (M, k, m, µ) a správu interaktivních legend.
* **`eda_analysis.py` (přejmenováno z `eda_marker.py`):**
Zde bude bydlet veškerá ta inteligentní matematika, kterou jsme vytvořili (THD, fázový šum, BW, zpoždění, P1dB). Navrhuji širší název "analysis" místo "marker", protože tyto nástroje data reálně počítají a analyzují, nejen graficky označují. Budou přijímat data z `eda_data` a grafický objekt z `eda_plot` a propojovat je.

### 2. Adresářový strom projektu (Workspace Management)

Zmínil jste klíčovou věc: každý projekt potřebuje vlastní složku s daty. Pokud spustíte parametrickou analýzu nebo Monte Carlo, Ngspice začne zběsile přepisovat výstupní soubory. Pokud nebudete mít striktní pořádek, data ze simulace A přepíšou data ze simulace B dříve, než je Python stihne přečíst.

V průmyslu se na to používá koncept **Sandboxing (Pískoviště)**. Koncepční návrh adresářové struktury pro každý váš hardwarový projekt by měl vypadat takto:

* **`Hardware_Project_Name/`** (Hlavní složka návrhu, např. LNA_130nm)
* **`schematics/`** (Zde pracuje pouze Xschem. Soubory `.sch` a `.sym`. Nikdy sem nezasahuje Python.)
* **`netlists/`** (Zde Xschem exportuje "zlaté šablony", např. `tb_lna_template.spice`. Jsou to read-only podklady pro Python.)
* **`simulations/`** (Zde pracuje váš Python skript. Sem patří váš hlavní spouštěcí soubor např. `run_pvt.py`.)
* **`work/`** (Dynamická, "špinavá" složka. Tuto složku bude plně ovládat modul `eda_engine`.)
* `run_tt_25C/` (Dočasné pískoviště pro 1. simulaci)
* `run_ss_125C/` (Dočasné pískoviště pro 2. simulaci)


* **`reports/`** (Čistá výstupní složka. Sem bude `eda_plot` a `eda_analysis` ukládat finální `.html` interaktivní grafy a `.csv` tabulky shrnující výsledky PVT.)



### 3. Koncept Sandboxingu (Proč potřebujeme dynamické složky `work/`)

Když engine dostane úkol spustit 5 různých simulací, nesmí je pustit ve stejném adresáři. Pokud byste v budoucnu přešel na paralelizaci (spuštění Ngspice na všech jádrech procesoru současně pro urychlení), vznikl by *Race Condition* – jedno vlákno by zapisovalo do `output.raw`, zatímco druhé by se ho snažilo číst.

Engine si proto pro každou variaci (např. kout SS, teplota -40) vytvoří dynamicky unikátní podsložku v adresáři `work/`. Do ní zkopíruje netlist, provede nahrazení proměnných, spustí v ní Ngspice a uloží tam RAW data. Jakmile `eda_data` tyto hodnoty načte do Python paměti (do strukturovaného DataFrame), engine může toto "pískoviště" rovnou smazat, aby vám simulace nezaplnily pevný disk desítkami gigabytů RAW souborů.

### 4. Datový tok (Jak to poletí skrz balíček)

Ve vašem hlavním simulačním skriptu se to poskládá do tohoto elegantního toku:

1. Definujete parametry (např. pole teplot a koutů).
2. Zavoláte **Engine**, předáte mu parametry a cestu k šabloně.
3. Engine vytvoří pískoviště, odřídí Ngspice a předá cesty k datům modulu **Data**.
4. **Data** modul vše zparsuje, sjednotí a vrátí vám jeden mocný, strukturovaný objekt (např. vícerozměrný slovník nebo MultiIndex DataFrame).
5. Tento datový objekt předáte modulu **Plot**, kterému jen řeknete: "Vykresli mi Idrain vůči Vgs pro všechny simulace". Plotter sám rozebere data, přiřadí konzistentní barvy a sestaví Plotly objekt.
6. Nakonec zavoláte modul **Analysis**, předáte mu hotový graf a část dat (např. nominální roh TT), aby do grafu zakreslil značky, vyhodnotil šířku pásma nebo spočítal THD.
7. Uložíte výsledek do složky `reports/`.

Dává vám toto rozdělení zodpovědností a izolace pracovních adresářů smysl?

###


Tento strategický plán (Roadmap) slouží jako architektonický blueprint našeho frameworku. Je navržen modulárně, abychom mohli implementovat a testovat každou část nezávisle.

Na konci tohoto plánu je navíc připraven **"Kontextový kotevní blok"** – krátký text, který mi v budoucnu jednoduše zkopírujete do promptu, abych si okamžitě načetl celou architekturu a přesně věděl, kde jsme skončili.

## Fáze 1: Adresářový Workspace a Sandboxing

Cílem je vytvořit bezpečné prostředí pro Ngspice, aby se soubory nepřepisovaly a disk se nezahltil.

* **Úkol:** Vytvořit inicializační skript (nebo součást enginu), který v projektu vygeneruje strukturu: `schematics/`, `netlists/`, `work/`, `reports/`.
* **Pískoviště (Sandboxing):** Naprogramovat logiku, která pro každý běh simulace vytvoří ve `work/` unikátní podsložku (např. `run_tt_25C_1_2V/`), provede v ní simulaci a po vytažení dat ji buď smaže, nebo ponechá pro debugování.

## Fáze 2: Jádro frameworku (`eda_engine.py`)

Tento modul bude fungovat jako dispečer (Controller). Nezná fyziku, řeší jen textové soubory a procesy OS.

* **Šablonování:** Třída, která načte "zlatý netlist" z Xschemu a pomocí slovníku (např. `{"{CORNER}": "mos_tt", "{TEMP}": "25"}`) dynamicky vygeneruje spustitelný SPICE soubor.
* **Execution Manager:** Obal nad knihovnou `subprocess`. Spustí Ngspice v batch módu (`-b`), odchytí případné chyby (crashe simulátoru) a vrátí absolutní cesty k vygenerovaným `.raw` nebo `.txt` datům.
* **Generátory úloh:** Funkce jako `generate_pvt_matrix()` nebo `generate_sweep_matrix()`, které na základě zadání (např. 3 kouty, 3 teploty) vytvoří seznam 9 úloh pro engine.

## Fáze 3: Datový sklad (`eda_data.py`)

Překladatel z binárního světa Ngspice do objektového světa Pandas.

* **RAW Parser:** Integrace open-source knihovny (např. `spyci`) pro bleskové čtení binárních `.raw` souborů.
* **Data Structuring:** Převod načtených dat do `pandas.DataFrame`.
* **Multi-Run Sklad:** Vytvoření zastřešujícího objektu (např. `SimulationResults`), který pojme výsledky z desítek běhů (PVT). Data budou indexována tak, abyste mohl snadno filtrovat: *"Dej mi Vout pro všechny běhy, kde Corner == 'SS'"*.

## Fáze 4: Inteligentní vizualizace (`eda_plot.py`)

Konec ručního formátování. Modul, který na jeden příkaz vygeneruje profesionální report.

* **AutoPlotter Třída:** Automaticky zjistí počet požadovaných signálů a dynamicky sestaví Plotly mřížku (Subplots).
* **Správa barev a legendy:** Logika, která zajistí, že např. roh `FF` bude napříč všemi podgrafy i budoucími simulacemi vždy modrý. Zapnutí `legendgroup` pro hromadné skrývání celých koutů jedním kliknutím.
* **Formátovací filtry:** Automatické převedení os X a Y na inženýrskou notaci (SI prefixy) na základě našich dosavadních funkcí.

## Fáze 5: Analytický arzenál (`eda_analysis.py`)

Zde přesuneme a adaptujeme všechny ty skvělé markery, které jsme doteď napsali (Zpoždění, BW, THD, P1dB, Skok, IP3).

* **Adaptace na API:** Upravit existující funkce tak, aby bezproblémově přijímaly roztříděná data z `eda_data.py` a kreslily do grafů generovaných v `eda_plot.py`.
* **Hromadná analýza (Map-Reduce):** Vytvoření wrapperů, které umožní zavolat např. měření "Šířky pásma" hromadně na celou PVT matici a vyhodí finální `.csv` tabulku (např. řádek = roh, sloupec = BW).

---

### 📌 KONTEXTOVÝ KOTEVNÍ BLOK (Pro budoucí prompty)

*Když naše konverzace v budoucnu vyprší, nebo otevřete nové okno, začněte svůj dotaz tímto textem:*

> **SYSTEM RESTORE:** Budujeme modulární Python framework pro automatizaci EDA návrhu s Ngspice (IHP 130nm PDK, IIC-OSIC-TOOLS). Architektura se skládá z:
> 1. `Workspace` (izolované dynamické složky pro běh simulací)
> 2. `eda_engine.py` (šablonování netlistů, spouštění Ngspice přes subprocess)
> 3. `eda_data.py` (čtení RAW souborů přes spyci do Pandas, správa PVT matic)
> 4. `eda_plot.py` (automatické generování Plotly podgrafů, konzistence barev rohů)
> 5. `eda_analysis.py` (naše hotové funkce pro THD, BW, IP3, zpoždění atd.)
> 
> 
> Navazujeme na fázi: **[ZDE DOPLŇTE, CO CHCETE ŘEŠIT, např. "Fáze 2 - Pojďme napsat třídu NgspiceRunner v eda_engine.py"]**