import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt

# Load the shapefile
print("Loading shapefile...")
gdf = gpd.read_file('data/GSA2024LB/GSA-2024_Lombardia.shp')

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

IT_CODES = pd.read_csv("/workspaces/my-first-binder/data/IT-crops_codes_and_crops_names_table-27061968.csv", sep=";", encoding="latin1")
IT_HCAT = pd.read_csv("data/IT_HCAT.csv", sep=";", encoding="latin1")

IT_HCAT_merged_IT_codes = pd.merge(IT_HCAT, IT_CODES[['crop_name', 'crop_code']], left_on='Italian_Name', right_on='crop_name', how='inner')