#!/usr/bin/env python3
"""
Step 3: Interactive Web Application for GSA Data
Flask backend with GeoPandas + Leaflet frontend + TIFF background layer
"""

from flask import Flask, jsonify, render_template_string, request
import geopandas as gpd
import pandas as pd
import json
from shapely.geometry import box
import numpy as np
from functools import lru_cache
import time
import warnings

# TIFF processing imports
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.crs import CRS
import matplotlib.pyplot as plt
from PIL import Image
import base64
from io import BytesIO

warnings.filterwarnings('ignore')

app = Flask(__name__)

# Global variables for data
gdf_global = None
top_crops = None
crop_colors = None
tiff_overlay_data = None  # Store TIFF overlay data

def load_tiff_overlay(tiff_path):
    """
    Load and prepare TIFF file for web overlay
    """
    global tiff_overlay_data
    
    print(f"🗺️  Loading TIFF overlay: {tiff_path}")
    
    try:
        with rasterio.open(tiff_path) as src:
            data = src.read(1)
            original_crs = src.crs
            original_bounds = src.bounds
            
            print(f"   TIFF Info: {data.shape}, CRS: {original_crs}")
            
            # Check if reprojection is needed
            needs_reprojection = (
                original_crs is None or 
                original_crs.to_epsg() != 4326
            )
            
            if needs_reprojection:
                print("   🔄 Reprojecting TIFF to WGS84...")
                
                # Set default CRS if missing
                if original_crs is None:
                    original_crs = CRS.from_epsg(4326)
                    needs_reprojection = False
                
                if needs_reprojection:
                    dst_crs = CRS.from_epsg(4326)
                    
                    transform, width, height = calculate_default_transform(
                        original_crs, dst_crs,
                        src.width, src.height,
                        *src.bounds
                    )
                    
                    reprojected_data = np.empty((height, width), dtype=data.dtype)
                    
                    reproject(
                        source=data,
                        destination=reprojected_data,
                        src_transform=src.transform,
                        src_crs=original_crs,
                        dst_transform=transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.bilinear
                    )
                    
                    from rasterio.transform import array_bounds
                    final_bounds = array_bounds(height, width, transform)
                    final_data = reprojected_data
                else:
                    final_data = data
                    final_bounds = original_bounds
            else:
                print("   ✅ TIFF already in WGS84")
                final_data = data
                final_bounds = original_bounds
            
            # Create visualization with only value 65535 visible, rest transparent
            plt.ioff()
            fig, ax = plt.subplots(figsize=(12, 10), dpi=120)
            
            # Handle bounds format
            if hasattr(final_bounds, 'left'):
                bounds_array = [final_bounds.left, final_bounds.bottom, 
                               final_bounds.right, final_bounds.top]
            else:
                bounds_array = final_bounds
            
            extent = [bounds_array[0], bounds_array[2], bounds_array[1], bounds_array[3]]
            
            # Create a mask for only value 65535
            display_data = final_data.copy()
            mask = (display_data == 65535)
            
            # Create RGBA array for transparency control
            rgba_data = np.zeros((display_data.shape[0], display_data.shape[1], 4))
            
            # Set color for 65535 values (blue color for water bodies)
            rgba_data[mask] = [0.2, 0.6, 1.0, 0.8]  # Blue with 80% opacity
            # All other values remain transparent (alpha = 0)
            
            # Display the RGBA image
            ax.imshow(rgba_data, extent=extent)
            ax.axis('off')
            
            # Save to buffer
            buffer = BytesIO()
            plt.savefig(buffer, format='PNG', bbox_inches='tight', 
                       pad_inches=0, dpi=150, transparent=True)
            plt.close(fig)
            
            # Convert to base64
            buffer.seek(0)
            img_base64 = base64.b64encode(buffer.read()).decode()
            
            # Store overlay data
            tiff_overlay_data = {
                'image_data': f"data:image/png;base64,{img_base64}",
                'bounds': [[bounds_array[1], bounds_array[0]], 
                          [bounds_array[3], bounds_array[2]]],  # [[south, west], [north, east]]
                'opacity': 0.7,
                'name': 'Water Body Data',
                'stats': {
                    'min': float(np.nanmin(final_data)),
                    'max': float(np.nanmax(final_data)),
                    'mean': float(np.nanmean(final_data))
                }
            }
            
            print(f"   ✅ TIFF overlay prepared successfully!")
            print(f"   Bounds: {bounds_array}")
            print(f"   Data range: {tiff_overlay_data['stats']['min']:.3f} to {tiff_overlay_data['stats']['max']:.3f}")
            
            return True
            
    except Exception as e:
        print(f"   ❌ Error loading TIFF: {e}")
        return False

