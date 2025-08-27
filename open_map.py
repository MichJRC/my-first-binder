#!/usr/bin/env python3
"""
Simple Water Layer Test - Minimal script to check water projection
"""

import geopandas as gpd
import rasterio
import rasterio.features
import numpy as np
from shapely.geometry import shape
import folium
import os

def load_and_test_water(water_file_path):
    """
    Load water data and create a simple map to test projection
    """
    print("🌊 Testing Water Layer...")
    
    if not os.path.exists(water_file_path):
        print(f"❌ File not found: {water_file_path}")
        return None
    
    try:
        with rasterio.open(water_file_path) as src:
            print(f"Original CRS: {src.crs}")
            print(f"Original bounds: {src.bounds}")
            print(f"Raster shape: {src.shape}")
            
            # Read raster data
            water_data = src.read(1)
            print(f"Unique values: {np.unique(water_data)}")
            
            # Find water pixels
            water_mask = water_data == 70
            water_count = np.sum(water_mask)
            print(f"Water pixels (value 70): {water_count:,}")
            
            if water_count == 0:
                print("❌ No water pixels found!")
                return None
            
            # Convert to polygons
            print("Converting to polygons...")
            shapes_gen = rasterio.features.shapes(
                water_data,
                mask=water_mask,
                transform=src.transform
            )
            
            # Collect geometries
            geometries = []
            for geom, value in shapes_gen:
                if value == 70:
                    geometries.append(shape(geom))
            
            print(f"Created {len(geometries)} polygons")
            
            # Create GeoDataFrame
            water_gdf = gpd.GeoDataFrame({
                'water': [1] * len(geometries)
            }, geometry=geometries, crs=src.crs)
            
            print(f"GDF bounds in original CRS: {water_gdf.total_bounds}")
            
            # Convert to WGS84 for web mapping
            water_gdf_wgs84 = water_gdf.to_crs('EPSG:4326')
            print(f"GDF bounds in WGS84: {water_gdf_wgs84.total_bounds}")
            
            return water_gdf_wgs84
    
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def create_simple_map(water_gdf):
    """
    Create a simple folium map to visualize water
    """
    print("🗺️ Creating test map...")
    
    # Get center point
    bounds = water_gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    print(f"Map center: {center_lat:.4f}, {center_lon:.4f}")
    
    # Create map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=8,
        tiles='OpenStreetMap'
    )
    
    # Add satellite layer as option
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Add water polygons
    folium.GeoJson(
        water_gdf.to_json(),
        style_function=lambda feature: {
            'fillColor': 'blue',
            'color': 'darkblue',
            'weight': 1,
            'fillOpacity': 0.6
        },
        popup=folium.Popup('Water Body', parse_html=True)
    ).add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Fit map to water bounds
    m.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    
    return m

if __name__ == '__main__':
    # Set your water file path here
    WATER_FILE = "data/water_bodies_italy_2025_06.tif"  # 👈 UPDATE THIS PATH
    
    print("🚀 Simple Water Layer Test")
    print("=" * 40)
    
    # Load water data
    water_gdf = load_and_test_water(WATER_FILE)
    
    if water_gdf is not None:
        # Create map
        map_obj = create_simple_map(water_gdf)
        
        # Save map
        output_file = "water_test_map.html"
        map_obj.save(output_file)
        
        print(f"✅ Map saved as: {output_file}")
        print(f"📊 Total water polygons: {len(water_gdf):,}")
        print(f"🗺️ Bounds: {water_gdf.total_bounds}")
        print("\n💡 Open the HTML file in your browser to check the water layer!")
        print("   - Switch between OpenStreetMap and Satellite view")
        print("   - Check if water bodies align with expected locations")
        print("   - Look for Italy's major lakes, rivers, and coastal areas")
        
    else:
        print("❌ Failed to load water data")
        print("   - Check the file path")
        print("   - Make sure the file contains pixels with value 70")