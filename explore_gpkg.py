#!/usr/bin/env python3
"""
GPKG Data Exploration Script
Step 1: Understanding your geospatial data structure
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box
import warnings
warnings.filterwarnings('ignore')

def explore_gpkg(file_path):
    """
    Comprehensive exploration of a GPKG file
    """
    print("=" * 60)
    print("🗺️  GPKG FILE EXPLORATION")
    print("=" * 60)
    
    # First, check if file exists
    import os
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        print("Please check the file path and try again.")
        return None
    
    try:
        # Step 1: Check what layers exist in the GPKG
        print("\n📁 STEP 1: Available Layers")
        print("-" * 30)
        
        layers = gpd.list_layers(file_path)
        print(f"Found {len(layers)} layers in the GPKG file:")
        print(f"Layers DataFrame structure: {layers.columns.tolist()}")
        print("Raw layers info:")
        print(layers)
        print()
        
        # Handle different layer info formats
        layer_names = []
        if 'layer_name' in layers.columns:
            layer_names = layers['layer_name'].tolist()
        elif len(layers.columns) >= 1:
            layer_names = layers.iloc[:, 0].tolist()  # First column as layer names
        
        if not layer_names:
            print("❌ Could not extract layer names. Trying to read file directly...")
            # Try reading without specifying layer
            gdf = gpd.read_file(file_path)
            print(f"✅ Successfully read file directly!")
            print(f"Shape: {gdf.shape}")
            layer_names = ['default_layer']
        
        # Step 2: Explore each layer
        for layer_name in layer_names:
            print(f"\n📊 STEP 2: Exploring Layer '{layer_name}'")
            print("-" * 50)
            
            # Load the layer
            try:
                if layer_name == 'default_layer':
                    gdf = gpd.read_file(file_path)
                else:
                    gdf = gpd.read_file(file_path, layer=layer_name)
            except Exception as layer_error:
                print(f"❌ Could not read layer '{layer_name}': {layer_error}")
                continue
            
            # Basic info
            print(f"Shape: {gdf.shape} (rows × columns)")
            print(f"CRS (Coordinate System): {gdf.crs}")
            
            # Geometry types
            geom_types = gdf.geom_type.value_counts()
            print(f"Geometry Types: {geom_types.to_dict()}")
            
            # Bounding box
            bounds = gdf.total_bounds  # [minx, miny, maxx, maxy]
            print(f"Bounding Box: [{bounds[0]:.6f}, {bounds[1]:.6f}, {bounds[2]:.6f}, {bounds[3]:.6f}]")
            
            # Convert to lat/lon for readability if needed
            if gdf.crs and gdf.crs.to_epsg() != 4326:
                try:
                    bounds_latlon = gdf.to_crs('EPSG:4326').total_bounds
                    print(f"Bounding Box (Lat/Lon): [{bounds_latlon[0]:.6f}, {bounds_latlon[1]:.6f}, {bounds_latlon[2]:.6f}, {bounds_latlon[3]:.6f}]")
                except Exception:
                    print("Could not convert to Lat/Lon coordinates")
            
            print(f"\n📋 Column Information:")
            print("-" * 20)
            
            # Show all columns and their types
            for col in gdf.columns:
                if col != 'geometry':
                    dtype = gdf[col].dtype
                    non_null = gdf[col].notna().sum()
                    total = len(gdf)
                    
                    print(f"  • {col}")
                    print(f"    Type: {dtype}")
                    print(f"    Non-null: {non_null}/{total} ({non_null/total*100:.1f}%)")
                    
                    # Show sample values for different data types
                    if dtype in ['object', 'string']:
                        unique_vals = gdf[col].nunique()
                        print(f"    Unique values: {unique_vals}")
                        if unique_vals <= 10:
                            sample_vals = list(gdf[col].dropna().unique())
                            print(f"    Values: {sample_vals}")
                        else:
                            sample_vals = list(gdf[col].dropna().unique()[:5])
                            print(f"    Sample values: {sample_vals}...")
                    
                    elif dtype in ['int64', 'float64', 'int32', 'float32']:
                        if gdf[col].notna().sum() > 0:  # Check if there are non-null values
                            print(f"    Range: {gdf[col].min():.2f} to {gdf[col].max():.2f}")
                            print(f"    Mean: {gdf[col].mean():.2f}")
                    
                    print()
            
            # Show first few rows
            print(f"📖 First 3 rows (excluding geometry):")
            print("-" * 30)
            display_cols = [col for col in gdf.columns if col != 'geometry']
            if display_cols:
                print(gdf[display_cols].head(3).to_string())
            else:
                print("Only geometry column found")
            print()
            
            # Memory usage
            memory_mb = gdf.memory_usage(deep=True).sum() / 1024 / 1024
            print(f"💾 Memory Usage: {memory_mb:.2f} MB")
            
            print("\n" + "="*60)
            
            return gdf  # Return the geodataframe for further analysis
    
    except Exception as e:
        print(f"❌ Error reading GPKG file: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        print("\nTroubleshooting tips:")
        print("1. Check if the file path is correct")
        print("2. Ensure the file is a valid GPKG format")
        print("3. Try opening the file in QGIS to verify it's valid")
        print("4. Check file permissions")
        return None

def analyze_for_visualization(file_path, layer_name=None):
    """
    Analyze specific aspects relevant for web visualization
    """
    print("\n🎨 VISUALIZATION ANALYSIS")
    print("=" * 40)
    
    try:
        # Try to read the file directly first
        try:
            gdf = gpd.read_file(file_path)
            print(f"✅ Successfully loaded data directly")
        except Exception as e:
            print(f"❌ Could not load file: {e}")
            return None
        
        # Ensure we're in WGS84 for web display
        original_crs = gdf.crs
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            print(f"Converting from {gdf.crs} to WGS84...")
            try:
                gdf = gdf.to_crs('EPSG:4326')
                print("✅ Conversion successful")
            except Exception as e:
                print(f"⚠️  Could not convert CRS: {e}")
        
        print(f"\n📏 Geometry Complexity:")
        print("-" * 25)
        
        # Calculate geometry complexity based on geometry type
        first_geom = gdf.geometry.iloc[0]
        if hasattr(first_geom, 'exterior') and first_geom.exterior:
            # Polygons
            coords_per_feature = []
            for geom in gdf.geometry:
                if geom and hasattr(geom, 'exterior') and geom.exterior:
                    coords_per_feature.append(len(geom.exterior.coords))
                else:
                    coords_per_feature.append(0)
            
            avg_coords = np.mean([x for x in coords_per_feature if x > 0])
            max_coords = max(coords_per_feature) if coords_per_feature else 0
            complex_features = sum(1 for x in coords_per_feature if x > 1000)
            
            print(f"Average coordinates per polygon: {avg_coords:.1f}")
            print(f"Max coordinates in a polygon: {max_coords}")
            print(f"Features with >1000 coordinates: {complex_features}")
        
        elif hasattr(first_geom, 'coords'):
            # Points or Lines
            print(f"Point/Line geometries detected")
        
        print(f"\n📊 Best Attributes for Visualization:")
        print("-" * 35)
        
        numeric_cols = gdf.select_dtypes(include=[np.number]).columns
        categorical_cols = gdf.select_dtypes(include=['object']).columns
        
        print("Numeric columns (good for choropleth maps):")
        for col in numeric_cols:
            if col != 'geometry' and gdf[col].notna().sum() > 0:
                min_val = gdf[col].min()
                max_val = gdf[col].max()
                print(f"  • {col}: {min_val:.2f} - {max_val:.2f}")
        
        print(f"\nCategorical columns (good for color coding):")
        for col in categorical_cols:
            unique_count = gdf[col].nunique()
            if unique_count <= 20:  # Good for visualization
                print(f"  • {col}: {unique_count} categories")
            else:
                print(f"  • {col}: {unique_count} categories (too many for simple viz)")
        
        # Suggest visualization strategies
        print(f"\n💡 Visualization Recommendations:")
        print("-" * 32)
        
        feature_count = len(gdf)
        if feature_count < 100:
            print("✅ Small dataset - all features can be shown at once")
        elif feature_count < 10000:
            print("⚠️  Medium dataset - consider level-of-detail or clustering")
        else:
            print("🚨 Large dataset - definitely need level-of-detail and bbox filtering")
        
        # Check for good choropleth candidates
        good_choropleth_cols = []
        for col in numeric_cols:
            if gdf[col].nunique() > 10:  # Has variety
                good_choropleth_cols.append(col)
        
        if good_choropleth_cols:
            print(f"📈 Good columns for choropleth: {good_choropleth_cols}")
        
        return gdf
        
    except Exception as e:
        print(f"❌ Error in visualization analysis: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return None

def quick_plot(gdf, attribute=None):
    """
    Create a quick matplotlib plot to see the data
    """
    print(f"\n🗺️  Quick Plot Preview")
    print("-" * 20)
    
    fig, ax = plt.subplots(1, 1, figsize=(12, 8))
    
    if attribute and attribute in gdf.columns:
        gdf.plot(column=attribute, ax=ax, legend=True, cmap='viridis')
        plt.title(f"Map colored by: {attribute}")
    else:
        gdf.plot(ax=ax, color='lightblue', edgecolor='black', linewidth=0.5)
        plt.title("All features")
    
    plt.axis('off')
    plt.tight_layout()
    plt.show()
    
    print("📍 This gives you a preview of your spatial data!")

# Example usage
if __name__ == "__main__":
    print("🚀 GPKG Data Explorer")
    print("Replace 'your_file.gpkg' with your actual file path")
    print()
    
    # Example usage - replace with your file path
    file_path = "downloaded_data/merged_geodata.gpkg"  # 👈 CHANGE THIS TO YOUR FILE PATH
    
    # Step 1: Full exploration
    explore_gpkg(file_path)
    
    # Step 2: Visualization analysis
    gdf = analyze_for_visualization(file_path)
    
    # Step 3: Quick plot (uncomment when you have data)
    # if gdf is not None:
    #     quick_plot(gdf)
    #     
    #     # Try plotting with an attribute
    #     numeric_cols = gdf.select_dtypes(include=[np.number]).columns
    #     if len(numeric_cols) > 0:
    #         quick_plot(gdf, numeric_cols[0])

print("""
📝 Next Steps:
1. Save this script as 'explore_gpkg.py'
2. Install required packages: pip install geopandas matplotlib
3. Change the file_path to your GPKG file
4. Run: python explore_gpkg.py
5. Review the output to understand your data structure
""")