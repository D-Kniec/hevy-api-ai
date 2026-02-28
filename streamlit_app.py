import sys
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st
import plotly.express as px

# --- KONFIGURACJA ŚCIEŻEK ---
def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file, *current_file.parents]:
        if (parent / "data").exists() and (parent / "src").exists():
            return parent
    return current_file.parent

base_dir = find_project_root()
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from src.etl.pipeline import run_full_pipeline
from src.ai.agent import run_agent

# Sztywna, JEDYNA POPRAWNA ścieżka zgodna z 02_silver.py!
DB_PATH = base_dir / "data" / "bronze_layer.db"

def get_db_connection() -> Optional[sqlite3.Connection]:
    if not DB_PATH.exists():
        st.error(f"Nie znaleziono bazy danych w ścieżce: {DB_PATH}")
        return None
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def get_routines_from_db() -> list:
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        query = "SELECT routine_id, routine_name FROM silver_dim_routine WHERE routine_name IS NOT NULL"
        cursor = conn.cursor()
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        
        return [{"id": row[0], "title": row[1]} for row in rows]
    except Exception as e:
        if conn: conn.close()
        st.error(f"Błąd przy pobieraniu list planów (uruchom ETL najpierw!): {e}")
        return []

def load_workout_dataframe() -> Optional[pd.DataFrame]:
    conn = get_db_connection()
    if not conn:
        return None

    try:
        # DOŁĄCZAMY bronze_workouts w ON f.workout_id = w.workout_id, aby odzyskać start_time!
        query = """
        SELECT 
            f.workout_id,
            f.routine_id,
            w.start_time,
            f.set_type,
            f.weight_kg,
            f.reps,
            f.rpe,
            f.execution_status,
            e.exercise_name AS exercise_title,
            r.routine_name AS workout_title
        FROM silver_fact_workout_history f
        LEFT JOIN bronze_workouts w ON f.workout_id = w.workout_id
        LEFT JOIN silver_dim_exercise e ON f.exercise_template_id = e.exercise_template_id
        LEFT JOIN silver_dim_routine r ON f.routine_id = r.routine_id
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return df
            
        # Formatowanie dat na podstawie dociągniętego start_time z bronze_workouts
        if "start_time" in df.columns:
            df["start_time"] = pd.to_datetime(df["start_time"], errors="coerce")
            df["workout_date"] = df["start_time"].dt.date
            df["year_week"] = df["start_time"].dt.strftime("%Y-W%V")
            
        df["volume"] = df["weight_kg"].fillna(0) * df["reps"].fillna(0)

        return df

    except Exception as e:
        conn.close()
        st.error(f"Błąd podczas ładowania analityki: {e}")
        return None


# --- LAYOUT APLIKACJI ---
st.set_page_config(page_title="Hevy API AI", layout="wide", page_icon="🏋️")
st.title("🏋️ Hevy API AI Assistant")

tab_coach, tab_analytics = st.tabs(["🤖 AI Coach", "📊 Analytics"])

# ─── TAB 1: AI COACH ────────────────────────────────────────────────────────
with tab_coach:
    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("ETL Pipeline")
        st.markdown("Pobierz najnowsze dane z API i przetwórz je do lokalnej bazy.")
        run_etl_button = st.button("Run ETL Pipeline", type="primary")

    with col_right:
        st.subheader("AI Coach")
        st.markdown("Wygeneruj plan treningowy na podstawie historii z Hevy.")
        
        routines = get_routines_from_db()
        
        if routines:
            routine_options = {f"{r['title']} (ID: {str(r['id'])[:8]}...)": r for r in routines}
            selected_option = st.selectbox("Wybierz plan treningowy:", options=list(routine_options.keys()))
            selected_routine_dict = routine_options[selected_option]
            
            run_ai_button = st.button("Run AI Agent", type="primary")
        else:
            st.info("Brak planów w bazie. Uruchom ETL.")
            run_ai_button = False

    if run_etl_button:
        with st.spinner("Running ETL pipeline..."):
            try:
                run_full_pipeline()
                st.success("ETL completed successfully!")
                st.rerun()
            except Exception as error:
                st.error("ETL Failed")
                st.exception(error)

    if run_ai_button:
        with st.spinner(f"Generating plan for '{selected_routine_dict['title']}'..."):
            try:
                run_agent(selected_routine_dict=selected_routine_dict, auto_confirm=True)
                st.success(f"Plan for '{selected_routine_dict['title']}' has been updated in Hevy!")
            except Exception as error:
                st.error("AI Agent Failed")
                st.exception(error)

# ─── TAB 2: ANALYTICS ───────────────────────────────────────────────────────
with tab_analytics:
    df = load_workout_dataframe()

    if df is not None and not df.empty:
        if "set_type" in df.columns:
            df["set_type"] = df["set_type"].fillna("normal")
            normal_sets = df[df["set_type"].str.lower() == "normal"].copy()
            if normal_sets.empty: normal_sets = df.copy()
        else:
            normal_sets = df.copy()

        # 1. KPI
        st.subheader("Global Stats")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        
        total_volume = normal_sets["volume"].sum() / 1000 
        total_workouts = normal_sets["workout_id"].nunique()
        total_sets = len(normal_sets)
        avg_rpe = pd.to_numeric(normal_sets["rpe"], errors="coerce").dropna().mean() if "rpe" in normal_sets.columns else float('nan')

        kpi1.metric("Total Volume", f"{total_volume:,.1f} t")
        kpi2.metric("Workouts Logged", f"{total_workouts}")
        kpi3.metric("Total Sets", f"{total_sets:,}")
        kpi4.metric("Avg RPE", f"{avg_rpe:.1f}" if pd.notna(avg_rpe) else "N/A")

        st.divider()

        # 2. Wykresy
        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            st.subheader("Volume Trend (Weekly)")
            if "year_week" in normal_sets.columns:
                weekly_vol = normal_sets.groupby("year_week")["volume"].sum().reset_index()
                weekly_vol["volume_t"] = weekly_vol["volume"] / 1000
                fig_vol = px.bar(weekly_vol, x="year_week", y="volume_t", title="Volume per Week (Tonnes)", labels={"year_week": "Week", "volume_t": "Volume (t)"})
                st.plotly_chart(fig_vol, use_container_width=True)

        with col_chart2:
            st.subheader("Exercise Frequency")
            if "exercise_title" in normal_sets.columns:
                ex_freq = normal_sets["exercise_title"].value_counts().reset_index().head(10)
                ex_freq.columns = ["Exercise", "Sets"]
                fig_freq = px.bar(ex_freq, x="Sets", y="Exercise", orientation='h', title="Top 10 Exercises by Sets")
                fig_freq.update_layout(yaxis={'categoryorder':'total ascending'})
                st.plotly_chart(fig_freq, use_container_width=True)

        # 3. Szczegóły
        st.subheader("Recent Working Sets Data")
        cols_to_show = ["workout_date", "workout_title", "exercise_title", "weight_kg", "reps", "rpe", "execution_status", "volume"]
        cols_available = [c for c in cols_to_show if c in normal_sets.columns]
        
        st.dataframe(
            normal_sets[cols_available].sort_values("workout_date", ascending=False) if "workout_date" in normal_sets.columns else normal_sets[cols_available],
            use_container_width=True,
            hide_index=True
        )

    else:
        st.info("No analytics data available yet. Please run ETL first to fetch workout data.")
