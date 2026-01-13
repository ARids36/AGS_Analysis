import subprocess
import os
import shutil

# --- CONFIGURATION ---
EXE_NAME = "AgsAnalysisApp"
SPEC_FILE = f"{EXE_NAME}.spec"
# ---------------------

def run_build():
    # 1. Check if the .spec file actually exists
    if not os.path.exists(SPEC_FILE):
        print(f"Error: {SPEC_FILE} not found!")
        print("You may need to run your old build script once more to generate it.")
        return

    print(f"Starting PyInstaller build using: {SPEC_FILE}")

    try:
        # 2. Run PyInstaller using the spec file
        # Note: We don't need --onefile or --add-data here;
        # those are already saved inside the .spec file.
        subprocess.run(['pyinstaller', '--noconfirm', SPEC_FILE], check=True)

        print("\nBuild Successful!")
        print(f"Location: dist/{EXE_NAME}.exe")

        # 3. Optional: Clean up the 'build' folder to keep your directory tidy
        if os.path.exists('build'):
            shutil.rmtree('build')
            print("Cleanup: Removed temporary 'build' directory.")

    except subprocess.CalledProcessError as e:
        print(f"\nBuild Failed with error code {e.returncode}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")

if __name__ == "__main__":
    run_build()