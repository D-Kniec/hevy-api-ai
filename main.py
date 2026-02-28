import sys
from pathlib import Path

def find_project_root() -> Path:
    current_file = Path(__file__).resolve()
    for parent in [current_file] + list(current_file.parents):
        if parent.name == "src":
            return parent.parent
    return current_file.parent

BASE_DIR = find_project_root()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm

from src.etl.pipeline import run_full_pipeline
from src.ai.agent import run_agent

console = Console()

def display_welcome_banner() -> None:
    welcome_text = Text(
        "Welcome to Hevy API AI Assistant\n\n"
        "This tool automates your workout data ingestion,\n"
        "processes it into analytical layers, and uses AI\n"
        "to plan your next progressive overload session.",
        justify="center",
        style="bold cyan"
    )
    console.print(Panel(welcome_text, title="🚀 Initialization", border_style="cyan"))

def execute_etl_phase() -> bool:
    console.print("\n[bold yellow]Step 1: Data Pipeline Execution[/bold yellow]")
    console.print("Starting ETL (Bronze -> Silver -> Gold)...")
    
    try:
        run_full_pipeline()
        console.print("[bold green]✔ ETL Pipeline completed successfully![/bold green]")
        return True
    except Exception as error:
        console.print(f"[bold red]✖ ETL Pipeline failed: {error}[/bold red]")
        return False

def execute_ai_agent() -> None:
    console.print("\n[bold yellow]Step 2: AI Coach Assistant[/bold yellow]")
    console.print("Loading AI routines and history...")
    
    try:
        run_agent()
        console.print("\n[bold green]✔ AI Agent execution finished![/bold green]")
    except Exception as error:
        console.print(f"[bold red]✖ AI Agent failed: {error}[/bold red]")

def main() -> None:
    display_welcome_banner()
    
    if Confirm.ask("Do you want to run the ETL pipeline to fetch the latest data?"):
        success = execute_etl_phase()
        if not success:
            console.print("[bold red]Aborting due to ETL failure.[/bold red]")
            sys.exit(1)
    else:
        console.print("[dim]Skipping ETL phase. Using existing database...[/dim]")
        
    console.print("\n" + "=" * 50)
    
    if Confirm.ask("Do you want to run the AI Coach to plan your next workout?"):
        execute_ai_agent()
    else:
        console.print("[dim]Skipping AI Coach.[/dim]")
        
    console.print("\n[bold cyan]Goodbye! Stay strong. 💪[/bold cyan]")

if __name__ == "__main__":
    main()