def load_data(file_path):
    """
    Load and prepare the GPKG data with optimizations
    """
    global gdf_global, top_crops, crop_colors
    
    print("🌾 Loading GSA Agricultural Data...")
    
    # Load data
    gdf = gpd.read_file(file_path)
    print(f"Loaded {len(gdf)} agricultural parcels")
    
    # Convert to WGS84 for web display
    if gdf.crs.to_epsg() != 4326:
        print("Converting to WGS84...")
        gdf = gdf.to_crs('EPSG:4326')
    
    # Create spatial index for fast bbox queries
    print("Creating spatial index...")
    gdf.sindex  # This creates the spatial index
    
    # Prepare crop color mapping
    top_crops = gdf['English_Name'].value_counts().head(15)
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
              '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
              '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2']
    crop_colors = {crop: colors[i] for i, crop in enumerate(top_crops.index)}
    
    # Add centroids for faster point-in-bbox calculations
    print("Computing centroids...")
    gdf['centroid_x'] = gdf.geometry.centroid.x
    gdf['centroid_y'] = gdf.geometry.centroid.y
    
    gdf_global = gdf
    print(f"✅ Data loaded and indexed successfully!")
    return gdf

@lru_cache(maxsize=100)
def get_features_in_bbox(north, south, east, west, max_features=1000):
    """
    Get features within bounding box with caching and limits
    """
    # Create bounding box
    bbox = box(west, south, east, north)
    
    # Fast pre-filter using centroids
    mask = (
        (gdf_global['centroid_x'] >= west) & 
        (gdf_global['centroid_x'] <= east) &
        (gdf_global['centroid_y'] >= south) & 
        (gdf_global['centroid_y'] <= north)
    )
    
    # Get subset
    gdf_subset = gdf_global[mask]
    
    if len(gdf_subset) == 0:
        return gdf_subset
    
    # Further filter with actual geometry intersection (more precise)
    gdf_filtered = gdf_subset[gdf_subset.geometry.intersects(bbox)]
    
    # Limit results based on zoom level (implement level-of-detail)
    if len(gdf_filtered) > max_features:
        # Sample the largest parcels first (assuming they're more important)
        gdf_filtered = gdf_filtered.sample(n=max_features, random_state=42)
    
    return gdf_filtered

