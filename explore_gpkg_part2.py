#!/usr/bin/env python3
"""
Step 2: Basic Plotting and Visualization
Understanding your Italian Agricultural Data
"""

import geopandas as gpd
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from shapely.geometry import box
import folium
from folium import plugins
import warnings
warnings.filterwarnings('ignore')

def load_and_sample_data(file_path, sample_size=1000):
    """
    Load the GPKG and create a manageable sample for plotting
    """
    print("🌾 Loading Italian Agricultural Data...")
    print("=" * 50)
    
    # Load full dataset info
    gdf_full = gpd.read_file(file_path)
    print(f"Full dataset: {len(gdf_full):,} agricultural parcels")
    print(f"Memory usage: {gdf_full.memory_usage(deep=True).sum() / 1024 / 1024:.1f} MB")
    
    # Convert to WGS84 for web visualization
    if gdf_full.crs.to_epsg() != 4326:
        print("Converting to WGS84...")
        gdf_full = gdf_full.to_crs('EPSG:4326')
    
    # Create a sample for visualization
    print(f"\nCreating sample of {sample_size:,} parcels for visualization...")
    gdf_sample = gdf_full.sample(n=min(sample_size, len(gdf_full)), random_state=42)
    
    return gdf_full, gdf_sample

def analyze_crop_distribution(gdf):
    """
    Analyze the distribution of crops in the dataset
    """
    print("\n📊 Crop Distribution Analysis")
    print("=" * 35)
    
    # Most common crops
    crop_counts = gdf['English_Name'].value_counts().head(15)
    print("Top 15 crops by parcel count:")
    for i, (crop, count) in enumerate(crop_counts.items(), 1):
        percentage = (count / len(gdf)) * 100
        print(f"{i:2d}. {crop:<25} {count:>8,} parcels ({percentage:5.1f}%)")
    
    # Categories analysis
    print(f"\nHCAT2 Categories:")
    cat_counts = gdf['HCAT2_Name'].value_counts().head(10)
    for i, (cat, count) in enumerate(cat_counts.items(), 1):
        percentage = (count / len(gdf)) * 100
        print(f"{i:2d}. {cat:<30} {count:>8,} parcels ({percentage:5.1f}%)")
    
    return crop_counts, cat_counts

def create_matplotlib_plots(gdf_sample, gdf_full):
    """
    Create matplotlib visualizations
    """
    print(f"\n🗺️  Creating Matplotlib Visualizations...")
    print("=" * 40)
    
    # Figure with multiple subplots
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    fig.suptitle('Italian Agricultural Parcels Analysis', fontsize=16, fontweight='bold')
    
    # Plot 1: All parcels (sample)
    ax1 = axes[0, 0]
    gdf_sample.plot(ax=ax1, color='lightgreen', edgecolor='darkgreen', linewidth=0.1, alpha=0.7)
    ax1.set_title(f'Sample of {len(gdf_sample):,} Agricultural Parcels', fontweight='bold')
    ax1.set_xlabel('Longitude')
    ax1.set_ylabel('Latitude')
    
    # Plot 2: Crop distribution (top 10)
    ax2 = axes[0, 1]
    top_crops = gdf_full['English_Name'].value_counts().head(10)
    colors = plt.cm.Set3(np.linspace(0, 1, len(top_crops)))
    bars = ax2.barh(range(len(top_crops)), top_crops.values, color=colors)
    ax2.set_yticks(range(len(top_crops)))
    ax2.set_yticklabels([name[:20] + '...' if len(name) > 20 else name for name in top_crops.index])
    ax2.set_xlabel('Number of Parcels')
    ax2.set_title('Top 10 Crops by Parcel Count', fontweight='bold')
    
    # Add value labels on bars
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax2.text(width + max(top_crops.values) * 0.01, bar.get_y() + bar.get_height()/2, 
                f'{int(width):,}', ha='left', va='center', fontsize=8)
    
    # Plot 3: Choropleth by crop type (sample of most common crops)
    ax3 = axes[1, 0]
    top_5_crops = gdf_full['English_Name'].value_counts().head(5).index
    gdf_top5 = gdf_sample[gdf_sample['English_Name'].isin(top_5_crops)]
    
    # Create a color map for top 5 crops
    unique_crops = gdf_top5['English_Name'].unique()
    color_map = {crop: plt.cm.Set1(i) for i, crop in enumerate(unique_crops)}
    colors = [color_map.get(crop, 'gray') for crop in gdf_top5['English_Name']]
    
    gdf_top5.plot(ax=ax3, color=colors, edgecolor='white', linewidth=0.1)
    ax3.set_title('Top 5 Crops Distribution (Sample)', fontweight='bold')
    ax3.set_xlabel('Longitude')
    ax3.set_ylabel('Latitude')
    
    # Add legend
    legend_elements = [plt.Rectangle((0,0),1,1, facecolor=color_map[crop], label=crop[:15]+'...' if len(crop) > 15 else crop) 
                      for crop in unique_crops]
    ax3.legend(handles=legend_elements, loc='upper left', bbox_to_anchor=(1.05, 1), fontsize=8)
    
    # Plot 4: Geographic distribution density
    ax4 = axes[1, 1]
    # Create a density plot using hexbin
    x = gdf_sample.geometry.centroid.x
    y = gdf_sample.geometry.centroid.y
    hb = ax4.hexbin(x, y, gridsize=20, cmap='YlOrRd', alpha=0.7)
    ax4.set_title('Parcel Density Distribution', fontweight='bold')
    ax4.set_xlabel('Longitude')
    ax4.set_ylabel('Latitude')
    plt.colorbar(hb, ax=ax4, label='Parcel Density')
    
    plt.tight_layout()
    plt.show()
    
    print("✅ Matplotlib visualizations complete!")

