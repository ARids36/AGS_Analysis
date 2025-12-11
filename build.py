"""Run process to create new .exe file"""

import subprocess

# --- CONFIGURATION ---
EXE_NAME = "AgsAnalysisApp"
MAIN_SCRIPT = 'ags_analysis.py'
DATA_DIR_NAME = 'data'
# ---------------------

# The format for --add-data is: <source>;<destination> (on Windows)
# This command tells PyInstaller to take the entire local 'data_files' folder
# and place it in a folder also named 'data_files' inside the executable.

pyinstaller_command = [
    'pyinstaller',
    '--onefile',         # Creates a single EXE file
    '--windowed',        # Prevents the console (terminal) window from appearing
    '--name', EXE_NAME,
    '--add-data', f'{DATA_DIR_NAME};{DATA_DIR_NAME}',
    MAIN_SCRIPT
]

print(f"Starting PyInstaller build for {EXE_NAME}.exe...")
try:
    # Run the PyInstaller command
    subprocess.run(pyinstaller_command, check=True)
    print("\n✅ Build Successful!")
    print(f"Your executable is located at: dist\\{EXE_NAME}.exe")
    print("You can now share this file with your colleagues.")

except subprocess.CalledProcessError as e:
    print(f"\n❌ Build Failed with error code {e.returncode}")
    print("Check the warnings/errors above and ensure all package names are correct.")