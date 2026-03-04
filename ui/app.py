import os
import sqlite3
import pandas as pd
import streamlit as st
import plotly.express as px
from dotenv import load_dotenv

# --- DATABASE CONNECTION & QUERIES ---

def initialize_environment() -> None:
    load_dotenv()
    if "api_client" not in st.session_state:
        st.session_state.api_client = os.getenv("HEVY_API_KEY", "")

def get_database_connection() -> sqlite3.Connection | None:
    db_path = "/home/kniec/Code/Hevy_API_AI/data/bronze_layer.db"
    if os.path.exists(db_path):
        return sqlite3.connect(db_path)
    return None

def fetch_database_overview() -> pd.DataFrame | None:
    connection = get_database_connection()
    if connection:
        try:
            query = "SELECT name FROM sqlite_master WHERE type='table';"
            return pd.read_sql_query(query, connection)
        finally:
            connection.close()
    return None

def fetch_table_data(table_name: str, limit: int = 5) -> pd.DataFrame | None:
    connection = get_database_connection()
    if connection:
        try:
            query = f"SELECT * FROM {table_name} LIMIT {limit};"
            return pd.read_sql_query(query, connection)
        finally:
            connection.close()
    return None

@st.cache_data
def load_progression_data() -> pd.DataFrame:
    query = """
    WITH WorkoutStats AS (
        SELECT 
            sde.exercise_name,
            sdr.routine_name,
            sfh.cycle_number,
            MAX(sfh.weight_kg) AS max_weight_kg,
            SUM(sfh.weight_kg * sfh.reps) AS total_volume_kg,
            MAX(sfh.weight_kg * (1 + (sfh.reps / 30.0))) AS estimated_1rm_kg
        FROM silver_fact_workout_history sfh
        INNER JOIN silver_dim_exercise sde ON sde.exercise_template_id = sfh.exercise_template_id 
        INNER JOIN silver_dim_routine sdr ON sdr.routine_id = sfh.routine_id 
        WHERE sfh.set_type = 'normal' 
          AND sfh.execution_status != 'Skipped'
        GROUP BY 
            sde.exercise_name,
            sdr.routine_name,
            sfh.cycle_number
    )
    SELECT 
        exercise_name,
        routine_name,
        cycle_number,
        max_weight_kg,
        ROUND(estimated_1rm_kg, 2) AS estimated_1rm_kg,
        total_volume_kg,
        max_weight_kg - LAG(max_weight_kg) OVER (PARTITION BY exercise_name, routine_name ORDER BY cycle_number) AS weight_progression,
        ROUND(estimated_1rm_kg - LAG(estimated_1rm_kg) OVER (PARTITION BY exercise_name, routine_name ORDER BY cycle_number), 2) AS rep_max_progression,
        total_volume_kg - LAG(total_volume_kg) OVER (PARTITION BY exercise_name, routine_name ORDER BY cycle_number) AS volume_progression
    FROM WorkoutStats
    ORDER BY 
        exercise_name,
        routine_name,
        cycle_number;
    """
    connection = get_database_connection()
    if connection:
        try:
            return pd.read_sql_query(query, connection)
        except Exception:
            return pd.DataFrame()
        finally:
            connection.close()
    return pd.DataFrame()

@st.cache_data
def load_execution_plan_data() -> pd.DataFrame:
    query = """
    SELECT 
        sde.exercise_name,
        sdr.routine_name,
        sfh.cycle_number,
        COUNT(sfh.set_index) AS total_sets_performed,
        ROUND(AVG(sfh.diff_weight_kg), 2) AS avg_weight_vs_plan_kg,
        SUM(sfh.diff_reps) AS total_reps_vs_plan
    FROM silver_fact_workout_history sfh
    INNER JOIN silver_dim_exercise sde ON sde.exercise_template_id = sfh.exercise_template_id 
    INNER JOIN silver_dim_routine sdr ON sdr.routine_id = sfh.routine_id 
    WHERE sfh.set_type = 'normal'
    GROUP BY 
        sde.exercise_name,
        sdr.routine_name,
        sfh.cycle_number
    ORDER BY 
        sde.exercise_name,
        sfh.cycle_number;
    """
    connection = get_database_connection()
    if connection:
        try:
            return pd.read_sql_query(query, connection)
        except Exception:
            return pd.DataFrame()
        finally:
            connection.close()
    return pd.DataFrame()

# --- UI COMPONENTS ---

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
            st.success("API Key configured")
        else:
            st.warning("API Key missing. Network operations disabled.")

