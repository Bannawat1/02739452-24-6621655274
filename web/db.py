import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine


@st.cache_resource
def engine():
    return create_engine(os.getenv("TRAFFIC_DB_URL", "postgresql+psycopg2://traffic:traffic@localhost:5432/traffic"))


@st.cache_data(ttl=30)
def query(sql, **params):
    """อ่านข้อมูลจาก PostgreSQL โดยตรง"""
    return pd.read_sql_query(sql, engine(), params=params or None)
