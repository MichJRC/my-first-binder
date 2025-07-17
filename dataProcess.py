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