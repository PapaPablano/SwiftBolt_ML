#!/usr/bin/env python3
import pandas as pd
import glob

# Find the NVDA file
nvda_files = glob.glob('*NVDA*.csv')
if not nvda_files:
    print("No NVDA file found")
    exit(1)

# Read the NVDA file
df = pd.read_csv(nvda_files[0])
df['time'] = pd.to_datetime(df['time'])

# Filter for October 2025
oct_data = df[(df['time'].dt.year == 2025) & (df['time'].dt.month == 10)]

print("NVDA October 2025 Data:")
print("=" * 80)
print(oct_data[['time', 'open', 'high', 'low', 'close']].to_string(index=False))
print("\n")

# Check October 1, 2025 specifically
oct1 = df[df['time'].dt.date == pd.Timestamp('2025-10-01').date()]
if not oct1.empty:
    print("October 1, 2025 Data:")
    print(oct1[['time', 'open', 'high', 'low', 'close']].to_string(index=False))
else:
    print("No data found for October 1, 2025")
