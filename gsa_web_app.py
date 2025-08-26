#!/usr/bin/env python3
"""
Step 3: Interactive Web Application for GSA Data
Flask backend with GeoPandas + Leaflet frontend + Water Bodies Layer
"""

from flask import Flask, jsonify, render_template_string, request, send_file
import geopandas as gpd
import pandas as pd
import json
from shapely.geometry import box
import numpy as np
from functools import lru_cache
import time
import warnings
import rasterio
from rasterio.warp import transform_bounds
from rasterio.io import MemoryFile
import io
import os
from PIL import Image
import math

warnings.filterwarnings('ignore')

app = Flask(__name__)

# Global variables for data
gdf_global = None
top_crops = None
crop_colors = None
water_raster = None
water_bounds = None

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
    gdf.sindex
    
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

def load_water_data(water_file_path):
    """
    Load and prepare water bodies raster data
    """
    global water_raster, water_bounds
    
    if not os.path.exists(water_file_path):
        print(f"⚠️ Water file not found: {water_file_path}")
        return False
    
    print("🌊 Loading Water Bodies Data...")
    
    try:
        with rasterio.open(water_file_path) as src:
            # Get bounds in WGS84
            if src.crs.to_epsg() != 4326:
                water_bounds = transform_bounds(src.crs, 'EPSG:4326', *src.bounds)
            else:
                water_bounds = src.bounds
            
            # Store raster info for tile serving
            water_raster = {
                'path': water_file_path,
                'bounds': water_bounds,
                'crs': src.crs,
                'shape': src.shape,
                'dtype': src.dtypes[0]
            }
            
        print(f"✅ Water bodies data loaded!")
        print(f"   Bounds: {water_bounds}")
        return True
        
    except Exception as e:
        print(f"❌ Error loading water data: {e}")
        return False

def deg2num(lat_deg, lon_deg, zoom):
    """Convert lat/lon to tile numbers"""
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    """Convert tile numbers to lat/lon"""
    n = 2.0 ** zoom
    lon_deg = xtile / n * 360.0 - 180.0
    lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_deg = math.degrees(lat_rad)
    return (lat_deg, lon_deg)

@app.route('/tiles/water/<int:z>/<int:x>/<int:y>.png')
def water_tile(z, x, y):
    """
    Serve water bodies tiles
    """
    if not water_raster:
        return "Water layer not available", 404
    
    try:
        # Calculate tile bounds
        lat_max, lon_min = num2deg(x, y, z)
        lat_min, lon_max = num2deg(x + 1, y + 1, z)
        
        # Check if tile intersects with water bounds
        if (lon_max < water_bounds[0] or lon_min > water_bounds[2] or
            lat_max < water_bounds[1] or lat_min > water_bounds[3]):
            # Return transparent tile
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            return send_file(img_io, mimetype='image/png')
        
        # Read raster data for this tile
        with rasterio.open(water_raster['path']) as src:
            # Transform tile bounds to raster CRS
            if src.crs.to_epsg() != 4326:
                from rasterio.warp import transform_bounds as tb
                raster_bounds = tb('EPSG:4326', src.crs, lon_min, lat_min, lon_max, lat_max)
            else:
                raster_bounds = (lon_min, lat_min, lon_max, lat_max)
            
            # Create window
            window = rasterio.windows.from_bounds(*raster_bounds, src.transform)
            
            # Read data
            data = src.read(1, window=window)
            
            # Resize to 256x256 if needed
            if data.shape != (256, 256):
                from PIL import Image as PILImage
                img_data = PILImage.fromarray(data)
                img_data = img_data.resize((256, 256), PILImage.NEAREST)
                data = np.array(img_data)
            
            # Create blue water visualization
            # Show only pixels with value 70 (persistent water)
            rgba = np.zeros((256, 256, 4), dtype=np.uint8)
            
            # Water pixels: only value 70 shows as water
            water_mask = data == 70
            rgba[water_mask] = [30, 144, 255, 180]  # Dodger blue with transparency
            
            # All other pixels (0, 250, etc.): fully transparent
            rgba[~water_mask] = [0, 0, 0, 0]
            
            # Convert to PIL Image
            img = Image.fromarray(rgba, 'RGBA')
            
            # Save to BytesIO
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            
            return send_file(img_io, mimetype='image/png')
            
    except Exception as e:
        print(f"Error generating water tile {z}/{x}/{y}: {e}")
        # Return transparent tile on error
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        return send_file(img_io, mimetype='image/png')

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
    
    # Further filter with actual geometry intersection
    gdf_filtered = gdf_subset[gdf_subset.geometry.intersects(bbox)]
    
    # Limit results
    if len(gdf_filtered) > max_features:
        gdf_filtered = gdf_filtered.sample(n=max_features, random_state=42)
    
    return gdf_filtered

