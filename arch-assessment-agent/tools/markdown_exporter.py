import re
from typing import Dict

def format_report(content: str) -> str:
    """Cleans up and validates the markdown report."""
    # Ensure standard headings
    content = re.sub(r'#{1,6}\s+', lambda m: m.group(0), content)
    return content.strip() + "\n"

def inject_diagrams(report_md: str, diagrams: Dict[str, str], assessment_id: str) -> str:
    """Dynamically appends diagram sections before section 4 (Conclusão e Recomendação)."""
    
    # 1. Build capabilities section if generated
    capabilities_block = ""
    if "capabilities_drawio" in diagrams and diagrams["capabilities_drawio"]:
        explanation = diagrams.get("capabilities_explanation", "").strip()
        capabilities_block = f"""
#### 3.4. Diagrama de Capacidades (ArchiMate 3.2)

O diagrama seguinte representa a vista de capacidades da solução proposta, organizado em três camadas ArchiMate 3.2: Negócio, Aplicacional e Tecnológica.

> **Diagrama de Capacidades (ArchiMate 3.2)**
> Ficheiro: `{assessment_id}_capabilities.drawio`
> Abrir com [draw.io](https://app.diagrams.net) ou extensão draw.io no VS Code.

*Figure 1 — Diagrama de Capacidades ArchiMate 3.2 — Vista de alto nível das capacidades de negócio, aplicacionais e tecnológicas da solução proposta.*

{explanation}
"""

    # 2. Build solution diagrams section if generated
    solution_diagrams_block = ""
    sub_blocks = []
    if "sequence_diagram" in diagrams and diagrams["sequence_diagram"]:
        seq_explanation = diagrams.get("sequence_explanation", "").strip()
        sub_blocks.append(f"##### Diagrama de Sequência\n```mermaid\n{diagrams['sequence_diagram'].strip()}\n```\n\n{seq_explanation}")
        
    if "flowchart" in diagrams and diagrams["flowchart"]:
        flow_explanation = diagrams.get("flowchart_explanation", "").strip()
        sub_blocks.append(f"##### Diagrama de Fluxo (Flowchart)\n```mermaid\n{diagrams['flowchart'].strip()}\n```\n\n{flow_explanation}")
        
    if sub_blocks:
        combined_subs = "\n\n".join(sub_blocks)
        solution_diagrams_block = f"""
#### 3.5. Diagramas de Solução

{combined_subs}

*Os diagramas acima representam a vista de solução: fluxos de interação (sequência) e arquitetura de componentes (flowchart).*
"""

    # Combine blocks
    diagrams_sections = ""
    if capabilities_block:
        diagrams_sections += "\n" + capabilities_block.strip() + "\n"
    if solution_diagrams_block:
        diagrams_sections += "\n" + solution_diagrams_block.strip() + "\n"

    if not diagrams_sections.strip():
        return report_md

    # Insert before the Conclusão section
    # Search for "## 4. Conclusão e Recomendação" (case-insensitive)
    pattern = r"(##\s*4\.\s*Conclusão\s*e\s*Recomendação)"
    match = re.search(pattern, report_md, re.IGNORECASE)
    if match:
        start_idx = match.start()
        report_md = report_md[:start_idx] + diagrams_sections + "\n" + report_md[start_idx:]
    else:
        # Fallback to appending at the end
        report_md = report_md.strip() + "\n\n" + diagrams_sections

    return report_md
