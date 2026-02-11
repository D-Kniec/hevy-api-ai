# Hevy_API_AI

**Status: Proof of Concept / Experimental**

This repository contains the preliminary architecture and codebase for an autonomous workout progression agent. The system integrates the Hevy App API with a Large Language Model (Google Gemini 1.5 Pro) and a vector-enabled database (Supabase) to automate training planning based on the principles of progressive overload.

## core concept

The application functions as a middleware between the user's workout history and the workout tracking platform. It retrieves past performance data, analyzes it against defined strength training logic, and generates the next scheduled routine via API.

## architecture overview

The system is designed around a "Fetch-Analyze-Act" loop:

1.  **Data Ingestion:**
    * Extracts raw workout logs from Hevy API.
    * Normalizes and stores data in a structured PostgreSQL database (Supabase).
2.  **Logic & Inference:**
    * **Statistical Analysis:** SQL queries calculate volume load, estimated 1RM, and fatigue indicators (RPE) from historical data.
    * **Reasoning Engine:** Google Gemini 1.5 Pro receives a context-rich prompt containing the statistical analysis and generates a JSON-structured workout plan.
    * **Vector Search (Planned):** Retreives semantic context (e.g., injury notes, user preferences) using `pgvector`.
3.  **Execution:**
    * Validates the AI-generated JSON against the Hevy API schema.
    * POSTs the new routine to the user's Hevy account.

## tech stack

* **Language:** Python 3.12+
* **External API:** Hevy API
* **Database:** Supabase (PostgreSQL + pgvector)
* **LLM:** Google Gemini 1.5 Pro (via `google-generativeai`)
* **Interface:** Streamlit (Web Dashboard) / CLI

## current roadmap

- [ ] Implement basic Hevy API client (GET/POST).
- [ ] Set up Supabase schema for workout logs.
- [ ] Develop the prompt engineering logic for Gemini 1.5.
- [ ] Create a basic Streamlit dashboard for manual trigger.