@app.route('/')
def index():
    """
    Main page with the interactive map
    """
    # Check if water layer is available
    water_available = water_raster is not None
    
    html_template = """
<!DOCTYPE html>
<html>
<head>
    <title>Italian Agricultural Parcels - Interactive Map</title>
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
        .water-legend { background: linear-gradient(90deg, rgba(30,144,255,0) 0%, rgba(30,144,255,0.7) 100%); }
    </style>
</head>
<body>
    <div id="container">
        <div id="map"></div>
        <div id="sidebar">
            <h2>🌾 Italian Agriculture {% if water_available %}& 🌊 Water Bodies{% endif %}</h2>
            
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
                <h4>Map Layers Legend</h4>
                <div id="legend-content"></div>
                {% if water_available %}
                <div class="legend-item">
                    <div class="legend-color water-legend"></div>
                    <span>🌊 Persistent Water Bodies (2025)</span>
                </div>
                {% endif %}
            </div>
            
            <div class="info-box">
                <h4>💡 Tips</h4>
                <ul>
                    <li>Zoom in for more parcels</li>
                    <li>Click parcels for details</li>
                    <li>Charts update with map view</li>
                    <li><strong>{{ parcel_count }} total parcels</strong> in dataset</li>
                    {% if water_available %}
                    <li><strong>Water layer</strong> shows persistent water bodies</li>
                    {% endif %}
                    <li>Use layer control (top-right) to toggle layers</li>
                </ul>
            </div>
        </div>
    </div>

    <script>
        // Initialize map centered on Northern Italy
        var map = L.map('map').setView([45.5, 9.5], 9);
        
        // Define base layers
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
            
            "CartoDB Light": L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap © CartoDB'
            }),
            
            "CartoDB Dark": L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
                attribution: '© OpenStreetMap © CartoDB'
            })
        };
        
        // Add default base layer
        baseLayers["OpenStreetMap"].addTo(map);
        
        // Layer group for parcels
        var parcelLayer = L.layerGroup().addTo(map);
        
        // Define overlay layers
        var overlayLayers = {
            "🌾 Agricultural Parcels": parcelLayer
        };
        
        {% if water_available %}
        // Add water bodies layer
        var waterLayer = L.tileLayer('/tiles/water/{z}/{x}/{y}.png', {
            attribution: 'Water Bodies Data 2025',
            opacity: 0.7,
            zIndex: 1000
        });
        
        overlayLayers["🌊 Persistent Water Bodies"] = waterLayer;
        {% endif %}
        
        // Add layer control
        L.control.layers(baseLayers, overlayLayers, {
            position: 'topright',
            collapsed: false
        }).addTo(map);
        
        // Crop colors from backend
        var cropColors = {{ crop_colors | safe }};
        
        // Update legend
        function updateLegend() {
            var legendContent = document.getElementById('legend-content');
            legendContent.innerHTML = '<h5 style="margin: 5px 0;">Agricultural Crops:</h5>';
            
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
                        
                        // Add popup
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
                                    <strong>Direct Match:</strong>
                                    <span style="color: ${feature.properties.Direct_Match === 'yes' ? '#27ae60' : '#e74c3c'}; font-weight: bold;">
                                        ${feature.properties.Direct_Match === 'yes' ? 'Yes' : 'No'}
                                    </span>
                                </div>
                                
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
    
    return render_template_string(
        html_template, 
        parcel_count=f"{len(gdf_global):,}",
        crop_colors=json.dumps(crop_colors),
        water_available=water_available
    )

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
            crop_counts = gdf_filtered['English_Name'].value_counts()
            stats['crop_distribution'] = crop_counts.head(15).to_dict()
            
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
            'bounds': gdf_global.total_bounds.tolist(),
            'water_available': water_raster is not None
        }
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Configuration
    GPKG_FILE = "downloaded_data/merged_geodata.gpkg"  # 👈 AGRICULTURAL DATA FILE PATH
    WATER_FILE = "data/water_bodies_italy_2025_06.tif"     # 👈 WATER BODIES FILE PATH
    
    print("🚀 Starting Italian Agricultural Data Web App with Water Bodies")
    print("=" * 60)
    
    try:
        # Load agricultural data
        load_data(GPKG_FILE)
        
        # Load water bodies data
        water_loaded = load_water_data(WATER_FILE)
        
        print(f"\n✅ Ready to serve!")
        print(f"📊 Dataset: {len(gdf_global):,} agricultural parcels")
        print(f"🌊 Water layer: {'✅ Available' if water_loaded else '❌ Not available'}")
        print(f"🎯 Features: Interactive map + real-time charts + water overlay")
        print("=" * 60)
        print("\n🌐 GitHub Codespaces Access:")
        print("1. Look at the 'PORTS' tab in the bottom panel of VS Code")
        print("2. Find port 5000 and click the 🌐 icon or copy the URL")
        print("3. If it shows 'Private', right-click and change to 'Public'")
        print("4. The URL format should be: https://your-codespace-5000.preview.app.github.dev")
        print("=" * 60)
        
        # Start server
        app.run(debug=False, host='0.0.0.0', port=5000, threaded=True)
        
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("Make sure to update file paths in the script")