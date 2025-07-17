#!/bin/bash
mkdir -p data
wget -q -O data/GSA2024LB.zip https://github.com/MichJRC/my-first-binder/releases/download/v1.0.0/GSA2024LB.zip
cd data && unzip -q GSA2024LB.zip && cd ..
echo "Data setup complete!"
