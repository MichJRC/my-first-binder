import pandas as pd

print("reading the csv")
classes = pd.read_csv("data/hcat3_EC_HRL.csv", sep=",", header=0, encoding='utf-8',quoting=1,skipinitialspace=True,engine='python')

print(classes.info)

classes.head()

classes.columns
uniqueHCAT = classes["hcat3_code"].unique()

for hcat in uniqueHCAT:
    print(hcat)


import re

# Read the file as text first
with open('data/hcat3_EC_HRL.csv', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the problematic quoting pattern
# Remove the outer quotes from entire rows and fix inner quotes
fixed_content = re.sub(r'^"([^"]*(?:""[^"]*)*)"$', r'\1', content, flags=re.MULTILINE)
fixed_content = fixed_content.replace('""', '"')

# Write to a new file
with open('data/hcat3_EC_HRL_fixed.csv', 'w', encoding='utf-8') as f:
    f.write(fixed_content)

# Now read the fixed file
df = pd.read_csv('data/hcat3_EC_HRL_fixed.csv')

hcat_name = df["hcat3_name"].unique()

df.columns

for i in hcat_name:
    print(i)