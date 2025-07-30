import geopandas as gpd
import folium
import pandas as pd
import numpy as np
from folium import plugins

def create_interactive_crop_map(gdf, sample_size=2000, save_name='interactive_crop_map.html'):
    """
    Create an interactive crop map with background tiles
    """
    print(f"Creating interactive map with {sample_size} polygons...")
    
    # Take a sample for performance
    sample_gdf = gdf.sample(n=min(sample_size, len(gdf)), random_state=42)
    
    # Convert to WGS84 for web mapping
    sample_gdf = sample_gdf.to_crs('EPSG:4326')
    
    # Get crop statistics
    crop_counts = sample_gdf['crop_name_clean'].value_counts()
    print(f"\nTop crops in sample:")
    for crop, count in crop_counts.head(10).items():
        print(f"  {crop}: {count} fields")
    
    # Calculate center point for map
    bounds = sample_gdf.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    print(f"Map center: {center_lat:.4f}, {center_lon:.4f}")
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles=None  # We'll add custom tiles
    )
    
    # Add different background tile layers
    folium.TileLayer(
        tiles='OpenStreetMap',
        name='OpenStreetMap',
        overlay=False,
        control=True
    ).add_to(m)
    
    folium.TileLayer(
        tiles='CartoDB positron',
        name='CartoDB Light',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Satellite imagery
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri',
        name='Satellite',
        overlay=False,
        control=True
    ).add_to(m)
    
    # Create color mapping for crops
    unique_crops = sample_gdf['crop_name_clean'].unique()
    colors = ['red', 'blue', 'green', 'orange', 'purple', 'brown', 'pink', 'gray', 'olive', 'cyan',
              'magenta', 'yellow', 'navy', 'lime', 'aqua', 'maroon', 'fuchsia', 'silver', 'teal', 'black']
    
    # Extend colors if we have more crops than colors
    while len(colors) < len(unique_crops):
        colors.extend(colors)
    
    crop_color_map = dict(zip(unique_crops, colors[:len(unique_crops)]))
    
    # Add crop polygons by type
    top_crops = crop_counts.head(10).index.tolist()
    
    for crop in top_crops:
        crop_data = sample_gdf[sample_gdf['crop_name_clean'] == crop]
        if len(crop_data) > 0:
            # Create feature group for this crop
            crop_group = folium.FeatureGroup(name=f'{crop} ({len(crop_data)} fields)')
            
            for idx, row in crop_data.iterrows():
                # Create popup with crop info
                popup_text = f"""
                <b>Crop:</b> {row['crop_name_clean']}<br>
                <b>Code:</b> {row['main_crop_clean']}<br>
                <b>Field ID:</b> {idx}
                """
                
                # Add polygon to map
                folium.GeoJson(
                    row.geometry,
                    style_function=lambda feature, color=crop_color_map[crop]: {
                        'fillColor': color,
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.7,
                        'opacity': 1
                    },
                    popup=folium.Popup(popup_text, max_width=300),
                    tooltip=f"{crop}"
                ).add_to(crop_group)
            
            crop_group.add_to(m)
    
    # Add remaining crops in a single group
    other_crops = sample_gdf[~sample_gdf['crop_name_clean'].isin(top_crops)]
    if len(other_crops) > 0:
        other_group = folium.FeatureGroup(name=f'Other crops ({len(other_crops)} fields)')
        
        for idx, row in other_crops.iterrows():
            popup_text = f"""
            <b>Crop:</b> {row['crop_name_clean']}<br>
            <b>Code:</b> {row['main_crop_clean']}<br>
            <b>Field ID:</b> {idx}
            """
            
            folium.GeoJson(
                row.geometry,
                style_function=lambda feature: {
                    'fillColor': 'lightgray',
                    'color': 'black',
                    'weight': 1,
                    'fillOpacity': 0.5,
                    'opacity': 1
                },
                popup=folium.Popup(popup_text, max_width=300),
                tooltip=f"{row['crop_name_clean']}"
            ).add_to(other_group)
        
        other_group.add_to(m)
    
    # Add layer control
    folium.LayerControl().add_to(m)
    
    # Add fullscreen button
    plugins.Fullscreen().add_to(m)
    
    # Add crop statistics as a fixed panel (removed search to avoid error)
    stats_html = f"""
    <div style="position: fixed; 
                top: 10px; right: 10px; width: 300px; height: 200px; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px; border-radius: 5px;">
    <h4>🌾 Crop Statistics (Sample)</h4>
    <p><b>Total fields:</b> {len(sample_gdf)}</p>
    <p><b>Crop types:</b> {len(unique_crops)}</p>
    <p><b>Top 3 crops:</b></p>
    <ul>
    """
    
    for crop, count in crop_counts.head(3).items():
        stats_html += f"<li>{crop}: {count} fields</li>"
    
    stats_html += """
    </ul>
    <p><i>💡 Click polygons for details</i></p>
    <p><i>🗂️ Use layer control to toggle crops</i></p>
    </div>
    """
    
    m.get_root().html.add_child(folium.Element(stats_html))
    
    # Save the map
    m.save(save_name)
    print(f"\nInteractive map saved as: {save_name}")
    print(f"🌐 Open this file in your browser to view the interactive map!")
    
    return m

# Load data and create map
print("Loading data...")
gdf = gpd.read_file('downloaded_data/merged_geodata.gpkg')
print(f"Total dataset: {len(gdf)} polygons")

# Create interactive crop map
interactive_map = create_interactive_crop_map(gdf, sample_size=1500)

print("\n✅ Interactive map created!")
print("📂 File: interactive_crop_map.html")
print("\n🎯 Features:")
print("- 🗺️ Multiple background layers (Street, Light, Satellite)")
print("- 🖱️ Click polygons for crop details")
print("- 👁️ Toggle crop types on/off")
print("- 🔍 Zoom and pan to explore")
print("- 📊 Statistics panel in top-right")