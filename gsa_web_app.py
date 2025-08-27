#!/usr/bin/env python3
"""
Step 3: Interactive Web Application for GSA Data
Flask backend with GeoPandas + Leaflet frontend + Water Bodies Layer (Vector-based)
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
import rasterio
import rasterio.features
from rasterio.warp import transform_bounds, reproject, calculate_default_transform, Resampling
from shapely.geometry import shape
import os

warnings.filterwarnings('ignore')

app = Flask(__name__)

# Global variables for data
gdf_global = None
top_crops = None
crop_colors = None
water_gdf = None

def load_data(file_path):
    """
    Load and prepare the GPKG data with memory optimizations
    """
    global gdf_global, top_crops, crop_colors
    
    print("🌾 Loading GSA Agricultural Data...")
    
    # Load data
    gdf = gpd.read_file(file_path)
    print(f"Loaded {len(gdf):,} agricultural parcels")
    print(f"Current CRS: {gdf.crs}")
    
    # Convert to WGS84 for web display (with memory management)
    if gdf.crs.to_epsg() != 4326:
        print("Converting to WGS84 (this may take a moment for large datasets)...")
        try:
            # Process in chunks to avoid memory issues
            chunk_size = 50000
            if len(gdf) > chunk_size:
                print(f"Processing in chunks of {chunk_size:,} features...")
                chunks = []
                for i in range(0, len(gdf), chunk_size):
                    print(f"Processing chunk {i//chunk_size + 1}/{(len(gdf)-1)//chunk_size + 1}")
                    chunk = gdf.iloc[i:i+chunk_size].copy()
                    chunk = chunk.to_crs('EPSG:4326')
                    chunks.append(chunk)
                
                # Combine chunks
                print("Combining chunks...")
                gdf = gpd.GeoDataFrame(pd.concat(chunks, ignore_index=True), crs='EPSG:4326')
            else:
                gdf = gdf.to_crs('EPSG:4326')
        except Exception as e:
            print(f"❌ Error during coordinate conversion: {e}")
            print("Try running with a smaller dataset or check memory availability")
            raise
    
    # Prepare crop color mapping
    print("Analyzing crop types...")
    top_crops = gdf['English_Name'].value_counts().head(15)
    colors = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4', '#FFEAA7', 
              '#DDA0DD', '#98D8C8', '#F7DC6F', '#BB8FCE', '#85C1E9',
              '#F8C471', '#82E0AA', '#F1948A', '#85C1E9', '#D7BDE2']
    crop_colors = {crop: colors[i] for i, crop in enumerate(top_crops.index)}
    
    # Add centroids for faster point-in-bbox calculations
    print("Computing centroids...")
    try:
        gdf['centroid_x'] = gdf.geometry.centroid.x
        gdf['centroid_y'] = gdf.geometry.centroid.y
    except Exception as e:
        print(f"Warning: Could not compute centroids: {e}")
        # Fallback: use bounds instead
        bounds = gdf.bounds
        gdf['centroid_x'] = (bounds['minx'] + bounds['maxx']) / 2
        gdf['centroid_y'] = (bounds['miny'] + bounds['maxy']) / 2
    
    # Create spatial index for fast bbox queries
    print("Creating spatial index...")
    try:
        gdf.sindex
    except Exception as e:
        print(f"Warning: Could not create spatial index: {e}")
    
    gdf_global = gdf
    print(f"✅ Data loaded and indexed successfully!")
    print(f"Memory usage: ~{gdf.memory_usage(deep=True).sum() / 1024**2:.1f} MB")
    return gdf

def load_water_data(water_file_path):
    """
    Load and vectorize water bodies raster data with proper projection handling
    """
    global water_gdf
    
    if not os.path.exists(water_file_path):
        print(f"⚠️ Water file not found: {water_file_path}")
        return False
    
    print("🌊 Loading and Vectorizing Water Bodies Data...")
    
    try:
        with rasterio.open(water_file_path) as src:
            print(f"Raster CRS: {src.crs}")
            print(f"Raster bounds: {src.bounds}")
            print(f"Raster shape: {src.shape}")
            print(f"Raster transform: {src.transform}")
            
            # Read the raster data
            water_data = src.read(1)
            
            print(f"Data shape: {water_data.shape}")
            print(f"Unique values: {np.unique(water_data)}")
            
            # Check for water pixels
            water_mask = water_data == 70
            water_pixel_count = np.sum(water_mask)
            print(f"Pixels with value 70: {water_pixel_count:,}")
            
            if water_pixel_count == 0:
                print("⚠️ No pixels with value 70 found!")
                return False
            
            # Use rasterio.warp.reproject to properly handle coordinate transformations
            from rasterio.warp import reproject, calculate_default_transform, Resampling
            from rasterio.transform import from_bounds
            
            print("Reprojecting raster to WGS84...")
            
            # Calculate transform for WGS84
            dst_crs = 'EPSG:4326'
            
            # Get bounds in destination CRS
            dst_bounds = transform_bounds(src.crs, dst_crs, *src.bounds)
            print(f"Destination bounds (WGS84): {dst_bounds}")
            
            # Calculate destination transform and dimensions
            dst_transform, dst_width, dst_height = calculate_default_transform(
                src.crs, dst_crs, src.width, src.height, *src.bounds
            )
            
            # Create destination array
            dst_array = np.zeros((dst_height, dst_width), dtype=src.dtypes[0])
            
            # Reproject the raster
            reproject(
                source=rasterio.band(src, 1),
                destination=dst_array,
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=dst_transform,
                dst_crs=dst_crs,
                resampling=Resampling.nearest
            )
            
            print(f"Reprojected array shape: {dst_array.shape}")
            print(f"Reprojected unique values: {np.unique(dst_array)}")
            
            # Create mask for reprojected data
            water_mask_reproj = dst_array == 70
            water_pixel_count_reproj = np.sum(water_mask_reproj)
            print(f"Water pixels after reprojection: {water_pixel_count_reproj:,}")
            
            if water_pixel_count_reproj == 0:
                print("⚠️ No water pixels found after reprojection!")
                return False
            
            # Vectorize the reprojected data
            print("Vectorizing reprojected water pixels to polygons...")
            shapes_gen = rasterio.features.shapes(
                dst_array,
                mask=water_mask_reproj,
                transform=dst_transform,
                connectivity=8
            )
            
            # Convert to geodataframe
            geometries = []
            values = []
            for geom, value in shapes_gen:
                if value == 70:
                    try:
                        geom_shape = shape(geom)
                        # Filter out very small polygons (likely noise)
                        if geom_shape.area > 0.0001:  # Minimum area threshold
                            geometries.append(geom_shape)
                            values.append(value)
                    except Exception as e:
                        print(f"Warning: Skipping invalid geometry: {e}")
                        continue
            
            print(f"Created {len(geometries)} valid water polygons")
            
            if geometries:
                # Create GeoDataFrame directly in WGS84
                water_gdf = gpd.GeoDataFrame({
                    'water_type': ['persistent_water'] * len(geometries),
                    'value': values
                }, geometry=geometries, crs='EPSG:4326')
                
                print(f"Water GDF bounds in WGS84: {water_gdf.total_bounds}")
                
                # Validate coordinates are reasonable for Italy
                bounds = water_gdf.total_bounds
                italy_bounds = [6.6, 35.5, 18.5, 47.1]  # Approximate Italy bounds
                
                if (bounds[0] < italy_bounds[0] - 5 or bounds[1] < italy_bounds[1] - 5 or
                    bounds[2] > italy_bounds[2] + 5 or bounds[3] > italy_bounds[3] + 5):
                    print(f"⚠️ Warning: Water bounds seem outside Italy region:")
                    print(f"   Water bounds: {bounds}")
                    print(f"   Expected Italy bounds: {italy_bounds}")
                else:
                    print(f"✅ Water bounds look good for Italy region")
                
                # Create spatial index
                water_gdf.sindex
                
                # Simplify geometries slightly to improve performance
                print("Simplifying geometries...")
                water_gdf.geometry = water_gdf.geometry.simplify(0.0001, preserve_topology=True)
                
                print(f"✅ Water bodies vectorized: {len(water_gdf):,} polygons")
                print(f"✅ Final bounds: {water_gdf.total_bounds}")
                return True
            else:
                print("⚠️ No valid water polygons created")
                return False
        
    except Exception as e:
        print(f"❌ Error loading water data: {e}")
        import traceback
        traceback.print_exc()
        return False

@lru_cache(maxsize=100)
def get_features_in_bbox(north, south, east, west, max_features=1000):
    """
    Get agricultural features within bounding box with caching and limits
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

