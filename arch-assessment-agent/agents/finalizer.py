import os
from langchain_core.messages import HumanMessage
from state.context_schema import GraphState
from tools.markdown_exporter import format_report
from tools.file_writer import save_report
from tools.response_parser import extract_text
from config import config

def run_reshape(state: GraphState) -> dict:
    """Applies reviewer feedback and user feedback to reshape the report."""
    print("[Finalizer] Reshaping report based on feedback...")
    context = state["context"]
    user_feedback = state.get("user_feedback", "")
    
    prompt = f"""
    You are an expert Enterprise Architect Editor.
    Revise the following Architecture Assessment Report based on the reviewer feedback and user feedback.
    Ensure the final output is in pt-PT and properly formatted in Markdown.
    
    Current Draft:
    {context.draft_report_md}
    
    Reviewer Feedback:
    {context.reviewer_feedback}
    
    User Feedback:
    {user_feedback}
    
    Output ONLY the revised Markdown report. Do not include introductory text.
    """
    
    llm = config.get_llm("gemini_flash")
    response = llm.invoke([HumanMessage(content=prompt)])
    
    context.draft_report_md = extract_text(response.content).strip()
    
    return {
        "context": context,
        "current_agent": "finalizer_reshape"
    }

def run_finalize(state: GraphState) -> dict:
    """Saves the final report."""
    print("[Finalizer] Saving final assessment...")
    context = state["context"]
    
    final_content = format_report(context.draft_report_md)
    context.final_report_md = final_content
    
    filepath = save_report(final_content, context.project_name)
    context.output_file_path = filepath
    
    print(f"[Finalizer] Report saved to: {filepath}")
    
    return {
        "context": context,
        "current_agent": "finalizer_complete"
    }
