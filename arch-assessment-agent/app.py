import streamlit as st
import os
import json
import io
import time
import glob
from datetime import datetime
from pypdf import PdfReader
import docx
from langchain_community.callbacks import get_openai_callback
from orchestrator.state_machine import build_graph
from state.context_schema import AssessmentContext, GraphState
from config import config

st.set_page_config(page_title="ArchiMap Agent", page_icon="🏗️", layout="wide")

# --- Helper function to extract text from uploaded files ---
def extract_text_from_file(uploaded_file) -> str:
    filename = uploaded_file.name.lower()
    try:
        if filename.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(uploaded_file.read()))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            return text
        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(uploaded_file.read()))
            return "\n".join([para.text for para in doc.paragraphs])
        else:  # txt, md
            return uploaded_file.read().decode("utf-8", errors="replace")
    except Exception as e:
        return f"[Erro ao extrair {filename}: {str(e)}]"

# --- Initialize session state ---
if "graph" not in st.session_state:
    st.session_state.graph = build_graph()
    st.session_state.thread_config = {"configurable": {"thread_id": "session_1"}}
    st.session_state.messages = []
    st.session_state.phase = "idle"  # idle | running | questions | review | done
    
    # Process Tracking
    st.session_state.node_metrics = [] # [{"node": "intake", "duration": 1.2, "tokens": 500, "cost": 0.01}]
    st.session_state.total_cost = 0.0
    st.session_state.total_tokens = 0
    st.session_state.start_time = None
    
    st.session_state.agent_status = {
        "intake": "pending",
        "impact": "pending",
        "question_agent": "pending",
        "context_builder": "pending",
        "reasoner": "pending",
        "writer": "pending",
        "diagrams": "pending",
        "reviewer": "pending",
        "finalizer": "pending"
    }

import streamlit.components.v1 as components

# --- Expected sequence for the UI Mini-map ---
AGENT_SEQUENCE = [
    ("intake", "Receção", "📥"),
    ("impact", "Impacto", "🎯"),
    ("question_agent", "Questões", "❓"),
    ("context_builder", "Contexto", "🧩"),
    ("reasoner", "Raciocínio", "🧠"),
    ("writer", "Escrita", "✍️"),
    ("diagrams", "Diagramas", "📊"),
    ("reviewer", "Revisão", "🧐"),
    ("finalizer", "Finalização", "✅")
]

