"""End-to-end test for all 4 tasks."""
import os
import sys
import json

# Force UTF-8 for Windows
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from state.context_schema import AssessmentContext, GraphState
from config import config

def run_test():
    # Build a pre-filled context that skips questions
    ctx = AssessmentContext(
        raw_input="Precisamos de evoluir o módulo de pagamentos do core banking para suportar pagamentos instantâneos via SEPA Instant Credit Transfer, integrando com o SDAPI e notificando clientes via Salesforce Marketing Cloud.",
        request_type="EVOLUTION",
        project_name="SEPA Instant Credit Transfer Integration",
        brief_description="Evolution of core banking payments module for SEPA ICT",
        context_confidence=0.95,
        question_rounds=3,
        business_requirements=["Support SEPA Instant Credit Transfer", "Integrate with SDAPI", "Notify clients via Salesforce Marketing Cloud"],
        technical_constraints=["Must integrate with existing core banking", "SDAPI API constraints", "Real-time processing required"],
        risks=["Integration complexity with SDAPI", "Latency requirements for instant payments"],
        assumptions=["SDAPI is available and documented", "Salesforce Marketing Cloud license is active"],
        impacted_systems=[
            {"name": "Core Banking - Payments Module", "impact": "HIGH"},
            {"name": "SDAPI Gateway", "impact": "HIGH"},
            {"name": "Salesforce Marketing Cloud", "impact": "MEDIUM"}
        ]
    )

    state = GraphState(context=ctx, current_agent="init", requires_human_input=False, user_feedback=None, error=None)

    results = []

    # 1. Context builder
    print("=" * 60)
    print("STAGE 1: Context Builder")
    print("=" * 60)
    from agents.context_builder import run_context_build
    result = run_context_build(state)
    state["context"] = result["context"]
    print(f"  Requirements: {len(state['context'].business_requirements)}")
    results.append(("Context Builder", True))

    # 2. Reasoner
    print("\n" + "=" * 60)
    print("STAGE 2: Architect Reasoner")
    print("=" * 60)
    from agents.architect_reasoner import run_reasoning
    result = run_reasoning(state)
    state["context"] = result["context"]
    print(f"  Reasoning keys: {list(state['context'].architectural_reasoning.keys())}")
    results.append(("Reasoner", True))

    # 3. Writer
    print("\n" + "=" * 60)
    print("STAGE 3: Architect Writer")
    print("=" * 60)
    from agents.architect_writer import run_writing
    result = run_writing(state)
    state["context"] = result["context"]
    draft = state["context"].draft_report_md
    print(f"  Draft length: {len(draft)} chars")
    print(f"  Assessment ID: {state['context'].assessment_id}")

    # TASK 1 CHECKS: No approval language (excluding the disclaimer which legitimately says "não constitui um documento de aprovação")
    bad_words = ["aprovado", "aprovação", "rejeitado", "não aprovado", "fica aprovado"]
    # Remove the disclaimer line before checking — it legitimately contains "aprovação" in a negating context
    draft_without_disclaimer = "\n".join(
        line for line in draft.split("\n")
        if "não constitui um documento de aprovação" not in line
    )
    found_bad = [w for w in bad_words if w.lower() in draft_without_disclaimer.lower()]
    if found_bad:
        print(f"  FAIL: Found approval language: {found_bad}")
        results.append(("No approval language", False))
    else:
        print("  PASS: No approval language found")
        results.append(("No approval language", True))

    # TASK 3 CHECKS: Placeholders structure
    has_archimate_placeholder = "ARCHIMATE_PLACEHOLDER" in draft
    has_sequence_placeholder = "SEQUENCE_PLACEHOLDER" in draft
    if has_archimate_placeholder and has_sequence_placeholder:
        print("  PASS: Placeholders for ArchiMate and Sequence are in initial draft (correct)")
        results.append(("Section 3 structure initial", True))
    else:
        print(f"  FAIL: archimate_placeholder={has_archimate_placeholder}, sequence_placeholder={has_sequence_placeholder} in initial draft")
        results.append(("Section 3 structure initial", False))

    # Disclaimer check
    if "não constitui um documento de aprovação ou decisão vinculativa" in draft:
        print("  PASS: Updated disclaimer found")
        results.append(("Disclaimer", True))
    else:
        print("  WARNING: Updated disclaimer not found in draft (may be added by LLM differently)")
        results.append(("Disclaimer", False))

    # Recommendation terminology check
    expected_terms = ["a abordagem preferencial seria", "a equipa considera", "do ponto de vista arquitetural", "a opinião da equipa é"]
    found_term = any(term in draft.lower() for term in expected_terms)
    if found_term:
        print("  PASS: New recommendation terminology found")
        results.append(("Recommendation terminology", True))
    else:
        print("  WARNING: New recommendation terminology not found")
        results.append(("Recommendation terminology", False))

    # 4. Diagram Agent
    print("\n" + "=" * 60)
    print("STAGE 4: Diagram Agent")
    print("=" * 60)
    state["context"].selected_diagrams = ["Sequence", "Archimate 3.2", "Flowchart"]
    from agents.diagram_agent import run_diagram_gen
    result = run_diagram_gen(state)
    state["context"] = result["context"]
    diags = state["context"].diagrams
    print(f"  Diagram keys: {list(diags.keys())}")
    print(f"  sequence_diagram: {len(diags.get('sequence_diagram', ''))} chars")
    print(f"  flowchart: {len(diags.get('flowchart', ''))} chars")
    print(f"  capabilities_drawio: {len(diags.get('capabilities_drawio', ''))} chars")

    if diags.get("sequence_diagram"):
        results.append(("Sequence diagram", True))
    else:
        results.append(("Sequence diagram", False))
    if diags.get("flowchart"):
        results.append(("Flowchart", True))
    else:
        results.append(("Flowchart", False))
    
    # Check .drawio file on disk
    drawio_path = os.path.join(config.OUTPUT_DIR, "diagrams", f"{state['context'].assessment_id}_capabilities.drawio")
    if os.path.exists(drawio_path):
        size = os.path.getsize(drawio_path)
        print(f"  PASS: .drawio file saved ({size} bytes)")
        results.append(("DrawIO file saved", True))
    else:
        print(f"  WARNING: .drawio file not found at {drawio_path}")
        results.append(("DrawIO file saved", False))

    # 5. Reviewer
    print("\n" + "=" * 60)
    print("STAGE 5: Reviewer Agent")
    print("=" * 60)
    from agents.reviewer_agent import run_review
    result = run_review(state)
    state["context"] = result["context"]
    print(f"  Feedback items: {len(state['context'].reviewer_feedback)}")
    results.append(("Reviewer", True))

    # 6. Finalizer
    print("\n" + "=" * 60)
    print("STAGE 6: Finalizer")
    print("=" * 60)
    from agents.finalizer import run_finalize
    result = run_finalize(state)
    state["context"] = result["context"]
    output_path = state["context"].output_file_path
    print(f"  Output: {output_path}")
    if os.path.exists(output_path):
        print(f"  PASS: Report file exists ({os.path.getsize(output_path)} bytes)")
        results.append(("Final report saved", True))
        
        with open(output_path, "r", encoding="utf-8") as f:
            final_content = f.read()
            
        has_diagrams_injected = "ARCHIMATE_PLACEHOLDER" not in final_content and "SEQUENCE_PLACEHOLDER" not in final_content
        has_archimate_section = "Diagrama de Capacidades (ArchiMate 3.2)" in final_content
        has_sequence_section = "sequenceDiagram" in final_content
        
        if has_diagrams_injected and has_archimate_section and has_sequence_section:
            print("  PASS: Diagrams injected and placeholders replaced in final report")
            results.append(("Final report structure", True))
        else:
            print(f"  FAIL: diagrams_injected={has_diagrams_injected}, archimate={has_archimate_section}, sequence={has_sequence_section}")
            results.append(("Final report structure", False))
    else:
        print(f"  FAIL: Report file not found")
        results.append(("Final report saved", False))
        results.append(("Final report structure", False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS SUMMARY")
    print("=" * 60)
    for name, passed in results:
        icon = "PASS" if passed else "FAIL"
        print(f"  [{icon}] {name}")
    
    passed_count = sum(1 for _, p in results if p)
    total = len(results)
    print(f"\n  {passed_count}/{total} checks passed")

    # List output files
    print("\n  Output files:")
    for dirpath, dirnames, filenames in os.walk(config.OUTPUT_DIR):
        for fname in filenames:
            fpath = os.path.join(dirpath, fname)
            print(f"    {fpath} ({os.path.getsize(fpath)} bytes)")

if __name__ == "__main__":
    run_test()
