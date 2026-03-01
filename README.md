# Hevy_API_AI

<<<<<<< HEAD
**Status:** Active Development / Beta

This repository contains the architecture and codebase for an autonomous workout progression agent. The system integrates the Hevy App API with a Large Language Model (Google Gemini) and a structured local database (SQLite) using a Bronze-Silver-Gold ETL pipeline to automate training planning based on the principles of progressive overload.

## Core Concept

The application functions as a middleware between the user's workout history and the workout tracking platform. It retrieves past performance data, normalizes it through multiple analytical layers, analyzes actual execution against planned metrics, and generates the next scheduled routine via API updates.

## Architecture Overview

The system is designed around a Data Engineering Pipeline and an Analyze-Act loop:

* **1. Data Ingestion & ETL (Bronze, Silver, Gold):**
    * Extracts raw workout logs, routines, and templates from Hevy API.
    * Validates data using strict Pydantic schemas.
    * Transforms and stores data in a structured SQLite database.
    * Implements Slowly Changing Dimensions (SCD2) to track routine history.

* **2. Logic & Inference:**
    * SQL queries aggregate performance, calculating volume, RPE, and historical compliance.
    * Google Gemini receives a context-rich prompt containing the statistical analysis.
    * The LLM evaluates progression steps and generates a JSON-structured workout plan.

* **3. Execution:**
    * Validates the AI-generated JSON against the internal Pydantic schemas.
    * Persists structural data like supersets and rest timers.
    * PUTs the new routine to the user's Hevy account.

## Database Architecture (ETL Pipeline)

The system relies on a local SQLite database governed by strict Python ETL processes. Full database schema definitions and SQL queries are available in [docs/database.sql](docs/database.sql).

### 1. Bronze Layer (Raw Ingestion)

Data is pulled as JSON from the Hevy API, validated against Pydantic definitions ([API Write Docs](docs/post_put_api.md)), and flattened into relational tables. Detailed documentation: [Bronze Schema MD](docs/bronze_schema.md).

![Bronze Schema Diagram](docs/bronze_schema.png)

### 2. Silver Layer (Dimensional Model)

Data is cleaned and structured into a Star Schema. Slowly Changing Dimensions (SCD2) track routine template alterations over time to accurately compare historical execution against the plan that existed at that exact moment.

![Silver Schema Diagram](docs/silver_schema.png)

### 3. Gold Layer (Prompt Engineering)

A highly denormalized, business-level view optimized specifically to be injected directly into LLM prompts. It pre-calculates the execution status (e.g., 'Overperformed', 'Target Met').

![Gold Schema Diagram](docs/gold_schema.png)

## Tech Stack

* **Language:** Python 3.12+
* **External API:** Hevy API
* **Database:** SQLite (Local Analytics)
* **LLM:** Google Gemini (via google-genai)
* **Data Validation:** Pydantic
* **Interface:** Rich (CLI Dashboard)

## Current Roadmap

- [x] Implement basic Hevy API client (GET/PUT).
- [x] Set up Pydantic schemas for data validation.
- [x] Develop Bronze, Silver, and Gold ETL layers in SQLite.
- [x] Develop the prompt engineering logic for Gemini.
- [x] Create an interactive CLI dashboard using Rich.
- [ ] Implement advanced periodization and custom progression steps.
- [ ] Deploy the solution in a Dockerized environment.
=======
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

```mermaid
---
config:
  layout: dagre
---
flowchart TB
    subgraph "External World"
        HEVY[Hevy API]
        USER((User))
    end

    subgraph "Application Logic (Python)"
        AGENT["AI Orchestrator\n(Core Logic)"]
        CLI[CLI Interface]
        ST["Streamlit App\n(Control Panel)"]
    end

    subgraph "Brain & Memory (Supabase)"
        DB[(PostgreSQL Database)]
        VEC["Vector Store\n(pgvector)"]
    end

    subgraph "Intelligence"
        GEM[Gemini 1.5 Pro]
    end

    subgraph "Business Intelligence"
        META["Metabase\n(Analytics Dashboard)"]
    end

    USER -->|Click 'Generate'| ST
    ST --> AGENT

    AGENT -->|1. Fetch History| HEVY
    AGENT -->|2. Upsert Data| DB

    DB -->|Read Data| META

    AGENT -->|"3. Get Context (SQL + RAG)"| DB
    DB -->|Context: Stats & Rules| AGENT
    AGENT -->|4. Send Context + Prompt| GEM
    GEM -->|5. JSON Plan| AGENT
  
    AGENT -->|6. POST Routine| HEVY
    AGENT -->|7. Log Decision| DB
