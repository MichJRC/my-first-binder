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

# create_and_upload_geodata.gpkg in the git release so that I can access it in in the download_data folder
import geopandas as gpd
import subprocess
import os

def create_geodata():
    """code to create the GeoPackage"""
    # ... data processing code ...
    merged_gdf.to_file("data/merged_geodata.gpkg", driver="GPKG")
    print("GeoPackage created successfully!")

def upload_to_release():
    """Upload to GitHub release using GitHub CLI"""
    try:
        # Check if file exists
        if not os.path.exists("data/merged_geodata.gpkg"):
            print("Error: GeoPackage file not found!")
            return
        
        # Upload to release
        result = subprocess.run([
            "gh", "release", "upload", "v1.0.0", 
            "data/merged_geodata.gpkg", "--clobber"  # --clobber replaces if exists
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("Successfully uploaded to GitHub release!")
            print(f"Download URL will be:")
            print(f"https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/merged_geodata.gpkg")
        else:
            print(f"Upload failed: {result.stderr}")
            
    except Exception as e:
        print(f"Error uploading: {e}")

if __name__ == "__main__":
    create_geodata()
    upload_to_release()

