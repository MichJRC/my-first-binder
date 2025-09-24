#!/usr/bin/env python3
"""
CSV Merge Test Script
Test the merge between GPKG and hcat3_EC_HRL_fixed.csv
Analyze match success and data quality
"""

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

def load_data():
    """Load the GPKG and CSV files"""
    print("🔄 Loading data...")
    
    # Load GPKG
    gdf = gpd.read_file("downloaded_data/merged_geodata.gpkg")
    print(f"   ✅ GPKG loaded: {len(gdf):,} parcels")
    
    # Load CSV
    csv_df = pd.read_csv("data/hcat3_EC_HRL_fixed.csv")
    print(f"   ✅ CSV loaded: {len(csv_df):,} classification entries")
    
    return gdf, csv_df

def test_merge(gdf, csv_df):
    """Perform the merge and return results"""
    print("\n🔗 Testing merge...")
    
    # Prepare HCAT2_Code for matching
    original_type = gdf['HCAT2_Code'].dtype
    print(f"   Original HCAT2_Code type: {original_type}")
    
    # Convert to integer, handling NaN values
    gdf_test = gdf.copy()
    gdf_test['HCAT2_Code'] = pd.to_numeric(gdf_test['HCAT2_Code'], errors='coerce').astype('Int64')
    
    print(f"   Converted HCAT2_Code type: {gdf_test['HCAT2_Code'].dtype}")
    print(f"   Non-null HCAT2_Code values: {gdf_test['HCAT2_Code'].notna().sum():,}")
    
    # Perform merge
    merged_gdf = gdf_test.merge(
        csv_df,
        left_on='HCAT2_Code',
        right_on='hcat3_code',
        how='left'
    )
    
    print(f"   ✅ Merge completed: {len(merged_gdf):,} rows")
    
    return merged_gdf

def analyze_match_success(original_gdf, merged_gdf, csv_df):
    """Comprehensive analysis of merge success"""
    print("\n" + "="*60)
    print("📊 MERGE SUCCESS ANALYSIS")
    print("="*60)
    
    # Basic match statistics
    total_parcels = len(merged_gdf)
    ec_matches = merged_gdf['ec_name'].notna().sum()
    hrl_matches = merged_gdf['hrl_name'].notna().sum()
    hcat3_matches = merged_gdf['hcat3_name'].notna().sum()
    
    print(f"\n📈 Overall Match Statistics:")
    print(f"   Total parcels: {total_parcels:,}")
    print(f"   EC matches: {ec_matches:,} ({ec_matches/total_parcels*100:.1f}%)")
    print(f"   HRL matches: {hrl_matches:,} ({hrl_matches/total_parcels*100:.1f}%)")
    print(f"   HCAT3 matches: {hcat3_matches:,} ({hcat3_matches/total_parcels*100:.1f}%)")
    
    # Analysis by HCAT2_Code
    print(f"\n🔍 Analysis by HCAT2_Code:")
    hcat_analysis = original_gdf.groupby('HCAT2_Code').agg({
        'gsa_par_id': 'count',
        'HCAT2_Name': 'first'
    }).rename(columns={'gsa_par_id': 'parcel_count'})
    
    # Add match info
    merge_success = merged_gdf.groupby('HCAT2_Code').agg({
        'ec_name': lambda x: x.notna().sum(),
        'hrl_name': lambda x: x.notna().sum(),
        'gsa_par_id': 'count'
    }).rename(columns={
        'ec_name': 'ec_matches',
        'hrl_name': 'hrl_matches',
        'gsa_par_id': 'total_parcels'
    })
    
    hcat_analysis = hcat_analysis.join(merge_success, how='left')
    hcat_analysis['ec_match_rate'] = (hcat_analysis['ec_matches'] / hcat_analysis['total_parcels'] * 100).fillna(0)
    hcat_analysis['hrl_match_rate'] = (hcat_analysis['hrl_matches'] / hcat_analysis['total_parcels'] * 100).fillna(0)
    
    # Show top categories by parcel count and their match rates
    print(f"\n📋 Top 15 HCAT2 Categories and Match Success:")
    print(f"{'HCAT2_Code':<15} {'HCAT2_Name':<35} {'Parcels':<8} {'EC%':<6} {'HRL%':<6}")
    print("-" * 75)
    
    top_categories = hcat_analysis.sort_values('parcel_count', ascending=False).head(15)
    for code, row in top_categories.iterrows():
        if pd.notna(code):
            name = str(row['HCAT2_Name'])[:32] + "..." if len(str(row['HCAT2_Name'])) > 35 else str(row['HCAT2_Name'])
            print(f"{int(code):<15,} {name:<35} {int(row['parcel_count']):<8,} {row['ec_match_rate']:<6.1f} {row['hrl_match_rate']:<6.1f}")
    
    # Identify unmatched categories
    unmatched = hcat_analysis[hcat_analysis['ec_match_rate'] == 0].sort_values('parcel_count', ascending=False)
    print(f"\n❌ Unmatched HCAT2 Categories ({len(unmatched)} total):")
    if len(unmatched) > 0:
        print(f"{'HCAT2_Code':<15} {'HCAT2_Name':<35} {'Affected Parcels':<15}")
        print("-" * 65)
        for code, row in unmatched.head(10).iterrows():
            if pd.notna(code):
                name = str(row['HCAT2_Name'])[:32] + "..." if len(str(row['HCAT2_Name'])) > 35 else str(row['HCAT2_Name'])
                print(f"{int(code):<15,} {name:<35} {int(row['parcel_count']):<15,}")
        
        total_unmatched_parcels = unmatched['parcel_count'].sum()
        print(f"\n   Total unmatched parcels: {total_unmatched_parcels:,} ({total_unmatched_parcels/total_parcels*100:.2f}%)")
    
    return hcat_analysis

