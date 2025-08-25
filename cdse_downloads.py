#!/usr/bin/env python3
"""
Standalone Agricultural Data Bounds Analyzer

This script analyzes your agricultural parcel data and generates:
- Bounding box coordinates
- CDSE browser URLs for water data download
- Map center and zoom settings  
- Leaflet map configuration
- Flask API endpoint code

Usage:
    python analyze_agricultural_data.py path/to/your/data.gpkg
"""

import sys
import os
import geopandas as gpd
import numpy as np
from pathlib import Path
import json

class AgriculturalDataAnalyzer:
    """Analyze agricultural data and generate map configurations"""
    
    def __init__(self, data_path):
        self.data_path = Path(data_path)
        self.gdf = None
        self.bounds = None
        self.center = None
        self.zoom = None
        
    def load_data(self):
        """Load and validate the agricultural data"""
        print(f"🌾 Loading agricultural data from: {self.data_path}")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        try:
            self.gdf = gpd.read_file(self.data_path)
            print(f"✅ Loaded {len(self.gdf)} agricultural parcels")
            print(f"📊 Original CRS: {self.gdf.crs}")
            
            if self.gdf.empty:
                raise ValueError("Data file is empty!")
                
            return True
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return False
    
    def calculate_bounds(self):
        """Calculate bounding box and map settings"""
        print("\n📐 Calculating spatial bounds...")
        
        # Ensure data is in WGS84 for web mapping
        if self.gdf.crs != 'EPSG:4326':
            print(f"🔄 Converting from {self.gdf.crs} to EPSG:4326...")
            gdf_wgs84 = self.gdf.to_crs('EPSG:4326')
        else:
            gdf_wgs84 = self.gdf
        
        # Get total bounds
        bounds_array = gdf_wgs84.total_bounds
        west, south, east, north = bounds_array
        
        self.bounds = {
            'west': float(west),
            'south': float(south), 
            'east': float(east),
            'north': float(north)
        }
        
        # Calculate center
        self.center = {
            'lat': float((north + south) / 2),
            'lon': float((east + west) / 2)
        }
        
        # Estimate appropriate zoom level
        lat_range = north - south
        lon_range = east - west
        max_range = max(lat_range, lon_range)
        
        if max_range > 10:
            self.zoom = 6   # Country/large region
        elif max_range > 5:
            self.zoom = 7   # Large region
        elif max_range > 2:
            self.zoom = 8   # Region
        elif max_range > 1:
            self.zoom = 9   # Province/area
        elif max_range > 0.5:
            self.zoom = 10  # City/district
        elif max_range > 0.2:
            self.zoom = 11  # Local area
        else:
            self.zoom = 12  # Very local
        
        print(f"✅ Bounds calculated successfully")
        
    def display_summary(self):
        """Display comprehensive analysis summary"""
        print(f"\n🗺️  AGRICULTURAL DATA ANALYSIS SUMMARY")
        print("=" * 60)
        
        # Basic info
        print(f"\n📂 DATA FILE INFORMATION:")
        print(f"   File: {self.data_path.name}")
        print(f"   Format: {self.data_path.suffix}")
        print(f"   Parcels: {len(self.gdf):,}")
        print(f"   CRS: {self.gdf.crs}")
        
        # Spatial extent
        print(f"\n🌍 SPATIAL EXTENT:")
        print(f"   West:  {self.bounds['west']:.6f}° ({self._format_coordinate(self.bounds['west'], 'lon')})")
        print(f"   East:  {self.bounds['east']:.6f}° ({self._format_coordinate(self.bounds['east'], 'lon')})")
        print(f"   South: {self.bounds['south']:.6f}° ({self._format_coordinate(self.bounds['south'], 'lat')})")
        print(f"   North: {self.bounds['north']:.6f}° ({self._format_coordinate(self.bounds['north'], 'lat')})")
        
        # Coverage area
        area_deg = (self.bounds['east'] - self.bounds['west']) * (self.bounds['north'] - self.bounds['south'])
        approx_area_km = area_deg * 111 * 111  # Very rough approximation
        
        print(f"\n📏 COVERAGE AREA:")
        print(f"   Width:  {(self.bounds['east'] - self.bounds['west']):.4f}° (~{(self.bounds['east'] - self.bounds['west']) * 111:.0f} km)")
        print(f"   Height: {(self.bounds['north'] - self.bounds['south']):.4f}° (~{(self.bounds['north'] - self.bounds['south']) * 111:.0f} km)")
        print(f"   Approx area: ~{approx_area_km:,.0f} km²")
        
        # Map settings
        print(f"\n🎯 MAP SETTINGS:")
        print(f"   Center: {self.center['lat']:.6f}°, {self.center['lon']:.6f}°")
        print(f"   Recommended zoom: {self.zoom}")
    
    def _format_coordinate(self, coord, coord_type):
        """Format coordinate with cardinal direction"""
        if coord_type == 'lat':
            return f"{'N' if coord >= 0 else 'S'}"
        else:  # lon
            return f"{'E' if coord >= 0 else 'W'}"
    
    def generate_cdse_urls(self):
        """Generate CDSE browser URLs for water data"""
        print(f"\n🌊 CDSE BROWSER URLS FOR WATER DATA:")
        print("=" * 45)
        
        base_url = "https://browser.dataspace.copernicus.eu/?"
        
        # Common parameters
        common_params = [
            f"lat={self.center['lat']:.6f}",
            f"lng={self.center['lon']:.6f}",
            f"zoom={self.zoom}",
            "themeId=DEFAULT-THEME",
            "datasetId=COPERNICUS_CLMS_WB_100M_MONTHLY_V1",
            "layerId=WB",
            'demSource3D="MAPZEN"',
            "dateMode=TIME%20RANGE",
            "clmsSelectedCollection=COPERNICUS_CLMS_WB_100M_MONTHLY_V1"
        ]
        
        # Different time periods
        time_periods = [
            {
                'name': 'Recent 3 months',
                'from': '2025-06-01T00:00:00.000Z',
                'to': '2025-08-25T23:59:59.999Z'
            },
            {
                'name': 'Full 2025',
                'from': '2025-01-01T00:00:00.000Z', 
                'to': '2025-12-31T23:59:59.999Z'
            },
            {
                'name': 'Growing season 2025',
                'from': '2025-03-01T00:00:00.000Z',
                'to': '2025-09-30T23:59:59.999Z'
            }
        ]
        
        for period in time_periods:
            params = common_params + [
                f"fromTime={period['from']}",
                f"toTime={period['to']}"
            ]
            
            url = base_url + "&".join(params)
            print(f"\n📅 {period['name']}:")
            print(f"   {url}")
    
    def generate_leaflet_config(self):
        """Generate Leaflet map configuration"""
        print(f"\n🗺️  LEAFLET MAP CONFIGURATION:")
        print("=" * 35)
        
        config = {
            'bounds': self.bounds,
            'center': self.center,
            'zoom': self.zoom
        }
        
        print("\n📋 JavaScript configuration:")
        print("```javascript")
        print("// Map bounds and center from your agricultural data")
        print(f"const agriculturalBounds = {json.dumps(self.bounds, indent=2)};")
        print(f"const mapCenter = [{self.center['lat']:.6f}, {self.center['lon']:.6f}];")
        print(f"const recommendedZoom = {self.zoom};")
        print("")
        print("// Initialize map")
        print("var map = L.map('map').setView(mapCenter, recommendedZoom);")
        print("")
        print("// Or fit to exact bounds")
        print("var bounds = [")
        print(f"  [agriculturalBounds.south, agriculturalBounds.west],")
        print(f"  [agriculturalBounds.north, agriculturalBounds.east]")
        print("];")
        print("map.fitBounds(bounds);")
        print("```")
    
    def generate_flask_api(self):
        """Generate Flask API endpoint code"""
        print(f"\n⚡ FLASK API ENDPOINT (Optional):")
        print("=" * 35)
        
        print("\n📋 Add this to your Flask app if needed:")
        print("```python")
        print("@app.route('/api/map_bounds')")
        print("def get_map_bounds():")
        print('    """Return map bounds for your agricultural data"""')
        print("    return jsonify({")
        print(f"        'bounds': {json.dumps(self.bounds)},")
        print(f"        'center': {json.dumps(self.center)},")
        print(f"        'zoom': {self.zoom}")
        print("    })")
        print("```")
    
    def save_config_file(self):
        """Save configuration to a JSON file"""
        config_file = self.data_path.parent / f"{self.data_path.stem}_map_config.json"
        
        config = {
            'data_file': str(self.data_path),
            'parcel_count': len(self.gdf),
            'crs': str(self.gdf.crs),
            'bounds': self.bounds,
            'center': self.center,
            'zoom': self.zoom,
            'generated_at': pd.Timestamp.now().isoformat() if 'pd' in globals() else 'unknown'
        }
        
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            print(f"\n💾 Configuration saved to: {config_file}")
            print("   You can load this in your applications or scripts.")
            
        except Exception as e:
            print(f"⚠️  Could not save config file: {e}")
    
    def run_analysis(self):
        """Run complete analysis"""
        try:
            # Load and analyze data
            if not self.load_data():
                return False
                
            self.calculate_bounds()
            
            # Display all results
            self.display_summary()
            self.generate_cdse_urls()
            self.generate_leaflet_config() 
            self.generate_flask_api()
            
            # Save config
            self.save_config_file()
            
            print(f"\n🎉 Analysis complete!")
            print(f"✅ Use the CDSE URLs above to download water data for your region")
            print(f"✅ Use the Leaflet config in your web application")
            
            return True
            
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return False

def main():
    """Main function with command line interface"""
    print("🌾 Agricultural Data Bounds Analyzer")
    print("=" * 50)
    
    # Check command line arguments
    if len(sys.argv) != 2:
        print("\n❌ Usage: python analyze_agricultural_data.py <path_to_data_file>")
        print("\n📋 Examples:")
        print("   python analyze_agricultural_data.py my_parcels.gpkg")
        print("   python analyze_agricultural_data.py ../data/agriculture.shp")
        print("   python analyze_agricultural_data.py parcels.geojson")
        print("\n💡 Supported formats: .gpkg, .shp, .geojson, .gml")
        sys.exit(1)
    
    data_path = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(data_path):
        print(f"❌ File not found: {data_path}")
        sys.exit(1)
    
    # Run analysis
    analyzer = AgriculturalDataAnalyzer(data_path)
    success = analyzer.run_analysis()
    
    if success:
        print(f"\n🚀 Next steps:")
        print("   1. Use the CDSE URLs to download water data")
        print("   2. Update your web app with the Leaflet configuration")
        print("   3. Integrate water data using the coordinates provided")
        sys.exit(0)
    else:
        print(f"\n❌ Analysis failed. Check your data file and try again.")
        sys.exit(1)

if __name__ == "__main__":
    main()