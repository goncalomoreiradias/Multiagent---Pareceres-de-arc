import json
import os
from typing import Dict, List, Optional, Any, TypedDict, Literal
from pydantic import BaseModel, Field

# Pydantic model for strict validation
class AssessmentContext(BaseModel):
    # Intake fields
    raw_input: str = Field(default="", description="The raw input from the requestor.")
    request_type: Optional[Literal["NEW_APPLICATION", "EVOLUTION", "EXPLORATORY"]] = Field(
        default=None, description="The type of the architectural request."
    )
    classification_confidence: float = Field(default=0.0, description="Confidence in the classification.")
    project_name: str = Field(default="Unknown Project", description="Name of the project.")
    requestor: str = Field(default="Unknown Requestor", description="Person who requested the assessment.")
    urgency: str = Field(default="Normal", description="Urgency level of the request.")
    brief_description: str = Field(default="", description="A brief summary of the request.")
    assessment_id: str = Field(default="", description="Unique assessment identifier (e.g. ASS-20260513-100000).")
    
    # Impact fields
    impacted_systems: List[Dict[str, Any]] = Field(default_factory=list, description="List of systems impacted.")
    integration_points: Dict[str, Any] = Field(default_factory=dict, description="Identified integration points.")
    
    # Question fields
    questions: List[Dict[str, Any]] = Field(default_factory=list, description="Questions generated for the user.")
    question_rounds: int = Field(default=0, description="Number of question rounds completed.")
    context_confidence: float = Field(default=0.0, description="Overall confidence in the gathered context.")
    dimension_scores: Dict[str, float] = Field(
        default_factory=lambda: {
            "business_objective": 0.0,
            "stakeholders": 0.0,
            "technical_constraints": 0.0,
            "integration_points": 0.0,
            "security_requirements": 0.0,
            "timeline_budget": 0.0,
            "slas": 0.0
        },
        description="Per-dimension confidence scores for the context."
    )
    
    # Context building fields
    business_requirements: List[str] = Field(default_factory=list, description="Consolidated business requirements.")
    technical_constraints: List[str] = Field(default_factory=list, description="Consolidated technical constraints.")
    risks: List[str] = Field(default_factory=list, description="Identified risks.")
    assumptions: List[str] = Field(default_factory=list, description="Identified assumptions.")
    
    # Architect Reasoning
    architectural_reasoning: Dict[str, Any] = Field(default_factory=dict, description="Internal reasoning (TOGAF).")
    candidate_architectures: List[Dict[str, Any]] = Field(default_factory=list, description="Alternative architectures considered.")
    trade_offs: Dict[str, Any] = Field(default_factory=dict, description="Trade-off analysis of alternatives.")
    
    # Writer and Diagram Output
    draft_report_md: str = Field(default="", description="The draft markdown report.")
    diagrams: Dict[str, str] = Field(default_factory=dict, description="Mermaid diagrams and draw.io XML generated.")
    
    # Reviewer
    reviewer_feedback: List[Dict[str, Any]] = Field(default_factory=list, description="Feedback from the architectural review.")
    reviewer_approved: bool = Field(default=False, description="Whether the Chief Architect approved the draft.")
    reviewer_run_count: int = Field(default=0, description="How many times the reviewer has run.")
    
    # Final Output
    final_report_md: str = Field(default="", description="The final merged markdown report.")
    output_file_path: str = Field(default="", description="Path to the saved report.")
    
    def to_json(self) -> str:
        return self.model_dump_json(indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "AssessmentContext":
        return cls.model_validate_json(json_str)

# LangGraph TypedDict state
class GraphState(TypedDict, total=False):
    # We embed the Pydantic model directly to ensure strict validation,
    # and provide fields for LangGraph to detect updates.
    # We will pass around a dict of the context, or just store the context object.
    context: AssessmentContext
    
    # Flow control flags
    current_agent: str
    requires_human_input: bool
    user_feedback: Optional[str]
    error: Optional[str]

# Serialization helpers
def save_checkpoint(state: GraphState, filepath: str) -> None:
    # Ensure directory exists
    os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
    
    dumpable_state = dict(state)
    if "context" in dumpable_state and isinstance(dumpable_state["context"], AssessmentContext):
        dumpable_state["context"] = dumpable_state["context"].model_dump()
        
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(dumpable_state, f, indent=2, ensure_ascii=False)

def load_checkpoint(filepath: str) -> Optional[GraphState]:
    if not os.path.exists(filepath):
        return None
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    if "context" in data:
        data["context"] = AssessmentContext.model_validate(data["context"])
        
    return GraphState(**data)