@app.route('/api/tiff-overlay')
def get_tiff_overlay():
    """
    API endpoint to get TIFF overlay data
    """
    try:
        if tiff_overlay_data is None:
            return jsonify({'error': 'No TIFF overlay data available'}), 404
        
        return jsonify(tiff_overlay_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/')
def index():
    """
    Main page with the interactive map including TIFF overlay
    """
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Italian Agricultural Parcels - Interactive Map with TIFF Layer</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.css" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/plotly.js/2.26.0/plotly.min.js"></script>
    <style>
        body { margin: 0; font-family: Arial, sans-serif; }
        #container { display: flex; height: 100vh; }
        #map { flex: 2; }
        #sidebar { flex: 1; padding: 20px; background: #f5f5f5; overflow-y: auto; }
        #stats { background: white; padding: 15px; margin-bottom: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        #chart { height: 300px; }
        #crop-chart { height: 300px; margin-top: 20px; }
        .loading { color: #666; font-style: italic; }
        .info-box { background: white; padding: 10px; margin: 10px 0; border-radius: 5px; }
        h3 { margin-top: 0; color: #2c3e50; }
        .legend { background: white; padding: 10px; border-radius: 5px; margin-top: 10px; }
        .legend-item { display: flex; align-items: center; margin: 5px 0; }
        .legend-color { width: 20px; height: 15px; margin-right: 8px; border-radius: 3px; }
        .custom-popup .leaflet-popup-content { margin: 12px 16px; }
        .custom-popup .leaflet-popup-content-wrapper { border-radius: 8px; }
        .tiff-info { background: #e8f4fd; border-left: 4px solid #3498db; padding: 10px; margin: 10px 0; }
    </style>
</head>
<body>
    <div id="container">
        <div id="map"></div>
        <div id="sidebar">
            <h2>🌾 Italian Agriculture</h2>
            
            <div id="stats" class="info-box">
                <h3>Current View Statistics</h3>
                <div id="parcel-count" class="loading">Move map to load data...</div>
                <div id="area-info"></div>
            </div>
            
            <div class="info-box">
                <h3>📊 Crop Distribution</h3>
                <div id="chart"></div>
            </div>
            
            <div class="info-box">
                <h3>🏷️ Category Breakdown</h3>
                <div id="crop-chart"></div>
            </div>
            
            <div class="legend">
                <h4>Top Crops Legend</h4>
                <div id="legend-content"></div>
            </div>
            
            <div class="info-box">
                <h4>💡 Tips</h4>
                <ul>
                    <li>Zoom in for more parcels</li>
                    <li>Click parcels for details</li>
                    <li>Charts update with map view</li>
                    <li><strong>{{ parcel_count }} total parcels</strong> in dataset</li>
                    <li>Use layer control (top-right) to change background</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        // Initialize map centered on Northern Italy
        var map = L.map('map').setView([45.5, 9.5], 9);
        
        // Define multiple base layers
        var baseLayers = {
            "OpenStreetMap": L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors'
            }),
            
            "Satellite (ESRI)": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri, Maxar, Earthstar Geographics'
            }),
            
            "Satellite (Google)": L.tileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
                attribution: '© Google'
            }),
            
            "Terrain": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri, USGS, NOAA'
            }),
            
            "Topo Map": L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}', {
                attribution: '© Esri, TomTom, Garmin, Intermap, USGS, NRCAN, Esri Japan'
            }),
            
            "CartoDB Light": L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap © CartoDB'
            }),
            
            "CartoDB Dark": L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap © CartoDB'
            })
        };
        
        // Add default layer (OpenStreetMap)
        baseLayers["OpenStreetMap"].addTo(map);
        
        // Layer group for parcels
        var parcelLayer = L.layerGroup().addTo(map);
        
        // Variable to hold TIFF overlay
        var tiffOverlay = null;
        
        // Load TIFF overlay if available
        {% if tiff_available %}
        fetch('/api/tiff-overlay')
            .then(response => response.json())
            .then(data => {
                console.log('Loading TIFF overlay...');
                
                tiffOverlay = L.imageOverlay(
                    data.image_data,
                    data.bounds,
                    {
                        opacity: data.opacity,
                        attribution: 'TIFF Background Layer'
                    }
                );
                
                // Add to overlay layers for layer control
                overlayLayers["🗺️ " + data.name] = tiffOverlay;
                
                // Update layer control
                updateLayerControl();
                
                console.log('✅ TIFF overlay loaded successfully');
            })
            .catch(error => {
                console.error('Error loading TIFF overlay:', error);
            });
        {% endif %}
        
        // Overlay layers
        var overlayLayers = {
            "🌾 Agricultural Parcels": parcelLayer
        };
        
        // Layer control variable
        var layerControl;
        
        // Function to update layer control
        function updateLayerControl() {
            // Remove existing layer control if it exists
            if (layerControl) {
                map.removeControl(layerControl);
            }
            
            // Add new layer control
            layerControl = L.control.layers(baseLayers, overlayLayers, {
                position: 'topright',
                collapsed: false
            }).addTo(map);
        }
        
        // Initial layer control
        updateLayerControl();
        
        // Crop colors from backend
        var cropColors = {{ crop_colors | safe }};
        
        // Update legend
        function updateLegend() {
            var legendContent = document.getElementById('legend-content');
            legendContent.innerHTML = '';
            
            for (var crop in cropColors) {
                var item = document.createElement('div');
                item.className = 'legend-item';
                item.innerHTML = `
                    <div class="legend-color" style="background-color: ${cropColors[crop]}"></div>
                    <span>${crop.length > 25 ? crop.substring(0, 25) + '...' : crop}</span>
                `;
                legendContent.appendChild(item);
            }
        }
        
        // Function to update data based on map view
        function updateMapData() {
            var bounds = map.getBounds();
            var zoom = map.getZoom();
            
            // Show loading
            document.getElementById('parcel-count').innerHTML = '<span class="loading">Loading...</span>';
            
            // Determine max features based on zoom level
            var maxFeatures = zoom > 12 ? 2000 : zoom > 10 ? 1000 : 500;
            
            // Fetch data for current view
            fetch(`/api/features?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}&max_features=${maxFeatures}`)
                .then(response => response.json())
                .then(data => {
                    // Clear existing parcels
                    parcelLayer.clearLayers();
                    
                    // Update stats
                    document.getElementById('parcel-count').innerHTML = 
                        `📍 ${data.stats.total_parcels.toLocaleString()} parcels in view<br>
                         📏 Zoom level: ${zoom} (Max parcels: ${maxFeatures.toLocaleString()})`;
                    
                    // Add parcels to map
                    data.features.forEach(function(feature) {
                        var crop = feature.properties.English_Name;
                        var color = cropColors[crop] || '#888888';
                        
                        var layer = L.geoJSON(feature, {
                            style: {
                                fillColor: color,
                                weight: 0.5,
                                opacity: 1,
                                color: 'white',
                                fillOpacity: 0.7
                            }
                        });
                        
                        // Add enhanced popup with clean styling
                        var popupContent = `
                            <div style="font-family: Arial, sans-serif; max-width: 300px;">
                                <h4 style="margin: 0 0 10px 0; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">
                                    Agricultural Parcel
                                </h4>
                                
                                <div style="margin-bottom: 8px;">
                                    <strong>Crop (EN):</strong><br>
                                    <span style="color: #27ae60; font-weight: bold;">${feature.properties.English_Name || 'N/A'}</span>
                                </div>
                                
                                <div style="margin-bottom: 8px;">
                                    <strong>Crop (IT):</strong><br>
                                    <span style="color: #27ae60;">${feature.properties.Italian_Name || 'N/A'}</span>
                                </div>
                                
                                <div style="margin-bottom: 8px;">
                                    <strong>Main Crop Code:</strong><br>
                                    <span style="color: #8e44ad;">${feature.properties.main_crop_clean || 'N/A'}</span>
                                </div>
                                
                                <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 10px 0;">
                                
                                <div style="margin-bottom: 8px;">
                                    <strong>HCAT2 Category:</strong><br>
                                    <span style="color: #2980b9;">${feature.properties.HCAT2_Name || 'N/A'}</span>
                                </div>
                                
                                <div style="margin-bottom: 8px;">
                                    <strong>HCAT2 Code:</strong><br>
                                    <span style="color: #7f8c8d;">${feature.properties.HCAT2_Code ? feature.properties.HCAT2_Code.toLocaleString() : 'N/A'}</span>
                                </div>
                                
                                <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 10px 0;">
                                
                                <div style="margin-bottom: 8px;">
                                    <strong>Direct Match:</strong>
                                    <span style="color: ${feature.properties.Direct_Match === 'yes' ? '#27ae60' : '#e74c3c'}; font-weight: bold;">
                                        ${feature.properties.Direct_Match === 'yes' ? 'Yes' : 'No'}
                                    </span>
                                </div>
                                
                                ${feature.properties.Reason ? `
                                <div style="margin-bottom: 8px;">
                                    <strong>Match Reason:</strong><br>
                                    <span style="color: #34495e; font-style: italic; font-size: 12px;">
                                        ${feature.properties.Reason}
                                    </span>
                                </div>
                                ` : ''}
                                
                                <hr style="border: none; border-top: 1px solid #ecf0f1; margin: 10px 0;">
                                
                                <div style="font-size: 11px; color: #7f8c8d;">
                                    <strong>Parcel ID:</strong> ${feature.properties.gsa_par_id}
                                </div>
                            </div>
                        `;
                        
                        layer.bindPopup(popupContent, {
                            maxWidth: 350,
                            className: 'custom-popup'
                        });
                        
                        parcelLayer.addLayer(layer);
                    });
                    
                    // Update charts
                    updateCharts(data.stats);
                })
                .catch(error => {
                    console.error('Error fetching data:', error);
                    document.getElementById('parcel-count').innerHTML = 'Error loading data';
                });
        }
        
        // Function to update charts
        function updateCharts(stats) {
            // Crop distribution pie chart
            if (stats.crop_distribution && Object.keys(stats.crop_distribution).length > 0) {
                var cropData = Object.entries(stats.crop_distribution)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 10);
                
                var pieChart = {
                    values: cropData.map(d => d[1]),
                    labels: cropData.map(d => d[0]),
                    type: 'pie',
                    marker: {
                        colors: cropData.map(d => cropColors[d[0]] || '#888888')
                    },
                    textinfo: 'percent',
                    textposition: 'inside'
                };
                
                Plotly.newPlot('chart', [pieChart], {
                    title: 'Crop Types in View',
                    height: 300,
                    margin: {t: 40, b: 20, l: 20, r: 20}
                });
            }
            
            // Category bar chart
            if (stats.category_distribution && Object.keys(stats.category_distribution).length > 0) {
                var catData = Object.entries(stats.category_distribution)
                    .sort((a, b) => b[1] - a[1])
                    .slice(0, 8);
                
                var barChart = {
                    x: catData.map(d => d[1]),
                    y: catData.map(d => d[0].length > 20 ? d[0].substring(0, 20) + '...' : d[0]),
                    type: 'bar',
                    orientation: 'h',
                    marker: {
                        color: '#4ECDC4'
                    }
                };
                
                Plotly.newPlot('crop-chart', [barChart], {
                    title: 'Categories in View',
                    height: 300,
                    margin: {t: 40, b: 40, l: 100, r: 20}
                });
            }
        }
        
        // Initialize legend
        updateLegend();
        
        // Event listeners
        map.on('moveend', updateMapData);
        map.on('zoomend', updateMapData);
        
        // Initial data load
        updateMapData();
    </script>
