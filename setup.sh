#!/bin/bash
mkdir -p downloaded_data

# Your existing data
wget -q -O downloaded_data/GSA2024LB.zip https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/GSA2024LB.zip
cd downloaded_data && unzip -q GSA2024LB.zip && cd ..

# Your new GeoPackage
echo "Downloading merged geodata..."
wget -q -O downloaded_data/merged_geodata.gpkg https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/merged_geodata.gpkg

echo "Data setup complete!"