def analyze_new_categories(merged_gdf):
    """Analyze the new classification categories"""
    print(f"\n" + "="*60)
    print("🎨 NEW CLASSIFICATION CATEGORIES")
    print("="*60)
    
    # EC Categories analysis
    ec_categories = merged_gdf[merged_gdf['ec_name'].notna()]
    if len(ec_categories) > 0:
        ec_stats = ec_categories.groupby('ec_name').agg({
            'gsa_par_id': 'count',
            'ec_code': 'first'
        }).rename(columns={'gsa_par_id': 'parcel_count'}).sort_values('parcel_count', ascending=False)
        
        print(f"\n📊 EC (European Commission) Categories ({len(ec_stats)} total):")
        print(f"{'EC Code':<8} {'EC Name':<35} {'Parcels':<10} {'%':<6}")
        print("-" * 65)
        
        total_with_ec = len(ec_categories)
        for name, row in ec_stats.head(15).iterrows():
            percentage = row['parcel_count'] / total_with_ec * 100
            ec_code = int(row['ec_code']) if pd.notna(row['ec_code']) else 'N/A'
            name_display = name[:32] + "..." if len(name) > 35 else name
            print(f"{ec_code:<8} {name_display:<35} {row['parcel_count']:<10,} {percentage:<6.1f}")
    
    # HRL Categories analysis
    hrl_categories = merged_gdf[merged_gdf['hrl_name'].notna()]
    if len(hrl_categories) > 0:
        hrl_stats = hrl_categories.groupby('hrl_name').agg({
            'gsa_par_id': 'count',
            'hrl_code': 'first'
        }).rename(columns={'gsa_par_id': 'parcel_count'}).sort_values('parcel_count', ascending=False)
        
        print(f"\n🛰️  HRL (High Resolution Layer) Categories ({len(hrl_stats)} total):")
        print(f"{'HRL Code':<8} {'HRL Name':<35} {'Parcels':<10} {'%':<6}")
        print("-" * 65)
        
        total_with_hrl = len(hrl_categories)
        for name, row in hrl_stats.head(15).iterrows():
            percentage = row['parcel_count'] / total_with_hrl * 100
            hrl_code = int(row['hrl_code']) if pd.notna(row['hrl_code']) else 'N/A'
            name_display = name[:32] + "..." if len(name) > 35 else name
            print(f"{hrl_code:<8} {name_display:<35} {row['parcel_count']:<10,} {percentage:<6.1f}")

def check_data_quality(original_gdf, merged_gdf):
    """Check data quality and integrity"""
    print(f"\n" + "="*60)
    print("🔍 DATA QUALITY CHECK")
    print("="*60)
    
    # Check for data loss
    print(f"\n📊 Data Integrity:")
    print(f"   Original rows: {len(original_gdf):,}")
    print(f"   Merged rows: {len(merged_gdf):,}")
    print(f"   Row change: {len(merged_gdf) - len(original_gdf):,}")
    
    # Check for duplicates
    original_unique = original_gdf['gsa_par_id'].nunique()
    merged_unique = merged_gdf['gsa_par_id'].nunique()
    print(f"   Original unique parcels: {original_unique:,}")
    print(f"   Merged unique parcels: {merged_unique:,}")
    
    # Memory usage
    original_memory = original_gdf.memory_usage(deep=True).sum() / 1024 / 1024
    merged_memory = merged_gdf.memory_usage(deep=True).sum() / 1024 / 1024
    print(f"\n💾 Memory Usage:")
    print(f"   Original GPKG: {original_memory:.1f} MB")
    print(f"   After merge: {merged_memory:.1f} MB")
    print(f"   Increase: +{merged_memory - original_memory:.1f} MB ({(merged_memory/original_memory-1)*100:.1f}%)")
    
    # Column analysis
    original_cols = len(original_gdf.columns)
    merged_cols = len(merged_gdf.columns)
    new_cols = merged_cols - original_cols
    print(f"\n📋 Column Analysis:")
    print(f"   Original columns: {original_cols}")
    print(f"   After merge: {merged_cols}")
    print(f"   New columns added: {new_cols}")
    
    # Show new column names
    if new_cols > 0:
        original_col_set = set(original_gdf.columns)
        new_column_names = [col for col in merged_gdf.columns if col not in original_col_set]
        print(f"   New columns: {new_column_names}")

