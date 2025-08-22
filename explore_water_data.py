#!/usr/bin/env python3
"""
Script to explore the water/ice TIFF data structure and values
"""

import rasterio
import numpy as np
import os
from pathlib import Path

def find_water_files():
    """Find all TIFF files in the water data directory"""
    water_dir = Path("data/water_data_milan/water_data_milan/result")
    tiff_files = []
    
    if water_dir.exists():
        for root, dirs, files in os.walk(water_dir):
            for file in files:
                if file.endswith(('.tif', '.tiff')):
                    tiff_files.append(os.path.join(root, file))
    
    return tiff_files

def examine_water_file(filepath):
    """Examine a single water TIFF file"""
    print(f"\n{'='*60}")
    print(f"Examining: {os.path.basename(filepath)}")
    print(f"{'='*60}")
    
    try:
        with rasterio.open(filepath) as src:
            print(f"📐 Dimensions: {src.width} x {src.height} pixels")
            print(f"📊 Data type: {src.dtypes[0]}")
            print(f"🗺️  CRS: {src.crs}")
            print(f"📍 Bounds: {src.bounds}")
            print(f"🔢 Band count: {src.count}")
            
            # Read the data
            data = src.read(1)
            
            # Get basic statistics
            print(f"\n📈 Data Statistics:")
            print(f"   Shape: {data.shape}")
            print(f"   Min value: {data.min()}")
            print(f"   Max value: {data.max()}")
            print(f"   Mean: {data.mean():.2f}")
            print(f"   No-data value: {src.nodata}")
            
            # Get unique values (for classification data)
            unique_values = np.unique(data)
            print(f"\n🏷️  Unique values in data: {unique_values[:20]}...")  # Show first 20
            print(f"   Total unique values: {len(unique_values)}")
            
            # Value frequency
            print(f"\n📊 Value frequencies:")
            unique, counts = np.unique(data, return_counts=True)
            total_pixels = data.size
            
            for val, count in zip(unique[:10], counts[:10]):  # Show top 10
                percentage = (count / total_pixels) * 100
                print(f"   Value {val}: {count:,} pixels ({percentage:.1f}%)")
            
            return {
                'filepath': filepath,
                'shape': data.shape,
                'crs': src.crs,
                'bounds': src.bounds,
                'unique_values': unique_values,
                'transform': src.transform
            }
            
    except Exception as e:
        print(f"❌ Error reading {filepath}: {e}")
        return None

def main():
    """Main function to explore all water data files"""
    print("🌊 Water Data Explorer")
    print("=" * 60)
    
    # Find all TIFF files
    tiff_files = find_water_files()
    
    if not tiff_files:
        print("❌ No TIFF files found in water_data_milan/result/")
        print("Make sure the data was extracted properly.")
        return
    
    print(f"📁 Found {len(tiff_files)} TIFF files")
    
    # Examine each file
    file_info = []
    for tiff_file in tiff_files:
        info = examine_water_file(tiff_file)
        if info:
            file_info.append(info)
    
    # Summary
    print(f"\n🎯 SUMMARY")
    print(f"={'*'*60}")
    print(f"Total water files processed: {len(file_info)}")
    
    if file_info:
        print(f"Coordinate system: {file_info[0]['crs']}")
        print(f"Typical image size: {file_info[0]['shape']}")
        
        # Combined bounds
        all_bounds = [info['bounds'] for info in file_info]
        min_x = min(bounds.left for bounds in all_bounds)
        min_y = min(bounds.bottom for bounds in all_bounds)
        max_x = max(bounds.right for bounds in all_bounds)
        max_y = max(bounds.top for bounds in all_bounds)
        
        print(f"Coverage area bounds:")
        print(f"  West: {min_x:.2f}")
        print(f"  South: {min_y:.2f}")
        print(f"  East: {max_x:.2f}")
        print(f"  North: {max_y:.2f}")

if __name__ == "__main__":
    main()