def render_minimap():
    st.markdown("### 🤖 Agents States", help="Passe o rato por cima de qualquer passo para ver métricas detalhadas.")
    
    html = """
    <style>
      body { margin: 0; font-family: 'Inter', sans-serif; }
      .workflow-container { padding: 10px 20px 20px 20px; }
      
      .node-row {
          display: flex;
          position: relative;
          margin-bottom: 30px;
      }
      
      /* Vertical line connecting nodes */
      .node-row:not(:last-child)::after {
          content: ""; position: absolute;
          width: 3px; background: #cbd5e1;
          left: 26px; top: 55px; bottom: -30px;
          z-index: 0; transition: background 0.3s;
      }
      .node-row.active:not(:last-child)::after {
          background: #10b981;
      }
      
      .node { 
          width: 55px; height: 55px; border-radius: 14px; 
          display: flex; align-items: center; justify-content: center;
          font-size: 26px; cursor: pointer;
          background: #ffffff; border: 2px solid #e2e8f0;
          box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
          z-index: 1; transition: transform 0.2s ease;
          flex-shrink: 0;
      }
      .node-row:hover .node { transform: scale(1.05); }
      
      .node.done { background: #ecfdf5; border-color: #10b981; }
      .node.running { 
          background: #eff6ff; border-color: #3b82f6; 
          box-shadow: 0 0 15px rgba(59,130,246,0.5); 
          animation: pulse 1.5s infinite; 
      }
      .node.pending { background: #f8fafc; border-color: #cbd5e1; filter: grayscale(100%); opacity: 0.6; }
      
      @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.6); }
        70% { box-shadow: 0 0 0 10px rgba(59, 130, 246, 0); }
        100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0); }
      }
      
      .info-box {
          margin-left: 15px; display: flex; flex-direction: column; justify-content: center;
          flex-grow: 1;
      }
      
      .title { font-weight: 600; font-size: 15px; color: #1e293b; }
      .status-text { font-size: 12px; color: #64748b; margin-top: 2px; }
      
      .metrics {
          display: none; margin-top: 8px; font-size: 12px; color: #475569;
          background: #f8fafc; padding: 8px 10px; border-radius: 6px; border: 1px solid #e2e8f0;
          box-shadow: inset 0 2px 4px 0 rgba(0, 0, 0, 0.02);
      }
      .node-row:hover .metrics { display: block; animation: fadeIn 0.2s; }
      
      @keyframes fadeIn { from { opacity: 0; transform: translateY(-5px); } to { opacity: 1; transform: translateY(0); } }
      
      .metric-row { display: flex; justify-content: space-between; margin-bottom: 3px; }
      .metric-row span:nth-child(2) { font-weight: 600; color: #0f172a; }
    </style>
    <div class="workflow-container">
    """
    
    for idx, (agent_key, agent_name, icon) in enumerate(AGENT_SEQUENCE):
        status = st.session_state.agent_status.get(agent_key, "pending")
        agent_metrics = [m for m in st.session_state.node_metrics if m["node"] == agent_key]
        
        # Details HTML
        if status == "pending":
            status_desc = "⏳ Em fila..."
            details_html = ""
        elif status == "running":
            status_desc = "🔄 A processar dados..."
            details_html = ""
        else:
            total_dur = sum(m["duration"] for m in agent_metrics) if agent_metrics else 0.0
            total_tok = sum(m["tokens"] for m in agent_metrics) if agent_metrics else 0
            total_cost = sum(m["cost"] for m in agent_metrics) if agent_metrics else 0.0
            
            status_desc = "✅ Concluído com sucesso"
            details_html = f"""
            <div class="metrics">
                <div class="metric-row"><span>⏱️ Tempo:</span> <span>{total_dur:.1f}s</span></div>
                <div class="metric-row"><span>🪙 Tokens:</span> <span>{total_tok:,}</span></div>
                <div class="metric-row"><span>💰 Custo:</span> <span>${total_cost:.4f}</span></div>
            """
            if agent_key == "question_agent" and len(agent_metrics) > 1:
                details_html += f"<div class='metric-row'><span>🔄 Iterações:</span> <span>{len(agent_metrics)} rondas</span></div>"
            details_html += "</div>"
                
        row_class = "node-row active" if status in ["done", "running"] else "node-row"
            
        html += f"""
        <div class="{row_class}">
            <div class="node {status}">{icon}</div>
            <div class="info-box">
                <div class="title">{agent_name}</div>
                <div class="status-text">{status_desc}</div>
                {details_html}
            </div>
        </div>
        """
    
    html += "</div>"
    
    components.html(html, height=800, scrolling=True)