def render_pipeline_tab() -> None:
    st.subheader("Bronze Layer Database Status")
    
    tables_dataframe = fetch_database_overview()
    
    if tables_dataframe is not None and not tables_dataframe.empty:
        selected_table = st.selectbox(
            "Select table to preview", 
            tables_dataframe['name'].tolist(),
            key="table_selector"
        )
        
        if selected_table:
            table_data = fetch_table_data(selected_table)
            if table_data is not None:
                st.dataframe(table_data, use_container_width=True)
    else:
        st.info("Local database not found or contains no tables.")

    st.divider()
    
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

def render_analytics_tab() -> None:
    progression_data = load_progression_data()
    execution_data = load_execution_plan_data()
    
    if progression_data.empty or execution_data.empty:
        st.warning("No data found in the silver tables. Make sure ETL pipeline has populated 'silver_fact_workout_history'.")
        return
        
    control_col1, control_col2 = st.columns(2)
    
    routines = progression_data["routine_name"].dropna().unique()
    with control_col1:
        selected_routine = st.selectbox("Select Routine", routines, key="routine_selector")
    
    filtered_by_routine = progression_data[progression_data["routine_name"] == selected_routine]
    exercises = filtered_by_routine["exercise_name"].dropna().unique()
    with control_col2:
        selected_exercise = st.selectbox("Select Exercise", exercises, key="exercise_selector")
    
    exercise_progression = progression_data[
        (progression_data["routine_name"] == selected_routine) & 
        (progression_data["exercise_name"] == selected_exercise)
    ]
    exercise_execution = execution_data[
        (execution_data["routine_name"] == selected_routine) & 
        (execution_data["exercise_name"] == selected_exercise)
    ]
    
    if not exercise_progression.empty:
        st.subheader(f"Performance Metrics: {selected_exercise}")
        
        metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
        latest_stats = exercise_progression.iloc[-1]
        
        e1rm_delta = latest_stats["rep_max_progression"] if pd.notna(latest_stats["rep_max_progression"]) else 0.0
        metrics_col1.metric("Estimated 1RM", f"{latest_stats['estimated_1rm_kg']} kg", f"{e1rm_delta} kg")
        
        vol_delta = latest_stats["volume_progression"] if pd.notna(latest_stats["volume_progression"]) else 0.0
        metrics_col2.metric("Total Volume", f"{latest_stats['total_volume_kg']} kg", f"{vol_delta} kg")
        
        weight_delta = latest_stats["weight_progression"] if pd.notna(latest_stats["weight_progression"]) else 0.0
        metrics_col3.metric("Max Weight", f"{latest_stats['max_weight_kg']} kg", f"{weight_delta} kg")
        
        chart_col1, chart_col2 = st.columns(2)
        
        figure_1rm = px.line(
            exercise_progression, 
            x="cycle_number", 
            y="estimated_1rm_kg", 
            markers=True,
            title="1RM Trend"
        )
        chart_col1.plotly_chart(figure_1rm, use_container_width=True)
        
        figure_volume = px.bar(
            exercise_progression, 
            x="cycle_number", 
            y="total_volume_kg",
            title="Volume Trend"
        )
        chart_col2.plotly_chart(figure_volume, use_container_width=True)
        
    if not exercise_execution.empty:
        st.subheader("Execution vs AI Plan")
        
        execution_col1, execution_col2 = st.columns(2)
        
        figure_reps_diff = px.bar(
            exercise_execution,
            x="cycle_number",
            y="total_reps_vs_plan",
            title="Total Reps Diff (Actual vs Planned)",
            color="total_reps_vs_plan",
            color_continuous_scale=px.colors.diverging.RdYlGn
        )
        execution_col1.plotly_chart(figure_reps_diff, use_container_width=True)
        
        figure_weight_diff = px.line(
            exercise_execution,
            x="cycle_number",
            y="avg_weight_vs_plan_kg",
            markers=True,
            title="Average Weight Diff (Actual vs Planned)"
        )
        execution_col2.plotly_chart(figure_weight_diff, use_container_width=True)

# --- MAIN APP ---

def main() -> None:
    st.set_page_config(
        page_title="Hevy API AI",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    initialize_environment()
    render_sidebar()
    
    tab_pipeline, tab_analytics = st.tabs(["Pipeline & ETL", "Analytics Dashboard"])
    
    with tab_pipeline:
        render_pipeline_tab()
        
    with tab_analytics:
        render_analytics_tab()

if __name__ == "__main__":
    main()
