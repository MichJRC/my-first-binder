#!/usr/bin/env python3
"""
GPKG Data Exploration Script - FIXED VERSION
Key fixes:
1. Better error handling for CRS conversion
2. Global variable assignment
3. Smaller chunk processing for large datasets
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box
import warnings
warnings.filterwarnings('ignore')

# Global variable to store the geodataframe
gdf = None

def explore_gpkg(file_path):
    """
    Comprehensive exploration of a GPKG file
    """
    global gdf  # Make it accessible globally
    
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
        if 'name' in layers.columns:
            layer_names = layers['name'].tolist()
        elif 'layer_name' in layers.columns:
            layer_names = layers['layer_name'].tolist()
        elif len(layers.columns) >= 1:
            layer_names = layers.iloc[:, 0].tolist()
        
        if not layer_names:
            print("❌ Could not extract layer names. Trying to read file directly...")
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
                    
                print(f"✅ Successfully loaded {len(gdf)} features")
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
                    # Process in smaller chunks for large datasets
                    if len(gdf) > 100000:
                        print("⚠️  Large dataset detected. Converting sample to Lat/Lon...")
                        sample_gdf = gdf.sample(1000).to_crs('EPSG:4326')
                        bounds_latlon = sample_gdf.total_bounds
                    else:
                        bounds_latlon = gdf.to_crs('EPSG:4326').total_bounds
                    print(f"Bounding Box (Lat/Lon): [{bounds_latlon[0]:.6f}, {bounds_latlon[1]:.6f}, {bounds_latlon[2]:.6f}, {bounds_latlon[3]:.6f}]")
                except Exception as crs_error:
                    print(f"Could not convert to Lat/Lon coordinates: {crs_error}")
            
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
                        if gdf[col].notna().sum() > 0:
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
            
            return gdf  # Return the geodataframe
    
    except Exception as e:
        print(f"❌ Error reading GPKG file: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        return None

def analyze_for_visualization_safe(file_path, layer_name=None):
    """
    SAFER version of visualization analysis with better error handling
    """
    global gdf
    
    print("\n🎨 VISUALIZATION ANALYSIS (SAFE MODE)")
    print("=" * 40)
    
    try:
        # Use the already loaded gdf if available
        if gdf is None:
            try:
                gdf = gpd.read_file(file_path)
                print(f"✅ Successfully loaded data directly")
            except Exception as e:
                print(f"❌ Could not load file: {e}")
                return None
        else:
            print(f"✅ Using already loaded data ({len(gdf)} features)")
        
        # Check original CRS
        original_crs = gdf.crs
        print(f"Original CRS: {original_crs}")
        
        # SAFER CRS conversion approach
        if gdf.crs and gdf.crs.to_epsg() != 4326:
            print(f"⚠️  Data is not in WGS84. Conversion needed for web visualization.")
            
            # For large datasets, don't convert in memory - just report
            if len(gdf) > 100000:
                print(f"🚨 Large dataset ({len(gdf)} features) - CRS conversion skipped to avoid memory issues")
                print(f"💡 For web visualization, consider:")
                print(f"   1. Process in smaller chunks")
                print(f"   2. Use PostGIS for conversion")
                print(f"   3. Create a simplified version first")
                needs_conversion = True
            else:
                try:
                    print(f"Converting smaller dataset from {gdf.crs} to WGS84...")
                    gdf = gdf.to_crs('EPSG:4326')
                    print("✅ Conversion successful")
                    needs_conversion = False
                except Exception as e:
                    print(f"❌ Could not convert CRS: {e}")
                    print(f"Will work with original CRS: {original_crs}")
                    needs_conversion = True
        else:
            print("✅ Data already in WGS84")
            needs_conversion = False
        
        print(f"\n📏 Geometry Complexity Analysis:")
        print("-" * 25)
        
        # Analyze first few geometries to avoid memory issues
        sample_size = min(1000, len(gdf))
        sample_gdf = gdf.head(sample_size)
        
        # Calculate geometry complexity
        coords_per_feature = []
        for geom in sample_gdf.geometry:
            if geom and hasattr(geom, 'geoms'):  # MultiPolygon
                total_coords = 0
                for poly in geom.geoms:
                    if hasattr(poly, 'exterior') and poly.exterior:
                        total_coords += len(poly.exterior.coords)
                coords_per_feature.append(total_coords)
            elif geom and hasattr(geom, 'exterior') and geom.exterior:  # Single Polygon
                coords_per_feature.append(len(geom.exterior.coords))
            else:
                coords_per_feature.append(0)
        
        if coords_per_feature:
            avg_coords = np.mean([x for x in coords_per_feature if x > 0])
            max_coords = max(coords_per_feature) if coords_per_feature else 0
            complex_features = sum(1 for x in coords_per_feature if x > 1000)
            
            print(f"Average coordinates per feature (sample): {avg_coords:.1f}")
            print(f"Max coordinates in a feature: {max_coords}")
            print(f"Complex features (>1000 coords) in sample: {complex_features}")
        
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
            if unique_count <= 20:
                print(f"  • {col}: {unique_count} categories")
            else:
                print(f"  • {col}: {unique_count} categories (too many for simple viz)")
        
        # Dataset size recommendations
        print(f"\n💡 Visualization Recommendations:")
        print("-" * 32)
        
        feature_count = len(gdf)
        if feature_count < 1000:
            print("✅ Small dataset - all features can be shown at once")
        elif feature_count < 10000:
            print("⚠️  Medium dataset - consider level-of-detail or clustering")
        else:
            print("🚨 Large dataset - definitely need optimization:")
            print("   • Use vector tiles (e.g., Tippecanoe)")
            print("   • Implement bbox filtering")
            print("   • Consider data aggregation")
            print("   • Use progressive loading")
        
        if needs_conversion:
            print(f"\n⚠️  CRS Conversion needed for web maps")
            print(f"   Original: {original_crs}")
            print(f"   Target: EPSG:4326 (WGS84)")
        
        return gdf
        
    except Exception as e:
        print(f"❌ Error in visualization analysis: {str(e)}")
        return None

def quick_data_check():
    """
    Quick check of the loaded data
    """
    global gdf
    
    if gdf is None:
        print("❌ No data loaded. Run explore_gpkg() first.")
        return False
    
    print(f"\n🔍 QUICK DATA CHECK")
    print(f"Shape: {gdf.shape}")
    print(f"CRS: {gdf.crs}")
    print(f"Memory: {gdf.memory_usage(deep=True).sum() / 1024 / 1024:.2f} MB")
    
    # Show available methods
    print(f"\n💡 Available operations:")
    print(f"   gdf.head()           - First 5 rows")
    print(f"   gdf.tail()           - Last 5 rows") 
    print(f"   gdf.info()           - Data info")
    print(f"   gdf.describe()       - Statistics")
    print(f"   gdf.columns          - Column names")
    print(f"   gdf.shape            - Dimensions")
    
    return True

# Example usage with fixes
if __name__ == "__main__":
    print("🚀 GPKG Data Explorer - FIXED VERSION")
    print("Key improvements:")
    print("- Better memory handling for large datasets")
    print("- Safer CRS conversion")
    print("- Global variable access")
    print()
    
    # Example usage
    file_path = "downloaded_data/merged_geodata.gpkg"
    
    # Step 1: Load and explore (this sets the global gdf variable)
    gdf = explore_gpkg(file_path)
    
    # Step 2: Check if data was loaded
    if gdf is not None:
        print(f"\n✅ Data successfully loaded into 'gdf' variable")
        print(f"You can now use: gdf.head(), gdf.info(), etc.")
        
        # Step 3: Safe visualization analysis
        analyze_for_visualization_safe(file_path)
        
        # Step 4: Show how to access the data
        print(f"\n" + "="*60)
        print(f"🎯 DATA IS NOW ACCESSIBLE!")
        print(f"="*60)
        print(f"Variable 'gdf' contains your geodataframe")
        print(f"Try these commands:")
        print(f"  print(gdf.head())")
        print(f"  print(gdf.columns.tolist())")
        print(f"  print(gdf['Italian_Name'].value_counts())")
        
    else:
        print(f"❌ Failed to load data")

# Make data checking function easily accessible
def check_data():
    quick_data_check()

print("""
📝 How to use this fixed script:
1. Run the script: python explore_gpkg_fixed.py
2. The 'gdf' variable will be globally accessible
3. Use gdf.head(), gdf.info(), etc. in the console
4. Call check_data() anytime to verify data is loaded
""")