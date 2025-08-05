# Add these imports to your Flask app
import rasterio
from rasterio.warp import transform_bounds, reproject, Resampling
from rasterio.windows import from_bounds
import io
from PIL import Image
import numpy as np

# Global variable for TIF data
tif_dataset = None

def load_tif_data(tif_path):
    """
    Load TIF file for serving
    """
    global tif_dataset
    
    print(f"🌍 Loading TIF file: {tif_path}")
    tif_dataset = rasterio.open(tif_path)
    print(f"✅ TIF loaded: {tif_dataset.width}x{tif_dataset.height}, CRS: {tif_dataset.crs}")
    
    # Reproject bounds to Web Mercator if needed
    if tif_dataset.crs.to_epsg() != 3857:
        bounds = transform_bounds(tif_dataset.crs, 'EPSG:3857', *tif_dataset.bounds)
        print(f"📍 TIF bounds (Web Mercator): {bounds}")

def deg2num(lat_deg, lon_deg, zoom):
    """
    Convert lat/lon to tile numbers
    """
    import math
    lat_rad = math.radians(lat_deg)
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return (xtile, ytile)

def num2deg(xtile, ytile, zoom):
    """
    Convert tile numbers to lat/lon bounds
    """
    import math
    n = 2.0 ** zoom
    lon_deg_left = xtile / n * 360.0 - 180.0
    lon_deg_right = (xtile + 1) / n * 360.0 - 180.0
    lat_rad_top = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
    lat_rad_bottom = math.atan(math.sinh(math.pi * (1 - 2 * (ytile + 1) / n)))
    lat_deg_top = math.degrees(lat_rad_top)
    lat_deg_bottom = math.degrees(lat_rad_bottom)
    return (lon_deg_left, lat_deg_bottom, lon_deg_right, lat_deg_top)

@app.route('/tif_tiles/<int:z>/<int:x>/<int:y>.png')
def serve_tif_tile(z, x, y):
    """
    Dynamically generate TIF tiles
    """
    if tif_dataset is None:
        abort(404)
    
    try:
        # Get tile bounds in lat/lon
        west, south, east, north = num2deg(x, y, z)
        
        # Check if tile intersects with TIF bounds
        tif_bounds = tif_dataset.bounds
        if tif_dataset.crs.to_epsg() != 4326:
            tif_bounds = transform_bounds(tif_dataset.crs, 'EPSG:4326', *tif_bounds)
        
        # If no intersection, return transparent tile
        if (east < tif_bounds[0] or west > tif_bounds[2] or 
            north < tif_bounds[1] or south > tif_bounds[3]):
            # Return transparent 256x256 PNG
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
            img_io = io.BytesIO()
            img.save(img_io, 'PNG')
            img_io.seek(0)
            return send_file(img_io, mimetype='image/png')
        
        # Read data from TIF for this tile area
        if tif_dataset.crs.to_epsg() != 4326:
            # Transform bounds to TIF CRS
            west, south, east, north = transform_bounds('EPSG:4326', tif_dataset.crs, west, south, east, north)
        
        # Create window for this area
        window = from_bounds(west, south, east, north, tif_dataset.transform)
        
        # Read data
        data = tif_dataset.read(1, window=window, out_shape=(256, 256))
        
        # Convert to image
        if data.dtype != np.uint8:
            # Normalize to 0-255 range
            data_min, data_max = np.nanmin(data), np.nanmax(data)
            if data_max > data_min:
                data = ((data - data_min) / (data_max - data_min) * 255).astype(np.uint8)
            else:
                data = np.zeros_like(data, dtype=np.uint8)
        
        # Create PIL image
        img = Image.fromarray(data, mode='L')  # Grayscale
        
        # Convert to RGB if you want to apply colormap
        img = img.convert('RGB')
        
        # Save to bytes
        img_io = io.BytesIO()
        img.save(img_io, 'PNG')
        img_io.seek(0)
        
        return send_file(img_io, mimetype='image/png')
        
    except Exception as e:
        print(f"Error serving TIF tile {z}/{x}/{y}: {e}")
        abort(404)

# Add this to your main section:
if __name__ == '__main__':
    GPKG_FILE = "your_file.gpkg"
    TIF_FILE = "your_file.tif"  # Add your TIF file path
    
    try:
        load_data(GPKG_FILE)
        load_tif_data(TIF_FILE)  # Load TIF data
        
        print(f"✅ Ready to serve!")
        # ... rest of your startup code
    except Exception as e:
        print(f"❌ Error: {e}")