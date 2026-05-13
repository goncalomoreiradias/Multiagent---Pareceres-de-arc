"""Quick check of .drawio file validity."""
import os
import sys
import glob
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Find the drawio file
drawio_files = glob.glob("output/diagrams/*.drawio")
if not drawio_files:
    print("No .drawio files found")
    exit(1)

for fp in drawio_files:
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    print(f"File: {fp}")
    print(f"  Size: {len(content)} chars")
    print(f"  Starts with <mxfile: {content.strip().startswith('<mxfile')}")
    print(f"  Ends with </mxfile>: {content.strip().endswith('</mxfile>')}")
    print(f"  First 300 chars:")
    print(f"  {content[:300]}")

# Check the report
report_files = sorted(glob.glob("output/PARECER_SEPA*.md"))
if report_files:
    fp = report_files[-1]
    with open(fp, "r", encoding="utf-8") as f:
        content = f.read()
    
    print(f"\nReport: {fp}")
    print(f"  Size: {len(content)} chars")
    
    # Check sections
    for section in ["6.1", "6.2", "6.3", "6.4", "6.5", "7.", "8."]:
        found = section in content
        print(f"  Section {section}: {'FOUND' if found else 'MISSING'}")
    
    # Check capabilities reference
    if "_capabilities.drawio" in content:
        print("  Capabilities drawio reference: FOUND")
    else:
        print("  Capabilities drawio reference: MISSING")
    
    # Check mermaid blocks
    mermaid_count = content.count("```mermaid")
    print(f"  Mermaid blocks: {mermaid_count}")