# --- Core pipeline execution ---
def execute_pipeline(initial_input: str = None, minimap_placeholder=None):
    """Run or resume the LangGraph pipeline."""
    graph = st.session_state.graph
    tc = st.session_state.thread_config

    if initial_input is not None:
        ctx = AssessmentContext(raw_input=initial_input)
        state = GraphState(
            context=ctx, current_agent="init",
            requires_human_input=False, user_feedback=None, error=None,
        )
        input_data = state
        st.session_state.agent_status["intake"] = "running"
        st.session_state.start_time = time.time()
    else:
        input_data = None
        # Determine what's resuming based on phase
        if st.session_state.phase == "questions":
            st.session_state.agent_status["question_agent"] = "running"
        elif st.session_state.phase == "review":
            st.session_state.agent_status["finalizer"] = "running"

    st.session_state.phase = "running"

    try:
        # Wrap stream in OpenAI callback to capture token usage globally
        with get_openai_callback() as cb:
            node_start_time = time.time()
            for event in graph.stream(input_data, tc, stream_mode="values"):
                agent = event.get("current_agent", "")
                
                # We ignore init events
                if not agent or agent == "init":
                    continue
                    
                # Mark agent as done and save metrics
                duration = time.time() - node_start_time
                node_start_time = time.time() # Reset for next node
                
                if agent.startswith("finalizer"):
                    agent_key = "finalizer"
                else:
                    agent_key = agent
                    
                st.session_state.agent_status[agent_key] = "done"
                
                # Approximate tokens for this step since callback captures cumulative
                # This is a naive delta approach
                step_tokens = cb.total_tokens - st.session_state.total_tokens
                step_cost = cb.total_cost - st.session_state.total_cost
                
                st.session_state.node_metrics.append({
                    "node": agent_key,
                    "duration": duration,
                    "tokens": step_tokens,
                    "cost": step_cost
                })
                
                st.session_state.total_tokens = cb.total_tokens
                st.session_state.total_cost = cb.total_cost
                
                # Figure out the next agent to mark as "running" visually
                # (This is an approximation for UI purposes)
                idx = next((i for i, v in enumerate(AGENT_SEQUENCE) if v[0] == agent_key), -1)
                if idx != -1 and idx + 1 < len(AGENT_SEQUENCE):
                    next_agent = AGENT_SEQUENCE[idx+1][0]
                    if st.session_state.agent_status[next_agent] == "pending":
                        st.session_state.agent_status[next_agent] = "running"
                        
                if minimap_placeholder is not None:
                    with minimap_placeholder.container():
                        render_minimap()

        # Check where the graph stopped
        gs = graph.get_state(tc)
        ctx = gs.values.get("context")

        if gs.next:
            next_node = gs.next[0]
            if next_node == "ask_human":
                st.session_state.phase = "questions"
                new_qs = ctx.questions[-3:]
                q_text = f"🔍 **Ronda de Clarificação {ctx.question_rounds}:**\n\n"
                for i, q in enumerate(new_qs, 1):
                    q_text += f"**{i}. [{q.get('category', '')}]** {q.get('question', '')}\n   _({q.get('rationale', '')})_\n\n"
                st.session_state.messages.append({"role": "assistant", "content": q_text})
            else:
                st.session_state.phase = "review"
                draft_preview = ctx.draft_report_md
                st.session_state.messages.append({"role": "assistant", "content": f"📝 **Draft gerado!** Analise o parecer e dê aprovação ('ok') ou indique correções.\n\n---\n\n{draft_preview}"})
        else:
            st.session_state.phase = "done"
            if ctx and ctx.output_file_path:
                st.session_state.messages.append({"role": "assistant", "content": f"✅ **Parecer Finalizado!** Guardado em `{ctx.output_file_path}`."})

    except Exception as e:
        error_str = str(e)
        st.session_state.phase = "idle"
        
        if "402" in error_str or "afford" in error_str.lower() or "credits" in error_str.lower():
            friendly_msg = (
                "💸 **Saldo Insuficiente no OpenRouter!**\n\n"
                "A API recusou o pedido porque o custo excederia o limite máximo autorizado (erro 402).\n\n"
                "**Como resolver:**\n"
                "1. Acede a [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys) e edita a tua chave.\n"
                "2. Aumenta o `Credit Limit` da chave ou recarrega a tua conta.\n"
                "3. Volta a tentar enviar o teu pedido!"
            )
            st.session_state.messages.append({"role": "assistant", "content": friendly_msg})
        else:
            st.session_state.messages.append({"role": "assistant", "content": f"❌ **Erro no pipeline:**\n```text\n{error_str}\n```"})

    st.rerun()

# --- UI Layout ---
tab1, tab2, tab3 = st.tabs(["💬 Assistente", "📊 Métricas Avançadas", "📜 Histórico"])

