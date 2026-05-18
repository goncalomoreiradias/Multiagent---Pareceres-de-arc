import re
from typing import Dict

def format_report(content: str) -> str:
    """Cleans up and validates the markdown report."""
    # Ensure standard headings
    content = re.sub(r'#{1,6}\s+', lambda m: m.group(0), content)
    return content.strip() + "\n"

def inject_diagrams(report_md: str, diagrams: Dict[str, str]) -> str:
    """Injects Mermaid diagrams and Draw.io references into the draft report markdown."""
    diagram_blocks = []
    
    if "sequence_diagram" in diagrams and diagrams["sequence_diagram"]:
        diagram_blocks.append("### Diagrama de Sequência\n```mermaid\n" + diagrams["sequence_diagram"].strip() + "\n```")
        
    if "flowchart" in diagrams and diagrams["flowchart"]:
        diagram_blocks.append("### Diagrama de Arquitetura (Flowchart)\n```mermaid\n" + diagrams["flowchart"].strip() + "\n```")
        
    # capabilities_drawio references are hardcoded in the writer prompt section 6.1

    combined_diagrams = "\n\n".join(diagram_blocks)
    
    # Replace the placeholder if it exists
    if "<!-- DIAGRAM_PLACEHOLDER -->" in report_md:
        report_md = report_md.replace("<!-- DIAGRAM_PLACEHOLDER -->", combined_diagrams)
    else:
        # Append to a default section if placeholder missing
        if combined_diagrams:
            report_md += "\n\n## Diagramas de Solução\n\n" + combined_diagrams
        
    return report_md
