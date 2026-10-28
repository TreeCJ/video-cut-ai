"""Repair corrupted audio files."""

import subprocess
from pathlib import Path


def check_m4a_valid(file_path: Path) -> bool:
    """Check if an M4A file has valid moov atom."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(file_path), "-f", "null", "-"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.returncode == 0
    except Exception as e:
        print(f"Error checking file: {e}")
        return False


def repair_m4a_file(input_path: Path, output_path: Path = None) -> Path:
    """Repair a corrupted M4A file by re-encoding it."""
    if output_path is None:
        output_path = input_path.with_suffix(".fixed.m4a")
    
    print(f"Attempting to repair: {input_path.name}")
    
    # Try to copy streams without re-encoding first
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-c", "copy",  # Copy without re-encoding
            str(output_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    
    if result.returncode == 0 and output_path.exists():
        print(f"✓ Repair successful (stream copy): {output_path.name}")
        return output_path
    
    # If stream copy fails, try re-encoding
    print("Stream copy failed, trying re-encode...")
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i", str(input_path),
            "-acodec", "aac",
            "-ar", "16000",
            "-ac", "1",
            str(output_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    
    if result.returncode == 0 and output_path.exists():
        print(f"✓ Repair successful (re-encode): {output_path.name}")
        return output_path
    
    print(f"✗ Repair failed for: {input_path.name}")
    print(f"Error: {result.stderr}")
    return None


def find_and_repair_corrupted_files(output_dir: Path):
    """Find all corrupted M4A files and attempt repair."""
    corrupted_count = 0
    repaired_count = 0
    
    for m4a_file in output_dir.rglob("*.m4a"):
        print(f"\nChecking: {m4a_file.name}")
        
        if not check_m4a_valid(m4a_file):
            print(f"  ✗ CORRUPTED - Attempting repair...")
            corrupted_count += 1
            
            repaired_file = repair_m4a_file(m4a_file)
            if repaired_file:
                repaired_count += 1
                # Replace original with repaired version
                backup = m4a_file.with_suffix(".m4a.backup")
                m4a_file.rename(backup)
                repaired_file.rename(m4a_file)
                print(f"  ✓ Original file replaced with repaired version")
                print(f"  ℹ Backup saved as: {backup.name}")
            else:
                print(f"  ✗ Could not repair this file")
        else:
            print(f"  ✓ OK")
    
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Corrupted files found: {corrupted_count}")
    print(f"  Successfully repaired: {repaired_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import sys
    
    output_dir = Path("output")
    if len(sys.argv) > 1:
        output_dir = Path(sys.argv[1])
    
    if not output_dir.exists():
        print(f"Error: Directory {output_dir} does not exist")
        sys.exit(1)
    
    print(f"Scanning for corrupted M4A files in: {output_dir}")
    find_and_repair_corrupted_files(output_dir)