</body>
</html>
    """
    
    # Prepare template variables
    template_vars = {
        'parcel_count': f"{len(gdf_global):,}",
        'crop_colors': json.dumps(crop_colors),
        'tiff_available': tiff_overlay_data is not None,
    }
    
    if tiff_overlay_data:
        template_vars.update({
            'tiff_name': tiff_overlay_data['name'],
            'tiff_stats': tiff_overlay_data['stats']
        })
    
    return render_template_string(html_template, **template_vars)

@app.route('/api/features')
def get_features():
    """
    API endpoint to get features within bounding box
    """
    try:
        # Get parameters
        north = float(request.args.get('north'))
        south = float(request.args.get('south'))
        east = float(request.args.get('east'))
        west = float(request.args.get('west'))
        max_features = int(request.args.get('max_features', 1000))
        
        start_time = time.time()
        
        # Get filtered data
        gdf_filtered = get_features_in_bbox(north, south, east, west, max_features)
        
        # Convert to GeoJSON
        if len(gdf_filtered) > 0:
            # Select columns including the new requested fields
            columns_to_keep = ['English_Name', 'Italian_Name', 'HCAT2_Name', 'HCAT2_Code', 
                             'main_crop_clean', 'Direct_Match', 'Reason', 'gsa_par_id', 'geometry']
            gdf_simplified = gdf_filtered[columns_to_keep]
            
            features = json.loads(gdf_simplified.to_json())['features']
        else:
            features = []
        
        # Calculate statistics
        stats = {
            'total_parcels': len(gdf_filtered),
            'query_time': round(time.time() - start_time, 3),
            'bbox': f"{north:.4f},{south:.4f},{east:.4f},{west:.4f}"
        }
        
        if len(gdf_filtered) > 0:
            # Crop distribution
            crop_counts = gdf_filtered['English_Name'].value_counts()
            stats['crop_distribution'] = crop_counts.head(15).to_dict()
            
            # Category distribution  
            cat_counts = gdf_filtered['HCAT2_Name'].value_counts()
            stats['category_distribution'] = cat_counts.head(10).to_dict()
        else:
            stats['crop_distribution'] = {}
            stats['category_distribution'] = {}
        
        return jsonify({
            'features': features,
            'stats': stats
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def get_global_stats():
    """
    Get global dataset statistics
    """
    try:
        stats = {
            'total_parcels': len(gdf_global),
            'total_crops': len(gdf_global['English_Name'].unique()),
            'total_categories': len(gdf_global['HCAT2_Name'].unique()),
            'top_crops': gdf_global['English_Name'].value_counts().head(10).to_dict(),
            'bounds': gdf_global.total_bounds.tolist()
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Configuration - ADD YOUR PATHS HERE
    GPKG_FILE = "downloaded_data/merged_geodata.gpkg"  # 👈 GPKG FILE PATH
    TIFF_FILE = "data/2025-06-01-00_00_2025-06-01-23_59_WB_100m_Monthly_V1_WB.tiff"  # 👈 TIFF FILE PATH
    
    print("🚀 Starting Italian Agricultural Data Web App with TIFF Background")
    print("=" * 70)
    
    try:
        # Load agricultural data
        load_data(GPKG_FILE)
        
        # Load TIFF overlay (optional)
        tiff_loaded = False
        try:
            if TIFF_FILE:
                tiff_loaded = load_tiff_overlay(TIFF_FILE)
        except Exception as e:
            print(f"⚠️  Could not load TIFF overlay: {e}")
            print("   App will continue without TIFF background layer")
        
        print(f"\n✅ Ready to serve!")
        print(f"📊 Dataset: {len(gdf_global):,} agricultural parcels")
        print(f"🗺️  TIFF overlay: {'✅ Loaded' if tiff_loaded else '❌ Not available'}")
        print(f"🎯 Features: Interactive map + real-time charts + {'background layer' if tiff_loaded else 'no background layer'}")
        print("=" * 70)
        print("\n🌐 GitHub Codespaces Access:")
        print("1. Look at the 'PORTS' tab in the bottom panel of VS Code")
        print("2. Find port 5000 and click the 🌐 icon or copy the URL")
        print("3. If it shows 'Private', right-click and change to 'Public'")
        print("4. The URL format should be: https://your-codespace-5000.preview.app.github.dev")
        
        if tiff_loaded:
            print("\n🎨 TIFF Background Layer:")
            print("• Use the layer control (top-right) to toggle the background layer")
            print("• The TIFF will appear as '🗺️ Water Body Data' in the layer control")
            print("• You can adjust opacity and visibility independently of other layers")
        
        print("=" * 70)
        
        # Start server with better Codespaces settings
        app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("\n🔧 Configuration checklist:")
        print(f"1. Update GPKG_FILE path: {GPKG_FILE}")
        print(f"2. Update TIFF_FILE path: {TIFF_FILE}")
        print("3. Make sure both files exist and are readable")
        print("4. Install required packages: pip install flask geopandas rasterio matplotlib pillow")