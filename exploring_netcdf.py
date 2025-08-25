import rasterio
import numpy as np

# Open the downloaded file
with rasterio.open('c_gls_WB100_202506010000_GLOBE_S2_V1.0.1.nc') as src:
    print("Shape:", src.shape)
    print("CRS:", src.crs)
    print("Bounds:", src.bounds)