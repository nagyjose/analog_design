from eda_framework.eda_engine import WorkspaceManager, NgspiceRunner

# 1. Inicializace projektu (ukazujeme do kořenové složky projektu)
ws = WorkspaceManager(project_root="..")
ws.clear_work_directory()
engine = NgspiceRunner(ws)

print("EDA Workspace pro projekt Test_OPA je připraven!")
print("1. Nakreslete schéma v ../schematics/")
print("2. Vygenerujte netlist (automaticky spadne do ../netlists/)")
print("3. Zde doplňte spouštěcí logiku a spusťte simulaci.")