def create_interactive_folium_map(gdf_sample, gdf_full):
    """
    Create an interactive Folium map
    """
    print(f"\n🌍 Creating Interactive Folium Map...")
    print("=" * 35)
    
    # Calculate center point
    bounds = gdf_sample.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2
    
    # Create base map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap'
    )
    
    # Add sample of parcels (limit to avoid browser overload)
    sample_for_map = gdf_sample.head(500)  # Even smaller sample for web map
    
    print(f"Adding {len(sample_for_map)} parcels to interactive map...")
    
    # Get top 10 crops for color coding
    top_crops = gdf_full['English_Name'].value_counts().head(10)
    colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred', 'lightred', 
              'beige', 'darkblue', 'darkgreen']
    crop_colors = {crop: colors[i] for i, crop in enumerate(top_crops.index)}
    
    # Add parcels to map
    for idx, row in sample_for_map.iterrows():
        crop_name = row['English_Name']
        italian_name = row['Italian_Name']
        color = crop_colors.get(crop_name, 'gray')
        
        # Create popup content
        popup_content = f"""
        <b>Agricultural Parcel</b><br>
        <b>Crop (EN):</b> {crop_name}<br>
        <b>Crop (IT):</b> {italian_name}<br>
        <b>Category:</b> {row['HCAT2_Name']}<br>
        <b>Parcel ID:</b> {row['gsa_par_id']}
        """
        
        # Add to map
        folium.GeoJson(
            row['geometry'],
            style_function=lambda feature, color=color: {
                'fillColor': color,
                'color': 'black',
                'weight': 0.5,
                'fillOpacity': 0.7,
            },
            popup=folium.Popup(popup_content, max_width=300),
            tooltip=f"{crop_name}"
        ).add_to(m)
    
    # Add a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: 200px; height: auto; 
                background-color: white; border:2px solid grey; z-index:9999; 
                font-size:14px; padding: 10px">
    <p><b>Top 10 Crops</b></p>
    '''
    
    for crop, color in list(crop_colors.items())[:10]:
        parcels_count = top_crops[crop]
        legend_html += f'<p><i class="fa fa-square" style="color:{color}"></i> {crop[:20]}{"..." if len(crop) > 20 else ""} ({parcels_count:,})</p>'
    
    legend_html += '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    
    # Save map
    map_filename = 'italian_agriculture_map.html'
    m.save(map_filename)
    
    print(f"✅ Interactive map saved as '{map_filename}'")
    print(f"   Open this file in your browser to explore!")
    
    return m

def recommend_visualization_strategy(gdf_full):
    """
    Recommend the best approach for web visualization
    """
    print(f"\n💡 Web Visualization Strategy Recommendations")
    print("=" * 50)
    
    total_parcels = len(gdf_full)
    memory_mb = gdf_full.memory_usage(deep=True).sum() / 1024 / 1024
    
    print(f"Dataset size: {total_parcels:,} parcels ({memory_mb:.1f} MB)")
    
    if total_parcels > 100000:
        print("🚨 LARGE DATASET - Special handling required:")
        print("   1. Implement level-of-detail (show fewer parcels when zoomed out)")
        print("   2. Use spatial indexing for fast bbox queries")
        print("   3. Consider data clustering/aggregation")
        print("   4. Implement progressive loading")
        print("   5. Use vector tiles for best performance")
    
    # Best attributes for visualization
    print(f"\n📊 Best attributes for dynamic charts:")
    print("   • English_Name: Perfect for crop type distribution")
    print("   • HCAT2_Name: Good for agricultural category analysis")
    print("   • Italian_Name: Local language visualization")
    
    print(f"\n🎯 Recommended approach:")
    print("   1. Backend: Flask + GeoPandas with spatial indexing")
    print("   2. Frontend: Leaflet.js with clustering")  
    print("   3. Data strategy: Bbox-based filtering + level-of-detail")
    print("   4. Charts: Crop distribution pie/bar charts")
    print("   5. Performance: Cache common queries, use PostGIS if possible")

# Main execution
if __name__ == "__main__":
    print("🌾 Italian Agricultural Data Visualization")
    print("Step 2: Basic Plotting and Analysis")
    print("=" * 60)
    
    # Change this to your GPKG file path
    file_path = "downloaded_data/merged_geodata.gpkg"  # 👈 CHANGE THIS
    
    try:
        # Load data
        gdf_full, gdf_sample = load_and_sample_data(file_path, sample_size=2000)
        
        # Analyze crop distribution
        crop_counts, cat_counts = analyze_crop_distribution(gdf_full)
        
        # Create visualizations
        create_matplotlib_plots(gdf_sample, gdf_full)
        
        # Create interactive map
        create_interactive_folium_map(gdf_sample, gdf_full)
        
        # Provide recommendations
        recommend_visualization_strategy(gdf_full)
        
        print(f"\n✅ Step 2 Complete!")
        print(f"Next: We'll build the web application with dynamic filtering!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("Make sure to update the file_path variable with your GPKG file path")

print("""
📝 To run this step:
1. Install: pip install folium
2. Update file_path in the script
3. Run: python step2_plotting.py
4. Open the generated HTML file in your browser
""")