import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

LEVEL_LABEL = {0: "โล่ง", 1: "คล่องตัว", 2: "ปานกลาง", 3: "หนาแน่น", 4: "ติดขัด", 5: "ถนนปิด"}
LEVEL_COLOR = {0: "#2ea043", 1: "#2ea043", 2: "#e6b41e", 3: "#f0781e", 4: "#d22828", 5: "#6e0f0f"}


@st.cache_resource
def engine():
    return create_engine(os.getenv("TRAFFIC_DB_URL", "postgresql+psycopg2://traffic:traffic@localhost:5432/traffic"))


@st.cache_data(ttl=30)
def query(sql, **params):
    """อ่านข้อมูลจาก PostgreSQL โดยตรง"""
    return pd.read_sql_query(sql, engine(), params=params or None)
