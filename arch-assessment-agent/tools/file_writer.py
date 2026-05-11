import os
from datetime import datetime
from config import config

def save_report(content: str, project_name: str, output_dir: str = config.OUTPUT_DIR) -> str:
    """Saves the markdown report to the output directory with a timestamp."""
    os.makedirs(output_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    clean_name = "".join([c if c.isalnum() else "_" for c in project_name]).strip("_")
    filename = f"PARECER_{clean_name}_{timestamp}.md"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    return filepath
