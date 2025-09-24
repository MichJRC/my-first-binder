import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import re
import numpy

# Load the shapefile
gdf = gpd.read_file('downloaded_data/GSA2024LB/GSA-2024_Lombardia.shp')

# Basic information about the data
print(f"📊 Shape: {gdf.shape} (rows, columns)")
print(f"📍 Coordinate system: {gdf.crs}")
print(gdf.columns.tolist())
print(gdf.head())
print(f"Total features: {len(gdf)}")
print(f"Geometry type: {gdf.geometry.geom_type.iloc[0]}")
print(gdf.iloc[0])

# Make some initial stats on the shapefile
main_crop_stats = gdf.groupby("main_crop").size().reset_index(name="count")
main_crop_stats.to_csv("data/main_crop_statistics.csv", index=False)

# Read the italian codes files, and make the merge with the HCAT classes
IT_CODES = pd.read_csv("data/IT-crops_codes_and_crops_names_table-27061968.csv", sep=";", encoding="latin1")
IT_HCAT = pd.read_csv("data/IT_HCAT.csv", sep=";", encoding="latin1")

# Normalize whitespace: replace multiple spaces with single space AND trim
IT_CODES['crop_name_clean'] = IT_CODES['crop_name'].str.replace(r'\s+', ' ', regex=True).str.strip()
IT_HCAT['Italian_Name_clean'] = IT_HCAT['Italian_Name'].str.replace(r'\s+', ' ', regex=True).str.strip()

IT_HCAT_merged_IT_codes = pd.merge(IT_HCAT, IT_CODES[['crop_name_clean', 'main_crop']], left_on='Italian_Name_clean', right_on='crop_name_clean', how='left')
IT_HCAT_merged_IT_codes.to_csv("data/IT_HCAT_merged_IT_codes.csv", index=False)

IT_HCAT_merged_IT_codes = pd.read_csv("data/IT_HCAT_merged_IT_codes.csv")
print(IT_HCAT_merged_IT_codes["main_crop"].isnull().sum())

# Prepare the shapefile column and the HCAT column code with the right format to make the merge
gdf['main_crop_clean'] = gdf['main_crop'].astype(str).str.zfill(3)
IT_HCAT_merged_IT_codes['main_crop_clean'] = IT_HCAT_merged_IT_codes['main_crop'].astype(str).str.zfill(3)

gdf_samples_sorted = sorted(gdf['main_crop_clean'].unique())
print(f"IT_HCAT samples (sorted): {gdf_samples_sorted[:10]}")

IT_HCAT_merged_IT_codes_sorted = sorted(IT_HCAT_merged_IT_codes['main_crop_clean'].unique())
print(f"IT_HCAT samples (sorted): {IT_HCAT_merged_IT_codes_sorted[:10]}")

def true_value_comparison(gdf_sorted, hcat_sorted):
    """Show values that actually match vs don't match"""
    all_values = sorted(set(gdf_sorted) | set(hcat_sorted))
    
    # Create data for DataFrame
    data = []
    for value in all_values:
        in_gdf = "✓" if value in gdf_sorted else "✗"
        in_hcat = "✓" if value in hcat_sorted else "✗"
        data.append({'Value': value, 'GDF': in_gdf, 'IT_HCAT': in_hcat})
    
    # Create and return DataFrame
    df = pd.DataFrame(data)
    return df

comp = true_value_comparison(gdf_samples_sorted, IT_HCAT_merged_IT_codes_sorted)
comp.to_csv('data/comparison_GSA_Lombardia_HCAT.csv', index=False)

# print only the values that are in gdg but nor referenced in the HCAT
gdf_only = comp[(comp['GDF'] == '✓') & (comp['IT_HCAT'] == '✗')]
print(gdf_only)

# Count how many times each value appears in the original GDF
value_counts = gdf['main_crop_clean'].value_counts()
total_polygons = len(gdf)
gdf_only = gdf_only.copy()
gdf_only['number_polygons'] = gdf_only['Value'].map(value_counts)
gdf_only['ratio_on_total'] = (gdf_only['number_polygons'] / total_polygons).round(4)
unmatchedGdf_HCAT = gdf_only.to_csv('data/unmatchedGdf_HCAT_stats.csv', index=False)

# From the Lombardia shapefile make the merge with the HCAT classes
merged_gdf = gdf.merge(
    IT_HCAT_merged_IT_codes[['Italian_Name', 'English_Name', 'HCAT2_Name', 
                            'HCAT2_Code', 'Direct_Match', 'Reason', 
                            'crop_name_clean', 'main_crop_clean']], 
    left_on='main_crop_clean', 
    right_on='main_crop_clean', 
    how='left'
)

