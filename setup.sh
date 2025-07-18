#!/bin/bash
mkdir -p downloaded_data
wget -q -O downloaded_data/GSA2024LB.zip https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/GSA2024LB.zip
cd downloaded_data && unzip -q GSA2024LB.zip && cd ..
echo "Data setup complete!"