def create_summary_files(merged_gdf, hcat_analysis):
    """Create summary CSV files for analysis"""
    print(f"\n💾 Creating summary files...")
    
    # Create output directory
    Path("merge_analysis").mkdir(exist_ok=True)
    
    # 1. Match success by HCAT category
    hcat_analysis.to_csv("merge_analysis/hcat_match_analysis.csv")
    print("   ✅ merge_analysis/hcat_match_analysis.csv")
    
    # 2. EC categories summary
    ec_summary = merged_gdf[merged_gdf['ec_name'].notna()].groupby(['ec_code', 'ec_name']).size().reset_index(name='parcel_count')
    ec_summary.to_csv("merge_analysis/ec_categories_summary.csv", index=False)
    print("   ✅ merge_analysis/ec_categories_summary.csv")
    
    # 3. HRL categories summary
    hrl_summary = merged_gdf[merged_gdf['hrl_name'].notna()].groupby(['hrl_code', 'hrl_name']).size().reset_index(name='parcel_count')
    hrl_summary.to_csv("merge_analysis/hrl_categories_summary.csv", index=False)
    print("   ✅ merge_analysis/hrl_categories_summary.csv")
    
    # 4. Unmatched parcels for investigation
    unmatched = merged_gdf[merged_gdf['ec_name'].isna()][['gsa_par_id', 'HCAT2_Code', 'HCAT2_Name', 'Italian_Name', 'English_Name']]
    unmatched.to_csv("merge_analysis/unmatched_parcels.csv", index=False)
    print("   ✅ merge_analysis/unmatched_parcels.csv")
    
    # 5. Sample of successfully merged data
    sample_merged = merged_gdf[merged_gdf['ec_name'].notna()].sample(min(1000, len(merged_gdf[merged_gdf['ec_name'].notna()]))).drop('geometry', axis=1)
    sample_merged.to_csv("merge_analysis/sample_merged_data.csv", index=False)
    print("   ✅ merge_analysis/sample_merged_data.csv")

def print_conclusion(merged_gdf):
    """Print final conclusions and recommendations"""
    print(f"\n" + "="*60)
    print("🎯 CONCLUSION & RECOMMENDATIONS")
    print("="*60)
    
    total_parcels = len(merged_gdf)
    ec_success_rate = merged_gdf['ec_name'].notna().mean() * 100
    hrl_success_rate = merged_gdf['hrl_name'].notna().mean() * 100
    
    print(f"\n📊 Overall Success:")
    print(f"   EC category match: {ec_success_rate:.1f}%")
    print(f"   HRL category match: {hrl_success_rate:.1f}%")
    
    if ec_success_rate >= 90:
        print("   ✅ EXCELLENT match rate - proceed with integration!")
    elif ec_success_rate >= 75:
        print("   ✅ GOOD match rate - acceptable for integration")
    elif ec_success_rate >= 60:
        print("   ⚠️  MODERATE match rate - investigate unmatched categories")
    else:
        print("   ❌ LOW match rate - review HCAT2_Code formatting or CSV data")
    
    print(f"\n💡 Next Steps:")
    if ec_success_rate >= 75:
        print("   1. ✅ Integration recommended")
        print("   2. 📝 Review merge_analysis/ files for insights")
        print("   3. 🔄 Update your GPKG creation script")
        print("   4. 🧪 Test visualization with new EC/HRL categories")
    else:
        print("   1. 🔍 Investigate unmatched categories in merge_analysis/")
        print("   2. 🔧 Consider HCAT2_Code data cleaning")
        print("   3. 📞 Verify CSV data completeness")
        print("   4. 🔄 Re-run test after fixes")

def main():
    """Main test function"""
    print("🧪 CSV MERGE TEST & ANALYSIS")
    print("=" * 40)
    
    try:
        # Load data
        gdf, csv_df = load_data()
        
        # Test merge
        merged_gdf = test_merge(gdf, csv_df)
        
        # Analyze results
        hcat_analysis = analyze_match_success(gdf, merged_gdf, csv_df)
        analyze_new_categories(merged_gdf)
        check_data_quality(gdf, merged_gdf)
        
        # Create summary files
        create_summary_files(merged_gdf, hcat_analysis)
        
        # Final conclusion
        print_conclusion(merged_gdf)
        
        print(f"\n✅ Test completed successfully!")
        print(f"📁 Check merge_analysis/ folder for detailed results")
        
    except Exception as e:
        print(f"❌ Error during testing: {str(e)}")
        print(f"Error type: {type(e).__name__}")
        raise

if __name__ == "__main__":
    main()