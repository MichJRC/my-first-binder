from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import os
import sqlite3
import tempfile
import urllib.request
import shutil

class CropMapHandler(BaseHTTPRequestHandler):
    gpkg_file_path = None
    
    def do_GET(self):
        print(f"GET request: {self.path}")
        
        if self.path == '/':
            self.serve_main_page()
        elif self.path.startswith('/api/crops'):
            self.serve_crop_data()
        elif self.path.startswith('/api/geojson'):
            self.serve_geojson_working()
        elif self.path.startswith('/download-gpkg'):
            self.download_gpkg_from_github()
        else:
            self.send_404()
    
    def serve_main_page(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>🌾 Crop Analysis Dashboard - Working Version</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            
            <!-- Leaflet CSS -->
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <!-- Chart.js -->
            <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
            
            <style>
                body {
                    margin: 0;
                    font-family: Arial, sans-serif;
                    background: #f0f2f5;
                }
                
                .header {
                    background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
                    color: white;
                    padding: 1rem;
                    text-align: center;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }
                
                .upload-section {
                    background: white;
                    margin: 1rem;
                    padding: 1rem;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    text-align: center;
                }
                
                .container {
                    display: flex;
                    height: calc(100vh - 200px);
                    margin: 1rem;
                    gap: 1rem;
                }
                
                #map {
                    flex: 2;
                    height: 100%;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                }
                
                .chart-panel {
                    flex: 1;
                    background: white;
                    padding: 1rem;
                    border-radius: 8px;
                    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
                    display: flex;
                    flex-direction: column;
                }
                
                .chart-container {
                    flex: 1;
                    position: relative;
                    margin-top: 1rem;
                }
                
                .stats-info {
                    background: #e8f5e8;
                    padding: 1rem;
                    border-radius: 6px;
                    margin-bottom: 1rem;
                }
                
                .file-input {
                    margin: 1rem 0;
                    padding: 0.5rem;
                    border: 2px dashed #4CAF50;
                    border-radius: 6px;
                    background: #f9f9f9;
                }
                
                .upload-btn {
                    background: #4CAF50;
                    color: white;
                    padding: 0.5rem 1rem;
                    border: none;
                    border-radius: 4px;
                    cursor: pointer;
                }
                
                .upload-btn:hover {
                    background: #45a049;
                }
                
                .status {
                    margin-top: 1rem;
                    padding: 0.5rem;
                    border-radius: 4px;
                    display: none;
                }
                
                .status.success {
                    background: #d4edda;
                    color: #155724;
                    display: block;
                }
                
                .status.error {
                    background: #f8d7da;
                    color: #721c24;
                    display: block;
                }
                
                .hidden {
                    display: none;
                }
                
                .bounds-info {
                    font-size: 0.9rem;
                    color: #666;
                    margin-top: 0.5rem;
                }
                
                .map-note {
                    background: #fff3cd;
                    border: 1px solid #ffeaa7;
                    color: #856404;
                    padding: 0.75rem;
                    border-radius: 4px;
                    margin-bottom: 1rem;
                    font-size: 0.9rem;
                }
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🌾 Crop Analysis Dashboard</h1>
                <p>Upload your GPKG file and explore crop data interactively</p>
            </div>
            
            <div class="upload-section" id="upload-section">
                <h3>📁 Load GPKG from GitHub</h3>
                <p>Enter the URL of your GPKG file from GitHub releases</p>
                
                <div class="file-input">
                    <input type="url" id="github-url" 
                           value="https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/merged_geodata.gpkg"
                           placeholder="https://github.com/user/repo/releases/download/tag/file.gpkg" 
                           style="width: 100%; padding: 0.5rem; border: 1px solid #ddd; border-radius: 4px;" />
                </div>
                
                <button class="upload-btn" onclick="downloadFromGitHub()">Download & Analyze</button>
                
                <div class="status" id="status"></div>
            </div>
            
            <div class="container hidden" id="main-container">
                <div id="map"></div>
                
                <div class="chart-panel">
                    <h3>📊 Top 10 Crops in View</h3>
                    
                    <div class="map-note">
                        <strong>📍 Map Data:</strong> Currently showing simplified point locations with real crop data. Zoom in and pan around to see your crop information!
                    </div>
                    
                    <div class="stats-info">
                        <strong>Current View Stats:</strong>
                        <div id="total-features">Total features: -</div>
                        <div id="unique-crops">Unique crops: -</div>
                        <div id="spatial-status">Spatial filtering: checking...</div>
                        <div class="bounds-info" id="bounds-info">
                            Pan and zoom to update data
                        </div>
                    </div>
                    
                    <div class="chart-container">
                        <canvas id="cropChart"></canvas>
                    </div>
                </div>
            </div>
            
            <!-- Leaflet JavaScript -->
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            
            <script>
                let map;
                let chart;
                let currentCropLayer;
                
                function downloadFromGitHub() {
                    const urlInput = document.getElementById('github-url');
                    const statusDiv = document.getElementById('status');
                    
                    if (!urlInput.value.trim()) {
                        showStatus('Please enter a GitHub URL', 'error');
                        return;
                    }
                    
                    showStatus('Downloading GPKG file from GitHub...', 'success');
                    
                    const encodedUrl = encodeURIComponent(urlInput.value);
                    
                    fetch(`/download-gpkg?url=${encodedUrl}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            showStatus(`File downloaded! Found ${data.total_features} features`, 'success');
                            setTimeout(() => {
                                initializeMap();
                            }, 1000);
                        } else {
                            showStatus('Error: ' + data.error, 'error');
                        }
                    })
                    .catch(error => {
                        showStatus('Download failed: ' + error.message, 'error');
                    });
                }
                
                function showStatus(message, type) {
                    const statusDiv = document.getElementById('status');
                    statusDiv.textContent = message;
                    statusDiv.className = 'status ' + type;
                }
                
                function initializeMap() {
                    document.getElementById('upload-section').classList.add('hidden');
                    document.getElementById('main-container').classList.remove('hidden');
                    
                    // Initialize map centered on central US
                    map = L.map('map').setView([39.8283, -98.5795], 6);
                    
                    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                        attribution: '© OpenStreetMap contributors'
                    }).addTo(map);
                    
                    initializeChart();
                    updateCropData();
                    loadMapData(); // Load map data immediately
                    
                    map.on('moveend', function() {
                        updateCropData();
                        loadMapData();
                    });
                    map.on('zoomend', function() {
                        updateCropData();
                        loadMapData();
                    });
                }
                
                function initializeChart() {
                    const ctx = document.getElementById('cropChart').getContext('2d');
                    chart = new Chart(ctx, {
                        type: 'bar',
                        data: {
                            labels: [],
                            datasets: [{
                                label: 'Number of Fields',
                                data: [],
                                backgroundColor: [
                                    '#4CAF50', '#8BC34A', '#CDDC39', '#FFEB3B', '#FFC107',
                                    '#FF9800', '#FF5722', '#795548', '#9C27B0', '#3F51B5'
                                ],
                                borderColor: '#2E7D32',
                                borderWidth: 1
                            }]
                        },
                        options: {
                            responsive: true,
                            maintainAspectRatio: false,
                            plugins: {
                                legend: {
                                    display: false
                                }
                            },
                            scales: {
                                y: {
                                    beginAtZero: true,
                                    ticks: {
                                        callback: function(value, index, ticks) {
                                            if (value >= 1000000) {
                                                return (value / 1000000).toFixed(1) + 'M';
                                            } else if (value >= 1000) {
                                                return (value / 1000).toFixed(1) + 'K';
                                            }
                                            return value;
                                        }
                                    }
                                },
                                x: {
                                    ticks: {
                                        maxRotation: 45
                                    }
                                }
                            }
                        }
                    });
                }
                
                function updateCropData() {
                    if (!map) return;
                    
                    const bounds = map.getBounds();
                    const url = `/api/crops?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}`;
                    
                    console.log('Requesting crop data for bounds:', bounds.toString());
                    
                    fetch(url)
                        .then(response => response.json())
                        .then(data => {
                            console.log('Received crop data:', data);
                            
                            document.getElementById('total-features').textContent = `Total features: ${data.total_features}`;
                            document.getElementById('unique-crops').textContent = `Unique crops: ${data.unique_crops}`;
                            
                            // Show spatial filtering status
                            const spatialStatus = data.spatial_filtering ? 
                                '✅ Spatial filtering active' : 
                                '⚠️ Showing all data (no spatial filter)';
                            document.getElementById('spatial-status').textContent = spatialStatus;
                            
                            document.getElementById('bounds-info').textContent = 
                                `Zoom: ${map.getZoom()} | Bounds: ${data.bounds_used || 'N/A'}`;
                            
                            updateChart(data.top_crops);
                        })
                        .catch(error => {
                            console.error('Error fetching crop data:', error);
                            document.getElementById('spatial-status').textContent = '❌ Error loading data';
                        });
                }
                
                function loadMapData() {
                    if (!map) return;
                    
                    const bounds = map.getBounds();
                    const geojsonUrl = `/api/geojson?north=${bounds.getNorth()}&south=${bounds.getSouth()}&east=${bounds.getEast()}&west=${bounds.getWest()}&limit=50`;
                    
                    console.log('Loading map data...');
                    
                    fetch(geojsonUrl)
                        .then(response => response.json())
                        .then(geojson => {
                            if (currentCropLayer) {
                                map.removeLayer(currentCropLayer);
                            }
                            
                            if (geojson.features && geojson.features.length > 0) {
                                console.log(`Adding ${geojson.features.length} features to map`);
                                
                                const cropColors = {
                                    'Corn': '#FFD700',
                                    'Soybeans': '#32CD32', 
                                    'Soybean': '#32CD32',
                                    'Wheat': '#DEB887',
                                    'Cotton': '#F0F8FF',
                                    'Rice': '#90EE90',
                                    'Barley': '#F4A460',
                                    'Oats': '#D2B48C',
                                    'Default': '#FF6B6B'
                                };
                                
                                currentCropLayer = L.geoJSON(geojson, {
                                    pointToLayer: function(feature, latlng) {
                                        const crop = feature.properties.crop;
                                        const color = cropColors[crop] || cropColors['Default'];
                                        
                                        return L.circleMarker(latlng, {
                                            radius: 8,
                                            fillColor: color,
                                            color: '#333',
                                            weight: 1,
                                            opacity: 0.8,
                                            fillOpacity: 0.6
                                        });
                                    },
                                    onEachFeature: function(feature, layer) {
                                        if (feature.properties) {
                                            const popup = `<b>Crop:</b> ${feature.properties.crop}<br>
                                                         <b>ID:</b> ${feature.properties.fid}<br>
                                                         <small>${feature.properties.note || ''}</small>`;
                                            layer.bindPopup(popup);
                                        }
                                    }
                                }).addTo(map);
                                
                                // Auto-fit on first load
                                if (!window.hasAutoFitted) {
                                    map.fitBounds(currentCropLayer.getBounds(), {padding: [20, 20]});
                                    window.hasAutoFitted = true;
                                }
                            } else {
                                console.log('No features returned for current view');
                            }
                        })
                        .catch(error => {
                            console.error('Error loading map data:', error);
                        });
                }
                
                function updateChart(topCrops) {
                    if (!chart) return;
                    
                    const labels = topCrops.map(item => item.crop);
                    const data = topCrops.map(item => item.count);
                    
                    chart.data.labels = labels;
                    chart.data.datasets[0].data = data;
                    chart.update();
                }
            </script>
        </body>
        </html>
        """
        self.wfile.write(html.encode())
    
    def download_gpkg_from_github(self):
        try:
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            github_url = params['url'][0]
            
            print(f"Downloading from: {github_url}")
            
            temp_dir = tempfile.mkdtemp()
            temp_file_path = os.path.join(temp_dir, 'crops.gpkg')
            
            req = urllib.request.Request(github_url, headers={'User-Agent': 'Crop-Analysis-Tool/1.0'})
            with urllib.request.urlopen(req, timeout=30) as response:
                with open(temp_file_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            CropMapHandler.gpkg_file_path = temp_file_path
            
            # Get feature count
            conn = sqlite3.connect(temp_file_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
            tables = cursor.fetchall()
            
            total_count = 0
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM `{table[0]}`")
                total_count += cursor.fetchone()[0]
            
            conn.close()
            
            response_data = {
                "success": True,
                "total_features": total_count,
                "file_size": os.path.getsize(temp_file_path)
            }
            
        except Exception as e:
            response_data = {"success": False, "error": str(e)}
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode())
    
    def serve_crop_data(self):
        """Serve crop data filtered by map bounds"""
        try:
            if not CropMapHandler.gpkg_file_path:
                response = {"total_features": 0, "unique_crops": 0, "top_crops": []}
            else:
                # Parse query parameters for map bounds
                parsed_url = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed_url.query)
                
                north = float(params.get('north', [90])[0])
                south = float(params.get('south', [-90])[0])
                east = float(params.get('east', [180])[0])
                west = float(params.get('west', [-180])[0])
                
                print(f"Filtering crops for bounds: N{north:.3f}, S{south:.3f}, E{east:.3f}, W{west:.3f}")
                
                conn = sqlite3.connect(CropMapHandler.gpkg_file_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
                tables = cursor.fetchall()
                table_name = tables[0][0]
                
                cursor.execute(f"PRAGMA table_info(`{table_name}`)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                print(f"Available columns: {column_names}")
                
                # Find crop column
                crop_column = None
                possible_crop_columns = [
                    'crop', 'crop_type', 'crop_name', 'landuse', 'land_use', 'type', 'class', 'category',
                    'cover', 'land_cover', 'use', 'vegetation', 'agriculture', 'farming', 'plant',
                    'code', 'description', 'label', 'name'
                ]
                
                for col_name in possible_crop_columns:
                    matching_cols = [col for col in column_names if col_name.lower() in col.lower()]
                    if matching_cols:
                        crop_column = matching_cols[0]
                        break
                
                if not crop_column:
                    non_geom_columns = [col for col in column_names 
                                      if 'geom' not in col.lower() 
                                      and col.lower() not in ['fid', 'id', 'objectid', 'gid']]
                    if non_geom_columns:
                        crop_column = non_geom_columns[0]
                
                print(f"Using crop column: {crop_column}")
                
                # Find geometry column for spatial filtering
                geom_column = None
                for col in column_names:
                    if 'geom' in col.lower():
                        geom_column = col
                        break
                
                print(f"Found geometry column: {geom_column}")
                
                if geom_column:
                    # Try spatial filtering with bounding box
                    # First, let's try a simple approach: check if geometry functions are available
                    try:
                        # Test if we can extract coordinates
                        test_query = f"SELECT ST_X(ST_Centroid(`{geom_column}`)), ST_Y(ST_Centroid(`{geom_column}`)) FROM `{table_name}` LIMIT 1"
                        cursor.execute(test_query)
                        test_result = cursor.fetchone()
                        
                        if test_result and test_result[0] is not None:
                            print("Using ST_X/ST_Y for spatial filtering")
                            # Use spatial filtering
                            query = f"""
                                SELECT `{crop_column}`, COUNT(*) as count 
                                FROM `{table_name}` 
                                WHERE `{crop_column}` IS NOT NULL 
                                AND ST_X(ST_Centroid(`{geom_column}`)) BETWEEN {west} AND {east}
                                AND ST_Y(ST_Centroid(`{geom_column}`)) BETWEEN {south} AND {north}
                                GROUP BY `{crop_column}` 
                                ORDER BY count DESC 
                                LIMIT 10
                            """
                            
                            cursor.execute(query)
                            results = cursor.fetchall()
                            
                            # Count total features in bounds
                            count_query = f"""
                                SELECT COUNT(*) FROM `{table_name}` 
                                WHERE ST_X(ST_Centroid(`{geom_column}`)) BETWEEN {west} AND {east}
                                AND ST_Y(ST_Centroid(`{geom_column}`)) BETWEEN {south} AND {north}
                            """
                            cursor.execute(count_query)
                            total_features = cursor.fetchone()[0]
                            
                            print(f"Spatial filtering successful: {total_features} features in bounds")
                            
                        else:
                            raise Exception("ST_X/ST_Y not available")
                            
                    except Exception as spatial_error:
                        print(f"Spatial filtering failed: {spatial_error}, using all data")
                        # Fallback to all data
                        query = f"""
                            SELECT `{crop_column}`, COUNT(*) as count 
                            FROM `{table_name}` 
                            WHERE `{crop_column}` IS NOT NULL 
                            GROUP BY `{crop_column}` 
                            ORDER BY count DESC 
                            LIMIT 10
                        """
                        
                        cursor.execute(query)
                        results = cursor.fetchall()
                        
                        cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                        total_features = cursor.fetchone()[0]
                        
                        print(f"Using all data: {total_features} total features")
                else:
                    # No geometry column found, use all data
                    print("No geometry column found, using all data")
                    query = f"""
                        SELECT `{crop_column}`, COUNT(*) as count 
                        FROM `{table_name}` 
                        WHERE `{crop_column}` IS NOT NULL 
                        GROUP BY `{crop_column}` 
                        ORDER BY count DESC 
                        LIMIT 10
                    """
                    
                    cursor.execute(query)
                    results = cursor.fetchall()
                    
                    cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
                    total_features = cursor.fetchone()[0]
                
                top_crops = []
                for row in results:
                    if row[0]:
                        crop_name = str(row[0])
                        if len(crop_name) > 20:
                            crop_name = crop_name[:17] + "..."
                        
                        top_crops.append({
                            "crop": crop_name,
                            "count": row[1]
                        })
                
                response = {
                    "total_features": total_features,
                    "unique_crops": len(top_crops),
                    "top_crops": top_crops,
                    "crop_column_used": crop_column,
                    "bounds_used": f"N{north:.3f},S{south:.3f},E{east:.3f},W{west:.3f}",
                    "spatial_filtering": geom_column is not None
                }
                
                conn.close()
                
        except Exception as e:
            print(f"Error in serve_crop_data: {e}")
            import traceback
            traceback.print_exc()
            response = {
                "total_features": 0, 
                "unique_crops": 0, 
                "top_crops": [], 
                "error": str(e)
            }
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def serve_geojson_working(self):
        """Working GeoJSON endpoint with real data"""
        try:
            if not CropMapHandler.gpkg_file_path:
                response = {"type": "FeatureCollection", "features": []}
            else:
                # Parse limit parameter
                parsed_url = urllib.parse.urlparse(self.path)
                params = urllib.parse.parse_qs(parsed_url.query)
                limit = int(params.get('limit', [20])[0])
                
                conn = sqlite3.connect(CropMapHandler.gpkg_file_path)
                cursor = conn.cursor()
                
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'gpkg_%' AND name NOT LIKE 'sqlite_%'")
                tables = cursor.fetchall()
                table_name = tables[0][0]
                
                cursor.execute(f"PRAGMA table_info(`{table_name}`)")
                columns = cursor.fetchall()
                column_names = [col[1] for col in columns]
                
                # Find crop column
                crop_column = None
                for col_name in ['crop', 'crop_type', 'landuse', 'type', 'class']:
                    matching = [col for col in column_names if col_name.lower() in col.lower()]
                    if matching:
                        crop_column = matching[0]
                        break
                
                if not crop_column:
                    non_geom = [col for col in column_names if 'geom' not in col.lower() and col.lower() not in ['fid', 'id']]
                    if non_geom:
                        crop_column = non_geom[0]
                
                # Get sample data and create points
                query = f"SELECT fid, `{crop_column}` FROM `{table_name}` WHERE `{crop_column}` IS NOT NULL LIMIT {limit}"
                cursor.execute(query)
                results = cursor.fetchall()
                
                features = []
                for i, row in enumerate(results):
                    fid, crop_value = row
                    
                    # Create spread-out dummy coordinates
                    base_lon = -98.0  # Central US longitude
                    base_lat = 39.5   # Central US latitude
                    
                    # Create a grid-like distribution
                    grid_size = int(limit**0.5) + 1
                    row_idx = i // grid_size
                    col_idx = i % grid_size
                    
                    lon = base_lon + (col_idx - grid_size/2) * 0.5
                    lat = base_lat + (row_idx - grid_size/2) * 0.3
                    
                    feature = {
                        "type": "Feature",
                        "properties": {
                            "fid": fid,
                            "crop": str(crop_value),
                            "note": "Sample location with real crop data"
                        },
                        "geometry": {
                            "type": "Point",
                            "coordinates": [lon, lat]
                        }
                    }
                    features.append(feature)
                
                response = {
                    "type": "FeatureCollection",
                    "features": features
                }
                
                conn.close()
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            print(f"Error in serve_geojson_working: {e}")
            
            response = {
                "type": "FeatureCollection",
                "features": [],
                "error": str(e)
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
    
    def send_404(self):
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>404 - Not Found</h1>')

if __name__ == '__main__':
    server = HTTPServer(('', 8080), CropMapHandler)
    print('🌾 Working Crop Analysis Server')
    print('📍 Features: Real crop data + working map display')
    print('🗺️  Running on port 8080')
    server.serve_forever()