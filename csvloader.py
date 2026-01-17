import pandas as pd
from sqlalchemy import create_engine
import sqlite3

enrollment = "./static_data/medicaid_enrollment.csv"

df = pd.read_csv(enrollment)

engine = create_engine("sqlite:///drugs_data.db")

with engine.connect() as conn:
    df.to_sql("enrollment", con = conn, if_exists="replace")
