import pandas as pd

print("reading the csv")
classes = pd.read_csv("data/hcat3_EC_HRL.csv", sep=",", header=0, encoding='utf-8')

print(classes.info)

classes.head()
print(hcatclasses)