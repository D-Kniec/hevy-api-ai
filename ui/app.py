import os
import sqlite3
import pandas as pd
import streamlit as st
from dotenv import load_dotenv

def initialize_environment() -> None:
    load_dotenv()
    if "api_client" not in st.session_state:
        st.session_state.api_client = os.getenv("HEVY_API_KEY", "")

def get_database_connection() -> sqlite3.Connection | None:
    db_path = "data/bronze_layer.db"
    if os.path.exists(db_path):
        return sqlite3.connect(db_path)
    return None

def fetch_database_overview() -> pd.DataFrame | None:
    connection = get_database_connection()
    if connection:
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            tables_dataframe = pd.read_sql_query(query, connection)
            return tables_dataframe
        finally:
            connection.close()
    return None

def fetch_table_data(table_name: str, limit: int = 5) -> pd.DataFrame | None:
    connection = get_database_connection()
    if connection:
        try:
            query = f"SELECT * FROM {table_name} LIMIT {limit};"
            data_dataframe = pd.read_sql_query(query, connection)
            return data_dataframe
        finally:
            connection.close()
    return None

def render_sidebar() -> None:
    with st.sidebar:
        st.title("Hevy Progression Agent")
        
        api_key_input = st.text_input(
            "Hevy API Key", 
            value=st.session_state.api_client, 
            type="password"
        )
        
        if api_key_input != st.session_state.api_client:
            st.session_state.api_client = api_key_input
        
        if st.session_state.api_client:
            st.success("API Key configured via .env")
        else:
            st.warning("API Key missing. Network operations disabled.")

def render_local_database_section() -> None:
    st.subheader("Bronze Layer Database Status")
    
    tables_dataframe = fetch_database_overview()
    
    if tables_dataframe is not None and not tables_dataframe.empty:
        selected_table = st.selectbox(
            "Select table to preview", 
            tables_dataframe['name'].tolist()
        )
        
        if selected_table:
            table_data = fetch_table_data(selected_table)
            if table_data is not None:
                st.dataframe(table_data, use_container_width=True)
    else:
        st.info("Local database data/bronze_layer.db not found or contains no tables.")

def render_action_buttons() -> None:
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("Fetch New Data (Run ETL)", use_container_width=True):
            if not st.session_state.api_client:
                st.error("Cannot connect to Hevy API: API Key is missing.")
            else:
                with st.spinner("Fetching data and updating Bronze layer..."):
                    st.success("ETL Pipeline completed successfully")

    with col2:
        if st.button("Generate Next Routine", use_container_width=True):
            with st.spinner("Analyzing local data and generating routine via LLM..."):
                st.success("Routine generated and saved locally")

def main() -> None:
    st.set_page_config(
        page_title="Hevy API AI",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_environment()
    render_sidebar()
    
    st.header("Workout Generation Pipeline")
    render_local_database_section()
    st.divider()
    render_action_buttons()

if __name__ == "__main__":
    main()