with tab1:
    col_main, col_side = st.columns([3, 1])
    
    with col_side:
        with st.container(border=True):
            st.header("📎 Anexos")
            uploaded_files = st.file_uploader("Cadernos de encargos (PDF, DOCX, TXT)", accept_multiple_files=True)
            
        with st.container(border=True):
            minimap_placeholder = st.empty()
            with minimap_placeholder.container():
                render_minimap()

    with col_main:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                
        if prompt := st.chat_input("Descreva o pedido ou responda às perguntas..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            phase = st.session_state.phase
            if phase == "idle":
                full_input = prompt
                if uploaded_files:
                    docs_text = "\n\n--- DOCUMENTOS DE SUPORTE ANEXADOS ---\n"
                    for f in uploaded_files:
                        docs_text += f"\n[Documento: {f.name}]\n{extract_text_from_file(f)}\n"
                    full_input += docs_text

                st.session_state.messages.append({"role": "assistant", "content": "🚀 Pipeline iniciado..."})
                with st.chat_message("assistant"):
                    st.markdown("🚀 Pipeline iniciado... (Acompanhe o estado dos agentes no painel lateral)")
                execute_pipeline(initial_input=full_input, minimap_placeholder=minimap_placeholder)
                
            elif phase == "questions":
                tc = st.session_state.thread_config
                gs = st.session_state.graph.get_state(tc)
                ctx = gs.values["context"]
                q_summary = "; ".join([q.get("question", "") for q in ctx.questions[-3:]])
                ctx.raw_input += f"\n\n[Perguntas: {q_summary}]\n[Resposta: {prompt}]\n"
                st.session_state.graph.update_state(tc, {"context": ctx})
                
                st.session_state.messages.append({"role": "assistant", "content": "🚀 Retomando pipeline..."})
                with st.chat_message("assistant"):
                    st.markdown("🚀 Retomando pipeline...")
                execute_pipeline(minimap_placeholder=minimap_placeholder)
                
            elif phase == "review":
                tc = st.session_state.thread_config
                feedback = "" if prompt.strip().lower() in ["ok", "sim", "yes", "aprovar"] else prompt
                st.session_state.graph.update_state(tc, {"user_feedback": feedback})
                
                st.session_state.messages.append({"role": "assistant", "content": "🚀 A processar a sua resposta..."})
                with st.chat_message("assistant"):
                    st.markdown("🚀 A processar a sua resposta...")
                execute_pipeline(minimap_placeholder=minimap_placeholder)

with tab2:
    st.title("📊 Métricas de Execução")
    st.markdown("Monitorização de performance, custos e utilização de tokens.")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Tokens Consumidos", f"{st.session_state.total_tokens:,}")
    # Show cost only if > 0 (OpenRouter sometimes reports 0 via langchain basic callback, but we display it if captured)
    col2.metric("Custo Estimado", f"${st.session_state.total_cost:.4f}") 
    
    total_time = sum(m["duration"] for m in st.session_state.node_metrics)
    col3.metric("Tempo Total (Agentes)", f"{total_time:.1f}s")
    
    if st.session_state.node_metrics:
        st.subheader("Detalhe por Agente")
        metrics_data = []
        for m in st.session_state.node_metrics:
            metrics_data.append({
                "Agente": m["node"].title().replace("_", " "),
                "Duração (s)": round(m["duration"], 2),
                "Tokens": m["tokens"],
                "Custo ($)": round(m["cost"], 4)
            })
        st.dataframe(metrics_data, use_container_width=True)
    else:
        st.info("Nenhuma métrica disponível ainda. Inicie uma avaliação na aba Assistente.")

with tab3:
    st.title("📜 Histórico de Pareceres")
    st.markdown("Consulte pareceres de arquitetura gerados anteriormente (armazenados localmente).")
    
    output_dir = config.OUTPUT_DIR
    if os.path.exists(output_dir):
        files = sorted(glob.glob(os.path.join(output_dir, "*.md")), reverse=True)
        if files:
            for f in files:
                filename = os.path.basename(f)
                # Parse timestamp from PARECER_ProjectName_YYYYMMDD_HHMMSS.md
                # Simplification: just show filename and content in expander
                with st.expander(f"📄 {filename}"):
                    try:
                        with open(f, "r", encoding="utf-8") as md_file:
                            st.markdown(md_file.read())
                    except Exception as e:
                        st.error(f"Erro ao ler ficheiro: {e}")
        else:
            st.info("Nenhum parecer gerado ainda.")
    else:
        st.info("O diretório de output ainda não existe.")
