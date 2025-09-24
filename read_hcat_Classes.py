#!/usr/bin/env python3
"""
Extract and Display HCAT2 Categories from GPKG File
Simple script to see what crop types are in data
"""

import geopandas as gpd
import pandas as pd
from pathlib import Path

def analyze_hcat_categories(gpkg_path):
    """
    Extract and analyze HCAT2 categories from your GPKG file
    """
    
    print("🌾 Analyzing HCAT Categories in Your Data")
    print("=" * 60)
    
    try:
        # Load the GPKG file
        print(f"📂 Loading: {gpkg_path}")
        gdf = gpd.read_file(gpkg_path)
        print(f"   ✅ Loaded {len(gdf):,} records")
        
        # Show basic info about the file
        print(f"\n📊 Dataset Info:")
        print(f"   Total parcels: {len(gdf):,}")
        print(f"   Columns: {list(gdf.columns)}")
        print(f"   CRS: {gdf.crs}")
        
        # Check if HCAT2 columns exist
        hcat_columns = [col for col in gdf.columns if 'HCAT' in col.upper()]
        print(f"\n🔍 HCAT-related columns found: {hcat_columns}")
        
        if not hcat_columns:
            print("   ❌ No HCAT columns found!")
            return
        
        # Analyze HCAT2_Code and HCAT2_Name if they exist
        results = {}
        
        if 'HCAT2_Code' in gdf.columns:
            print(f"\n📋 HCAT2_Code Analysis:")
            hcat2_codes = gdf['HCAT2_Code'].dropna()
            print(f"   Non-null codes: {len(hcat2_codes):,}")
            print(f"   Unique codes: {hcat2_codes.nunique():,}")
            
            # Show top 20 HCAT2 codes
            top_codes = hcat2_codes.value_counts().head(20)
            print(f"\n   📈 Top 20 HCAT2_Code values:")
            for code, count in top_codes.items():
                percentage = count / len(hcat2_codes) * 100
                print(f"      {int(code):>12,} : {count:>6,} parcels ({percentage:>5.1f}%)")
            
            results['codes'] = top_codes
        
        if 'HCAT2_Name' in gdf.columns:
            print(f"\n📋 HCAT2_Name (Categories) Analysis:")
            hcat2_names = gdf['HCAT2_Name'].dropna()
            print(f"   Non-null names: {len(hcat2_names):,}")
            print(f"   Unique categories: {hcat2_names.nunique():,}")
            
            # Show all unique HCAT2 categories
            top_names = hcat2_names.value_counts()
            print(f"\n   🌾 ALL Your HCAT2 Categories ({len(top_names)} total):")
            print(f"   {'Rank':<4} {'Count':<8} {'%':<6} {'HCAT2_Name':<50}")
            print(f"   {'-'*4} {'-'*8} {'-'*6} {'-'*50}")
            
            for rank, (name, count) in enumerate(top_names.items(), 1):
                percentage = count / len(hcat2_names) * 100
                name_display = name[:47] + "..." if len(name) > 50 else name
                print(f"   {rank:<4} {count:<8,} {percentage:<6.1f}% {name_display}")
            
            results['names'] = top_names
        
        # Create code-to-name mapping if both exist
        if 'HCAT2_Code' in gdf.columns and 'HCAT2_Name' in gdf.columns:
            print(f"\n🔗 HCAT2 Code-to-Name Mapping:")
            mapping_df = gdf[['HCAT2_Code', 'HCAT2_Name']].dropna().drop_duplicates()
            mapping = dict(zip(mapping_df['HCAT2_Code'].astype(int), mapping_df['HCAT2_Name']))
            
            print(f"   Total unique code-name pairs: {len(mapping):,}")
            print(f"\n   📋 Sample Mappings (showing first 20):")
            print(f"   {'HCAT2_Code':<15} {'HCAT2_Name':<50}")
            print(f"   {'-'*15} {'-'*50}")
            
            for i, (code, name) in enumerate(list(mapping.items())[:20]):
                name_display = name[:47] + "..." if len(name) > 50 else name
                print(f"   {code:<15,} {name_display}")
            
            if len(mapping) > 20:
                print(f"   ... and {len(mapping) - 20} more mappings")
            
            results['mapping'] = mapping
        
        # Check for other relevant columns
        other_crop_columns = [col for col in gdf.columns if any(word in col.lower() 
                             for word in ['crop', 'english', 'italian', 'name']) 
                             and 'hcat' not in col.lower()]
        
        if other_crop_columns:
            print(f"\n🌱 Other Crop-related Columns:")
            for col in other_crop_columns[:5]:  # Show first 5
                unique_vals = gdf[col].dropna().nunique()
                print(f"   {col}: {unique_vals:,} unique values")
                
                # Show top 5 values for this column
                if unique_vals > 0 and unique_vals < 100:  # Only if reasonable number
                    top_vals = gdf[col].value_counts().head(5)
                    print(f"      Top values: {list(top_vals.index)}")
        
        print(f"\n" + "=" * 60)
        print("✅ Analysis Complete!")
        
        # Save results to CSV for reference
        if 'names' in results:
            output_file = "hcat2_categories.csv"
            results['names'].to_csv(output_file, header=['Count'])
            print(f"💾 HCAT2 categories saved to: {output_file}")
        
        if 'mapping' in results:
            mapping_file = "hcat2_code_name_mapping.csv"
            mapping_df = pd.DataFrame(list(results['mapping'].items()), 
                                    columns=['HCAT2_Code', 'HCAT2_Name'])
            mapping_df.to_csv(mapping_file, index=False)
            print(f"💾 HCAT2 code-name mapping saved to: {mapping_file}")
        
        return results
        
    except FileNotFoundError:
        print(f"❌ File not found: {gpkg_path}")
        print("   Please check the file path and make sure the file exists.")
        return None
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return None

def main():
    """
    Main function - update the path to GPKG file
    """
    
    # 👇 PATH TO GPKG FILE
    GPKG_FILE = "downloaded_data/merged_geodata.gpkg"
    
    # Check if file exists
    if not Path(GPKG_FILE).exists():
        print(f"❌ File not found: {GPKG_FILE}")
        print("\n📁 Please update GPKG_FILE path in the script to point to your file.")
        print("   Common locations:")
        print("   • downloaded_data/merged_geodata.gpkg")
        print("   • data/merged_geodata.gpkg") 
        print("   • /path/to/your/merged_geodata.gpkg")
        return
    
    # Analyze the data
    results = analyze_hcat_categories(GPKG_FILE)
    
    if results:
        print(f"\n💡 Next Steps:")
        print("1. Review your HCAT2 categories above")
        print("2. Compare with JRC EuroCropMap categories:")
        print("   • Common wheat, Barley, Maize, Rice, etc.")
        print("3. Run the mapping tool to create connections:")
        print("   python jrc_hcat_mapping_tool.py")

if __name__ == "__main__":
    main()