for index, row in merged_gdf.iterrows():
    print(row)
    break

# how many polygons are not matching the hcat classes (853)
unmatched_main_crops = merged_gdf[merged_gdf['crop_name_clean'].isna()]['main_crop']

# ============================================================================
# 🆕 NEW: Add CSV merge for EC and HRL classifications
# ============================================================================
print("\n🔗 Adding EC and HRL classifications...")

# Load CSV classifications
csv_classifications = pd.read_csv("data/hcat3_EC_HRL_fixed.csv")
print(f"   ✅ CSV loaded: {len(csv_classifications)} classification entries")

# Convert HCAT2_Code to integer for matching (handle NaN values)
print(f"   Original HCAT2_Code type: {merged_gdf['HCAT2_Code'].dtype}")
merged_gdf['HCAT2_Code'] = pd.to_numeric(merged_gdf['HCAT2_Code'], errors='coerce').astype('Int64')
print(f"   Converted HCAT2_Code type: {merged_gdf['HCAT2_Code'].dtype}")
print(f"   Non-null HCAT2_Code values: {merged_gdf['HCAT2_Code'].notna().sum():,}")

# Perform the CSV merge
final_gdf = merged_gdf.merge(
    csv_classifications,
    left_on='HCAT2_Code', 
    right_on='hcat3_code',
    how='left'  # Keep all parcels
)

# Check merge success
total_parcels = len(final_gdf)
ec_matches = final_gdf['ec_name'].notna().sum()
hrl_matches = final_gdf['hrl_name'].notna().sum()

print(f"   📊 Merge results:")
print(f"     Total parcels: {total_parcels:,}")
print(f"     EC matches: {ec_matches:,} ({ec_matches/total_parcels*100:.1f}%)")
print(f"     HRL matches: {hrl_matches:,} ({hrl_matches/total_parcels*100:.1f}%)")
print(f"     Final columns: {len(final_gdf.columns)} (original: {len(gdf.columns)})")

# Show new column names
original_cols = set(merged_gdf.columns)
new_cols = [col for col in final_gdf.columns if col not in original_cols]
print(f"     New columns added: {new_cols}")

# Memory check
original_memory = merged_gdf.memory_usage(deep=True).sum() / 1024 / 1024
final_memory = final_gdf.memory_usage(deep=True).sum() / 1024 / 1024
print(f"   💾 Memory: {original_memory:.1f} MB → {final_memory:.1f} MB (+{final_memory-original_memory:.1f} MB)")

print("   ✅ CSV merge completed successfully!")

# ============================================================================
# Update the create_geodata function to use final_gdf
# ============================================================================

import subprocess
import os

def create_geodata(geodataframe):
    """Create the enhanced GeoPackage with EC and HRL classifications"""
    print("\n💾 Creating enhanced GeoPackage...")
    
    # Save the final geodataframe with all classifications
    geodataframe.to_file("data/merged_geodata.gpkg", driver="GPKG")
    
    file_size = os.path.getsize("data/merged_geodata.gpkg") / 1024 / 1024
    print(f"   ✅ Enhanced GeoPackage created: {file_size:.1f} MB")
    print(f"   📊 Contains: {len(geodataframe)} parcels with {len(geodataframe.columns)} columns")
    print(f"   🎨 Ready for visualization with EC and HRL categories!")

def upload_to_release():
    """Upload to GitHub release using GitHub CLI"""
    try:
        # Check if file exists
        if not os.path.exists("data/merged_geodata.gpkg"):
            print("Error: GeoPackage file not found!")
            return
        
        print("\n☁️ Uploading to GitHub release...")
        
        # Upload to release
        result = subprocess.run([
            "gh", "release", "upload", "v1.0.0", 
            "data/merged_geodata.gpkg", "--clobber"  # --clobber replaces if exists
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("   ✅ Successfully uploaded to GitHub release!")
            print(f"   🔗 Download URL:")
            print(f"   https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/merged_geodata.gpkg")
            print(f"\n   🎯 Users will now get:")
            print(f"     • All 635,808 agricultural parcels")
            print(f"     • HCAT classifications")
            print(f"     • EC categories (European Commission standards)")
            print(f"     • HRL categories (High Resolution Layer)")
            print(f"     • Ready for immediate web visualization!")
        else:
            print(f"   ❌ Upload failed: {result.stderr}")
            
    except Exception as e:
        print(f"   ❌ Error uploading: {e}")

if __name__ == "__main__":
    create_geodata(final_gdf)  # Pass final_gdf as parameter
    upload_to_release()