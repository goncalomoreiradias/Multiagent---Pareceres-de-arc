import re
from typing import Dict

def format_report(content: str) -> str:
    """Cleans up and validates the markdown report, stripping technical comments and placeholders."""
    # Ensure standard headings
    content = re.sub(r'#{1,6}\s+', lambda m: m.group(0), content)
    
    # Remove technical start/end diagram comment wrappers (case-insensitive)
    content = re.sub(r'<!--\s*(START|END)_(ARCHIMATE|SEQUENCE|FLOWCHART)_DIAGRAM\s*-->', '', content, flags=re.IGNORECASE)
    # Remove technical diagram placeholder tags (case-insensitive)
    content = re.sub(r'<!--\s*(ARCHIMATE|SEQUENCE|FLOWCHART)_PLACEHOLDER\s*-->', '', content, flags=re.IGNORECASE)
    
    return content.strip() + "\n"

def inject_diagrams(report_md: str, diagrams: Dict[str, str], assessment_id: str) -> str:
    """Injects or updates diagrams in the report using placeholders or wrapped HTML comments."""
    
    # 1. Build capabilities section if generated
    capabilities_block = ""
    if "capabilities_drawio" in diagrams and diagrams["capabilities_drawio"]:
        explanation = diagrams.get("capabilities_explanation", "").strip()
        capabilities_block = f"""<!-- START_ARCHIMATE_DIAGRAM -->
#### Diagrama de Capacidades (ArchiMate 3.2)

O diagrama seguinte representa a vista de capacidades da solução proposta, organizado em três camadas ArchiMate 3.2: Negócio, Aplicacional e Tecnológica.

> **Diagrama de Capacidades (ArchiMate 3.2)**
> Ficheiro: `{assessment_id}_capabilities.drawio`
> Abrir com [draw.io](https://app.diagrams.net) ou extensão draw.io no VS Code.

*Figure 1 — Diagrama de Capacidades ArchiMate 3.2 — Vista de alto nível das capacidades de negócio, aplicacionais e tecnológicas da solução proposta.*

{explanation}
<!-- END_ARCHIMATE_DIAGRAM -->"""

    # 2. Build sequence diagram if generated
    sequence_block = ""
    if "sequence_diagram" in diagrams and diagrams["sequence_diagram"]:
        seq_explanation = diagrams.get("sequence_explanation", "").strip()
        sequence_block = f"""<!-- START_SEQUENCE_DIAGRAM -->
```mermaid
{diagrams['sequence_diagram'].strip()}
```

{seq_explanation}
<!-- END_SEQUENCE_DIAGRAM -->"""

    # 3. Build flowchart diagram if generated
    flowchart_block = ""
    if "flowchart" in diagrams and diagrams["flowchart"]:
        flow_explanation = diagrams.get("flowchart_explanation", "").strip()
        flowchart_block = f"""<!-- START_FLOWCHART_DIAGRAM -->
```mermaid
{diagrams['flowchart'].strip()}
```

{flow_explanation}
<!-- END_FLOWCHART_DIAGRAM -->"""

    # Helper function to replace wrapped blocks
    def replace_wrapped_block(content: str, start_comment: str, end_comment: str, new_block: str) -> str:
        pattern = re.escape(start_comment) + r".*?" + re.escape(end_comment)
        if re.search(pattern, content, re.DOTALL):
            return re.sub(pattern, new_block, content, flags=re.DOTALL)
        return content

    # --- Injection Logic ---
    
    # Track which blocks were actually handled via placeholders or wrappers
    archimate_handled = False
    sequence_handled = False
    flowchart_handled = False

    # A. Handle ArchiMate
    if capabilities_block:
        if "<!-- START_ARCHIMATE_DIAGRAM -->" in report_md:
            report_md = replace_wrapped_block(report_md, "<!-- START_ARCHIMATE_DIAGRAM -->", "<!-- END_ARCHIMATE_DIAGRAM -->", capabilities_block)
            archimate_handled = True
        elif "<!-- ARCHIMATE_PLACEHOLDER -->" in report_md:
            report_md = report_md.replace("<!-- ARCHIMATE_PLACEHOLDER -->", capabilities_block)
            archimate_handled = True

    # B. Handle Sequence
    if sequence_block:
        if "<!-- START_SEQUENCE_DIAGRAM -->" in report_md:
            report_md = replace_wrapped_block(report_md, "<!-- START_SEQUENCE_DIAGRAM -->", "<!-- END_SEQUENCE_DIAGRAM -->", sequence_block)
            sequence_handled = True
        elif "<!-- SEQUENCE_PLACEHOLDER -->" in report_md:
            report_md = report_md.replace("<!-- SEQUENCE_PLACEHOLDER -->", sequence_block)
            sequence_handled = True

    # C. Handle Flowchart
    if flowchart_block:
        if "<!-- START_FLOWCHART_DIAGRAM -->" in report_md:
            report_md = replace_wrapped_block(report_md, "<!-- START_FLOWCHART_DIAGRAM -->", "<!-- END_FLOWCHART_DIAGRAM -->", flowchart_block)
            flowchart_handled = True
        elif "<!-- FLOWCHART_PLACEHOLDER -->" in report_md:
            report_md = report_md.replace("<!-- FLOWCHART_PLACEHOLDER -->", flowchart_block)
            flowchart_handled = True

    # D. Fallback: If any diagram was generated but not handled by placeholders/wrappers, inject before Section 4
    fallback_sections = ""
    if capabilities_block and not archimate_handled:
        fallback_sections += "\n" + capabilities_block.strip() + "\n"
    
    solution_diagrams_sub = []
    if sequence_block and not sequence_handled:
        solution_diagrams_sub.append(sequence_block.strip())
    if flowchart_block and not flowchart_handled:
        solution_diagrams_sub.append(flowchart_block.strip())
        
    if solution_diagrams_sub:
        fallback_sections += "\n#### Diagramas de Solução\n\n" + "\n\n".join(solution_diagrams_sub) + "\n"

    if fallback_sections.strip():
        # Search for "## 4. Conclusão e Recomendação" (case-insensitive)
        pattern = r"(##\s*4\.\s*Conclusão\s*e\s*Recomendação)"
        match = re.search(pattern, report_md, re.IGNORECASE)
        if match:
            start_idx = match.start()
            report_md = report_md[:start_idx] + fallback_sections + "\n" + report_md[start_idx:]
        else:
            report_md = report_md.strip() + "\n\n" + fallback_sections

    return report_md