def get_water_in_bbox(north, south, east, west):
    """
    Get water features within bounding box
    """
    if water_gdf is None:
        return gpd.GeoDataFrame()
    
    # Create bounding box
    bbox = box(west, south, east, north)
    
    # Filter water features
    water_filtered = water_gdf[water_gdf.geometry.intersects(bbox)]
    
    return water_filtered

@app.route('/')
def index():
    """
    Main page with the interactive map
    """
    # Check if water layer is available
    water_available = water_gdf is not None
    
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
                {% if water_available %}
                <div id="water-count"></div>
                {% endif %}
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
                    <li><strong>{{ water_count }} water bodies</strong> detected</li>
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
        
        // Layer groups for parcels and water
        var parcelLayer = L.layerGroup().addTo(map);
        var waterLayerGroup = L.layerGroup();
        
        // Define overlay layers
        var overlayLayers = {
            "🌾 Agricultural Parcels": parcelLayer
        };
        
        {% if water_available %}
        overlayLayers["🌊 Persistent Water Bodies"] = waterLayerGroup;
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
        
        // Function to update agricultural data
        function updateMapData() {
            var bounds = map.getBounds();
            var zoom = map.getZoom();
            
            // Show loading
            document.getElementById('parcel-count').innerHTML = '<span class="loading">Loading...</span>';
            
            // Determine max features based on zoom level
            var maxFeatures = zoom > 12 ? 2000 : zoom > 10 ? 1000 : 500;
            
            // Fetch agricultural data
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
                    console.error('Error fetching agricultural data:', error);
                    document.getElementById('parcel-count').innerHTML = 'Error loading data';
                });
            
            {% if water_available %}
            // Update water bodies if layer is active
            if (map.hasLayer(waterLayerGroup)) {
                updateWaterData();
            }
            {% endif %}
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
        
        {% if water_available %}
        // Function to update water bodies
        function updateWaterData() {
            var bounds = map.getBounds();
            
            fetch(`/api/water?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}`)
                .then(response => response.json())
                .then(data => {
                    // Clear existing water features
                    waterLayerGroup.clearLayers();
                    
                    // Update water count in sidebar
                    var waterCountEl = document.getElementById('water-count');
                    if (waterCountEl) {
                        waterCountEl.innerHTML = `🌊 ${data.total_count} water bodies in view`;
                    }
                    
                    // Add water features to map
                    data.features.forEach(function(feature) {
                        var waterFeature = L.geoJSON(feature, {
                            style: {
                                fillColor: '#1E90FF',     // Dodger blue
                                weight: 1.5,
                                opacity: 0.8,
                                color: '#0066CC',          // Darker blue border
                                fillOpacity: 0.6
                            }
                        });
                        
                        // Add popup for water bodies
                        waterFeature.bindPopup(`
                            <div style="font-family: Arial, sans-serif;">
                                <h4 style="margin: 0 0 10px 0; color: #0066CC;">🌊 Persistent Water Body</h4>
                                <div><strong>Type:</strong> ${feature.properties.water_type}</div>
                                <div><strong>Value:</strong> ${feature.properties.value}</div>
                                <div><strong>Data Source:</strong> 2025 Water Occurrence</div>
                                <div style="font-size: 11px; color: #666; margin-top: 8px;">
                                    Detected from satellite imagery
                                </div>
                            </div>
                        `);
                        
                        waterLayerGroup.addLayer(waterFeature);
                    });
                })
                .catch(error => {
                    console.error('Error loading water data:', error);
                });
        }
        
        // Listen for water layer toggle
        map.on('overlayadd', function(e) {
            if (e.name === '🌊 Persistent Water Bodies') {
                updateWaterData();
            }
        });
        
        map.on('overlayremove', function(e) {
            if (e.name === '🌊 Persistent Water Bodies') {
                waterLayerGroup.clearLayers();
            }
        });
        {% endif %}
        
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
        water_available=water_available,
        water_count=f"{len(water_gdf):,}" if water_gdf is not None else "0"
    )

@app.route('/api/features')
def get_features():
    """
    API endpoint to get agricultural features within bounding box
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

@app.route('/api/water')
def get_water_features():
    """
    API endpoint to get water features within bounding box
    """
    if water_gdf is None:
        return jsonify({'features': [], 'total_count': 0})
    
    try:
        # Get parameters
        north = float(request.args.get('north', 90))
        south = float(request.args.get('south', -90))
        east = float(request.args.get('east', 180))
        west = float(request.args.get('west', -180))
        
        # Get filtered water data
        water_filtered = get_water_in_bbox(north, south, east, west)
        
        # Convert to GeoJSON
        if len(water_filtered) > 0:
            features = json.loads(water_filtered.to_json())['features']
        else:
            features = []
        
        return jsonify({
            'features': features,
            'total_count': len(water_filtered)
        })
        
    except Exception as e:
        return jsonify({'error': str(e), 'features': [], 'total_count': 0}), 500

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
            'water_available': water_gdf is not None,
            'total_water_bodies': len(water_gdf) if water_gdf is not None else 0
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
        if water_loaded:
            print(f"🌊 Water bodies: {len(water_gdf):,} polygons")
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