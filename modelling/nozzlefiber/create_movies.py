#!/usr/bin/env python3
"""
Create MP4 movies from sequentially numbered PNG files in MD subfolders.

This script:
1. Searches for all folders starting with 'md' and ending with '_output'
2. For each folder, looks for PNG files with sequential numbering
3. Creates an MP4 movie using ffmpeg with the folder name (without '_output') + '.mp4'
4. Saves the movie inside the respective subfolder
5. Skips folders that don't contain PNG files
"""

import os
import subprocess
import glob
import re
from pathlib import Path

def find_png_sequences(folder_path):
    """
    Find PNG files in a folder and determine if they form a sequence.
    Returns the pattern for ffmpeg input if a sequence is found, None otherwise.
    """
    png_files = glob.glob(os.path.join(folder_path, "*.png"))
    if not png_files:
        return None
    
    # Sort the PNG files to analyze the naming pattern
    png_files.sort()
    
    # Try to find a common pattern with sequential numbering
    # Look for patterns like: prefix_number.png, prefix_number_suffix.png, etc.
    
    # Extract all numbers from filenames to find sequential patterns
    file_patterns = {}
    for png_file in png_files:
        basename = os.path.basename(png_file)
        # Find all numbers in the filename
        numbers = re.findall(r'\d+', basename)
        if numbers:
            # Use the last number as the sequence number (most likely to be sequential)
            seq_num = int(numbers[-1])
            # Create a pattern by replacing the last number with a placeholder
            pattern = basename
            for num in reversed(numbers):
                pattern = pattern.replace(num, '%03d', 1)  # Replace only the first occurrence from the end
                break
            
            if pattern not in file_patterns:
                file_patterns[pattern] = []
            file_patterns[pattern].append(seq_num)
    
    # Find the pattern with the most sequential numbers
    best_pattern = None
    best_count = 0
    
    for pattern, numbers in file_patterns.items():
        numbers.sort()
        # Check if numbers are sequential
        if len(numbers) > 1:
            sequential_count = 1
            for i in range(1, len(numbers)):
                if numbers[i] == numbers[i-1] + 1:
                    sequential_count += 1
                else:
                    break
            
            if sequential_count > best_count:
                best_count = sequential_count
                best_pattern = pattern
    
    if best_pattern and best_count > 1:
        return best_pattern
    
    # If no clear sequential pattern, just use the first PNG file pattern
    if png_files:
        first_file = os.path.basename(png_files[0])
        # Try to create a simple pattern
        numbers = re.findall(r'\d+', first_file)
        if numbers:
            # Replace the last number with %03d
            pattern = first_file
            last_num = numbers[-1]
            pattern = pattern.replace(last_num, '%03d')
            return pattern
    
    return None

def create_movie(folder_path, output_name, movies_dir):
    """
    Create an MP4 movie from PNG files in the given folder.
    """
    png_pattern = find_png_sequences(folder_path)
    if not png_pattern:
        print(f"  No suitable PNG sequence found in {folder_path}")
        return False
    
    input_pattern = os.path.join(folder_path, png_pattern)
    output_path = os.path.join(movies_dir, f"{output_name}.mp4")
    
    # FFmpeg command to create movie
    # -framerate 2: 2 frames per second (adjust as needed)
    # -i: input pattern
    # -vf pad: pad to make dimensions divisible by 2 (required for H.264)
    # -c:v libx264: use H.264 codec
    # -pix_fmt yuv420p: pixel format for compatibility
    # -y: overwrite output file if it exists
    cmd = [
        'ffmpeg',
        '-framerate', '2',  # 2 FPS - adjust if needed
        '-i', input_pattern,
        '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',  # Pad to make dimensions even
        '-c:v', 'libx264',
        '-pix_fmt', 'yuv420p',
        '-y',  # Overwrite existing file
        output_path
    ]
    
    try:
        print(f"  Creating movie: {output_name}.mp4")
        print(f"  Input pattern: {png_pattern}")
        print(f"  Output location: movies/{output_name}.mp4")
        
        # Run ffmpeg with suppressed output
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f"  ✓ Successfully created movies/{output_name}.mp4")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"  ✗ Error creating movie for {output_name}:")
        print(f"    {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"  ✗ ffmpeg not found. Please make sure ffmpeg is installed and in PATH.")
        return False

def main():
    """
    Main function to process all MD folders.
    """
    # Get the directory where this script is located
    script_dir = Path(__file__).parent
    
    # Create movies directory
    movies_dir = script_dir / "movies"
    movies_dir.mkdir(exist_ok=True)
    
    print("Creating movies from PNG sequences in MD folders...")
    print(f"Working directory: {script_dir}")
    print(f"Movies will be saved to: {movies_dir}")
    print()
    
    # Find all folders that match the pattern md*_output
    md_folders = []
    for item in script_dir.iterdir():
        if item.is_dir() and item.name.startswith('md') and item.name.endswith('_output'):
            md_folders.append(item)
    
    if not md_folders:
        print("No MD folders found matching pattern 'md*_output'")
        return
    
    # Sort folders for consistent processing order
    md_folders.sort(key=lambda x: x.name)
    
    print(f"Found {len(md_folders)} MD folders to process:")
    for folder in md_folders:
        print(f"  - {folder.name}")
    print()
    
    successful_movies = 0
    skipped_folders = 0
    
    # Process each folder
    for folder in md_folders:
        folder_name = folder.name
        # Extract the base name (remove '_output' suffix)
        output_name = folder_name.replace('_output', '') if folder_name.endswith('_output') else folder_name
        
        print(f"Processing {folder_name}...")
        
        # Check if folder contains PNG files
        png_files = list(folder.glob("*.png"))
        if not png_files:
            print(f"  No PNG files found. Skipping.")
            skipped_folders += 1
            print()
            continue
        
        print(f"  Found {len(png_files)} PNG files")
        
        # Create the movie
        success = create_movie(str(folder), output_name, str(movies_dir))
        if success:
            successful_movies += 1
        
        print()
    
    # Summary
    print("="*50)
    print(f"Processing complete!")
    print(f"Successfully created: {successful_movies} movies")
    print(f"Skipped folders: {skipped_folders}")
    print(f"Total folders processed: {len(md_folders)}")

if __name__ == "__main__":
    main()