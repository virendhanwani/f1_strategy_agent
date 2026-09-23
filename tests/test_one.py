import pandas as pd
laps = pd.read_parquet("data/processed/2023_Monaco_R_laps.parquet")
print(laps.columns.tolist())
print(laps[["Driver", "LapNumber", "LapTime", "Compound", "TyreLife"]].head(10))