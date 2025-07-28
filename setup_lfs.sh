#!/bin/bash

# Setup Git LFS for large geodata files
echo "Setting up Git LFS..."

# Initialize git-lfs
git lfs install

# Track the large geodata file
echo "Tracking large geodata file..."
git lfs track "data/merged_geodata.gpkg"

# Add the .gitattributes file
echo "Adding .gitattributes..."
git add .gitattributes

# Add the large geodata file
echo "Adding geodata file..."
git add data/merged_geodata.gpkg

# Commit the changes
echo "Committing changes..."
git commit -m "Add large geodata file with LFS tracking"

# Push to remote
echo "Pushing to GitHub..."
git push origin main

echo "large file should now store with Git LFS."