import os
import shutil
import zipfile

# --- Configuration ---
BUILD_DIR = "build"
EXTENSION_SOURCE_DIR = "extension"
CHROME_DIR = os.path.join(BUILD_DIR, "chrome")
FIREFOX_DIR = os.path.join(BUILD_DIR, "firefox")

# List of all files and folders to be included in the extension packages
COMMON_FILES = [
    "background.js",
    "icon.png",
    "popup.css",
    "popup.html",
    "popup.js",
    "deps" # Include the whole dist folder
]
# --- End Configuration ---

def create_zip(source_dir, zip_path):
    """Creates a zip archive from a source directory."""
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Create a relative path for the files inside the zip
                archive_name = os.path.relpath(file_path, source_dir)
                zipf.write(file_path, archive_name)
    print(f"  -> Successfully created archive: {zip_path}")

def build_extension(target_dir, manifest_name):
    """Builds a single extension package for a specific browser."""
    print(f"\nBuilding package for {os.path.basename(target_dir)}...")
    
    # Create the target directory
    os.makedirs(target_dir, exist_ok=True)
    
    # Copy all common files and folders
    for item in COMMON_FILES:
        source_path = os.path.join(EXTENSION_SOURCE_DIR, item)
        dest_path = os.path.join(target_dir, item)
        if os.path.isdir(source_path):
            shutil.copytree(source_path, dest_path)
        else:
            shutil.copy(source_path, dest_path)
    print(f"  -> Copied {len(COMMON_FILES)} common items.")
    
    # Copy and rename the correct manifest file
    manifest_source = os.path.join(EXTENSION_SOURCE_DIR, manifest_name)
    manifest_dest = os.path.join(target_dir, "manifest.json")
    shutil.copy(manifest_source, manifest_dest)
    print(f"  -> Copied and renamed '{manifest_name}' to 'manifest.json'.")
    
    # Create the zip file
    zip_filename = f"{os.path.basename(target_dir)}_extension.zip"
    zip_path = os.path.join(BUILD_DIR, zip_filename)
    create_zip(target_dir, zip_path)

def main():
    """Main function to run the build process."""
    print("--- Starting Extension Build Process ---")
    
    # Clean up old build directory if it exists
    if os.path.exists(BUILD_DIR):
        print(f"Removing old '{BUILD_DIR}' directory...")
        shutil.rmtree(BUILD_DIR)
    
    # Create the main build directory
    os.makedirs(BUILD_DIR)
    
    # Build both extension packages
    build_extension(CHROME_DIR, "manifest-chrome.json")
    build_extension(FIREFOX_DIR, "manifest-firefox.json")
    
    print("\n--- Build process completed successfully! ---")
    print(f"Your packaged extensions are in the '{BUILD_DIR}' folder.")

if __name__ == "__main__":
    main()