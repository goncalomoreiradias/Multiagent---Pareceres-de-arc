import os
from rich.console import Console
from rich.prompt import Prompt
from orchestrator.state_machine import build_graph
from state.context_schema import AssessmentContext, GraphState, save_checkpoint, load_checkpoint
from config import config

console = Console()

def run_assessment(raw_input: str, resume: bool = False) -> str:
    """Main execution flow for the multi-agent system."""
    graph = build_graph()
    thread_config = {"configurable": {"thread_id": "assessment_1"}}
    
    checkpoint_path = os.path.join(config.STATE_DIR, "current_session.json")
    
    if resume and os.path.exists(checkpoint_path):
        console.print("[yellow]Resuming from last checkpoint...[/yellow]")
        # In a real app we'd load the state into the graph memory.
        # For simplicity, we just rely on LangGraph's in-memory thread or re-init state.
        pass
        
    # Initialize state
    initial_context = AssessmentContext(raw_input=raw_input)
    state = GraphState(context=initial_context, current_agent="init", requires_human_input=False, user_feedback=None, error=None)
    
    console.print("\n[bold green]Starting Architecture Assessment Pipeline...[/bold green]\n")
    
    try:
        # Run graph until interrupted or finished
        events = graph.stream(state, thread_config, stream_mode="values")
        for event in events:
            # We can log state changes here
            if "current_agent" in event:
                # Save checkpoint after each node
                save_checkpoint(event, checkpoint_path)
                pass
                
        # Check if we paused for human-in-the-loop
        current_state = graph.get_state(thread_config)
        
        while current_state.next and current_state.next[0] == "ask_human_review":
            console.print("\n[bold cyan]Draft Assessment Generated & Reviewed![/bold cyan]")
            console.print("The reviewer agent has completed its checks. Would you like to provide any feedback?")
            
            feedback = Prompt.ask("[yellow]Enter feedback (or press Enter to approve)[/yellow]")
            
            # Update state with feedback
            graph.update_state(thread_config, {"user_feedback": feedback})
            
            # Resume graph
            console.print("[green]Resuming graph execution...[/green]")
            events = graph.stream(None, thread_config, stream_mode="values")
            for event in events:
                save_checkpoint(event, checkpoint_path)
                
            current_state = graph.get_state(thread_config)
                
        # Final state
        final_state = graph.get_state(thread_config).values
        if "context" in final_state:
            ctx = final_state["context"]
            if hasattr(ctx, "output_file_path") and ctx.output_file_path:
                return ctx.output_file_path
            
        return "Assessment complete, but output file path not found."
            
    except Exception as e:
        console.print(f"[bold red]Pipeline failed: {e}[/bold red]")
        return str(e)
