import typer
from rich.console import Console
from rich.panel import Panel
from orchestrator.flow import run_assessment
from config import config

app = typer.Typer()
console = Console()

@app.command()
def main(
    input_text: str = typer.Option(None, "--input", "-i", help="Direct text input for the assessment"),
    file_path: str = typer.Option(None, "--file", "-f", help="Path to a text file containing the input"),
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume from the last session"),
    model: str = typer.Option("openrouter", "--model", "-m", help="LLM to use (openrouter, gemini, claude, gpt)"),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode")
):
    """
    Architecture Assessment Agent System
    Generates 'Pareceres de Arquitetura' via multi-agent orchestration.
    """
    console.print(Panel.fit("[bold blue]Architecture Assessment Agent[/bold blue]\nPowered by LangGraph & LLMs", border_style="blue"))
    
    if model not in ["openrouter", "gemini", "claude", "gpt"]:
        console.print(f"[red]Unsupported model: {model}[/red]")
        raise typer.Exit()
        
    raw_input = ""
    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_input = f.read()
        except Exception as e:
            console.print(f"[red]Error reading file: {e}[/red]")
            raise typer.Exit()
    elif input_text:
        raw_input = input_text
    elif not resume:
        raw_input = typer.prompt("Please describe the architectural request")
        
    if not raw_input and not resume:
        console.print("[red]No input provided.[/red]")
        raise typer.Exit()
        
    result_path = run_assessment(raw_input=raw_input, resume=resume)
    
    console.print("\n[bold green]Assessment Pipeline Finished[/bold green]")
    console.print(f"Result: {result_path}")

if __name__ == "__main__":
    app()
