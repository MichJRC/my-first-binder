import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

# Load the shapefile
print("Loading shapefile...")
gdf = gpd.read_file('downloaded_data/GSA2024LB/GSA-2024_Lombardia.shp')

# Basic information about the data
print(f"✅ Shapefile loaded successfully!")
print(f"📊 Shape: {gdf.shape} (rows, columns)")
print(f"📍 Coordinate system: {gdf.crs}")

# Show column names
print(f"\n📋 Columns in the dataset:")
print(gdf.columns.tolist())

# Show first few rows
print(f"\n🔍 First 5 rows:")
print(gdf.head())

# Basic statistics
print(f"\n📈 Dataset info:")
print(f"Total features: {len(gdf)}")
print(f"Geometry type: {gdf.geometry.geom_type.iloc[0]}")

# Show some sample data (first feature)
print(f"\n📝 Sample feature:")
print(gdf.iloc[0])

main_crop_stats = gdf.groupby("main_crop").size().reset_index(name="count")
main_crop_stats.to_csv("data/main_crop_statistics.csv", index=False)
print("\n🌾 Main crop statistics exported to main_crop_statistics.csv")

import re
# Read the files
IT_CODES = pd.read_csv("data/IT-crops_codes_and_crops_names_table-27061968.csv", sep=";", encoding="latin1")
IT_HCAT = pd.read_csv("data/IT_HCAT.csv", sep=";", encoding="latin1")

# Normalize whitespace: replace multiple spaces with single space AND trim
IT_CODES['crop_name_clean'] = IT_CODES['crop_name'].str.replace(r'\s+', ' ', regex=True).str.strip()
IT_HCAT['Italian_Name_clean'] = IT_HCAT['Italian_Name'].str.replace(r'\s+', ' ', regex=True).str.strip()

IT_HCAT_merged_IT_codes = pd.merge(IT_HCAT, IT_CODES[['crop_name_clean', 'main_crop']], left_on='Italian_Name_clean', right_on='crop_name_clean', how='left')
IT_HCAT_merged_IT_codes.to_csv("data/IT_HCAT_merged_IT_codes.csv", index=False)

IT_HCAT_merged_IT_codes = pd.read_csv("data/IT_HCAT_merged_IT_codes.csv")
print(IT_HCAT_merged_IT_codes["main_crop"].isnull().sum())

merged_gdf = gdf.merge(IT_HCAT_merged_IT_codes,  left_on='main_crop', right_on='main_crop', how='left')
merged_gdf.to_file("data/merged_geodata.gpkg", driver="GPKG")

unmatched_main_crops = merged_gdf[merged_gdf['crop_name_clean'].isna()]['main_crop']

gdf['main_crop_clean'] = gdf['main_crop'].astype(str).str.zfill(3)
IT_HCAT_merged_IT_codes['main_crop_clean'] = IT_HCAT_merged_IT_codes['main_crop'].astype(str).str.zfill(3)

gdf_samples_sorted = sorted(gdf['main_crop_clean'].unique())
print(f"IT_HCAT samples (sorted): {gdf_samples_sorted[:10]}")

IT_HCAT_merged_IT_codes_sorted = sorted(IT_HCAT_merged_IT_codes['main_crop_clean'].unique())
print(f"IT_HCAT samples (sorted): {IT_HCAT_merged_IT_codes_sorted[:10]}")