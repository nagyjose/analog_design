from eda_engine import WorkspaceManager

# Inicializujeme workspace v aktuální složce pro projekt "Moje_OTA"
ws = WorkspaceManager(project_root="./Moje_OTA")

# Před velkou simulací vyčistíme pískoviště
ws.clear_work_directory()

# Vytvoříme pískoviště pro dvě různé simulace
sandbox_1 = ws.create_sandbox(run_id="tt_25C")
sandbox_2 = ws.create_sandbox(run_id="ss_125C")

print(f"Běžím simulaci 1 v: {sandbox_1}")
print(f"Běžím simulaci 2 v: {sandbox_2}")