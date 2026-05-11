import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Project Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    OUTPUT_DIR = os.path.join(BASE_DIR, "output")
    STATE_DIR = os.path.join(BASE_DIR, "state")
    PROMPTS_DIR = os.path.join(BASE_DIR, "prompts")
    
    # Ensure directories exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(STATE_DIR, exist_ok=True)
    
    # Institution Context
    INSTITUTION_NAME = "Caixa Geral de Depósitos (CGD)"
    
    # Default Thresholds
    CONFIDENCE_THRESHOLD = 0.85
    MAX_QUESTION_ROUNDS = 3
    
    @staticmethod
    def get_llm(model_name: str = "openrouter"):
        """Factory method to get the specified LangChain model."""
        if model_name == "openrouter":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable is missing.")
            return ChatOpenAI(
                model="anthropic/claude-4.6-sonnet", # Utilizador pediu Sonnet 4.6
                api_key=api_key,
                base_url="https://openrouter.ai/api/v1",
                temperature=0.2,
                max_tokens=4096,  # Limite máximo para output para evitar reserva total de 65k e erro 402
                max_retries=3
            )
        elif model_name == "gemini":
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError("GOOGLE_API_KEY environment variable is missing.")
            return ChatGoogleGenerativeAI(
                model="gemini-2.5-pro", # Use the latest available or requested
                temperature=0.2,
                max_retries=3
            )
        elif model_name == "claude":
            from langchain_anthropic import ChatAnthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable is missing.")
            return ChatAnthropic(
                model="claude-3-5-sonnet-20240620",
                temperature=0.2,
                max_retries=3
            )
        elif model_name == "gpt":
            from langchain_openai import ChatOpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable is missing.")
            return ChatOpenAI(
                model="gpt-4o",
                temperature=0.2,
                max_retries=3
            )
        else:
            raise ValueError(f"Unsupported model: {model_name}")

# Default global configuration instance
config = Config()
