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

# Default layout properties (removed problematic custom block-container padding)

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
        "intake_agent": "pending",
        "impact_agent": "pending",
        "question_agent": "pending",
        "context_builder": "pending",
        "architect_reasoner": "pending",
        "diagram_agent": "pending",
        "architect_writer": "pending",
        "reviewer_agent": "pending",
        "ai_corrector": "pending",
        "finalizer_reshape": "pending",
        "finalizer_complete": "pending"
    }

import streamlit.components.v1 as components

# --- Expected sequence for the UI Mini-map ---
AGENT_SEQUENCE = [
    ("intake_agent", "Receção", "📥"),
    ("impact_agent", "Impacto", "🎯"),
    ("question_agent", "Questões", "❓"),
    ("context_builder", "Contexto", "🧩"),
    ("architect_reasoner", "Raciocínio", "🧠"),
    ("diagram_agent", "Diagramas", "📊"),
    ("architect_writer", "Escrita", "✍️"),
    ("reviewer_agent", "Review do AI", "🧐"),
    ("ai_corrector", "Auto Correção", "🛠️"),
    ("finalizer_reshape", "Loop Utilizador", "🔄"),
    ("finalizer_complete", "Finalização", "✅")
]

def render_minimap():
    """Simple, stable agent minimap for UI progress tracking."""
    st.markdown("### 🤖 Estado dos Agentes")
    
    html = """
    <style>
      body { margin: 0; }
      .workflow-container { 
          padding: 10px; 
          font-family: sans-serif; 
          height: 100vh;
          max-height: 580px;
          overflow-y: auto; 
          overflow-x: hidden;
      }
      /* Custom scrollbar for webkit */
      .workflow-container::-webkit-scrollbar { width: 6px; }
      .workflow-container::-webkit-scrollbar-track { background: transparent; }
      .workflow-container::-webkit-scrollbar-thumb { background: #d1d5db; border-radius: 4px; }
      .workflow-container::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
      
      .node-row { display: flex; align-items: center; margin-bottom: 20px; position: relative; }
      .node { 
          width: 40px; height: 40px; border-radius: 50%; 
          display: flex; align-items: center; justify-content: center;
          font-size: 20px; background: #f0f2f6; border: 2px solid #d1d5db;
          z-index: 1;
      }
      .node.done { background: #e1f5fe; border-color: #03a9f4; }
      .node.running { background: #fff9c4; border-color: #fbc02d; animation: pulse 2s infinite; }
      .info { margin-left: 15px; }
      .title { font-weight: bold; font-size: 14px; color: #31333f; }
      .status { font-size: 12px; color: #555; }
      
      @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(251, 192, 45, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(251, 192, 45, 0); }
        100% { box-shadow: 0 0 0 0 rgba(251, 192, 45, 0); }
      }
      
      .line {
          position: absolute; left: 20px; top: 40px; width: 2px; height: 20px;
          background: #d1d5db; z-index: 0;
      }
    </style>
    <div class="workflow-container">
    """
    
    counts = {}
    rendered_nodes = []
    
    # 1. Add all completed nodes from node_metrics
    for m in st.session_state.node_metrics:
        node_key = m["node"]
        counts[node_key] = counts.get(node_key, 0) + 1
        
        name = node_key
        icon = "⚙️"
        for k, n, i in AGENT_SEQUENCE:
            if k == node_key:
                name = n
                icon = i
                break
                
        display_name = f"{name} (It. {counts[node_key]})" if counts[node_key] > 1 else name
        rendered_nodes.append({
            "key": node_key,
            "name": display_name,
            "icon": icon,
            "status": "done"
        })
        
    # 2. Add currently running node(s)
    running_keys = [k for k, v in st.session_state.agent_status.items() if v == "running"]
    for r_key in running_keys:
        c = counts.get(r_key, 0) + 1
        
        name = r_key
        icon = "⚙️"
        for k, n, i in AGENT_SEQUENCE:
            if k == r_key:
                name = n
                icon = i
                break
                
        display_name = f"{name} (It. {c})" if c > 1 else name
        rendered_nodes.append({
            "key": r_key,
            "name": display_name,
            "icon": icon,
            "status": "running"
        })
        
    # 3. Add remaining nodes from AGENT_SEQUENCE that haven't run at all yet
    for k, n, i in AGENT_SEQUENCE:
        if k not in counts and k not in running_keys:
            rendered_nodes.append({
                "key": k,
                "name": n,
                "icon": i,
                "status": "pending"
            })
            
    for idx, node in enumerate(rendered_nodes):
        status = node["status"]
        status_text = "Concluído" if status == "done" else ("Em execução..." if status == "running" else "Pendente")
        
        html += f"""
        <div class="node-row">
            <div class="node {status}">{node['icon']}</div>
            <div class="info">
                <div class="title">{node['name']}</div>
                <div class="status">{status_text}</div>
            </div>
            {"<div class='line'></div>" if idx < len(rendered_nodes)-1 else ""}
        </div>
        """
    
    html += "</div>"
    components.html(html, height=600)


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
        st.session_state.agent_status["intake_agent"] = "running"
        st.session_state.start_time = time.time()
    else:
        input_data = None
        # Determine what's resuming based on phase
        if st.session_state.phase == "questions":
            st.session_state.agent_status["question_agent"] = "running"
        elif st.session_state.phase == "review":
            # Determine which finalizer to start if we are resuming from human review
            tc = st.session_state.thread_config
            user_feedback = st.session_state.graph.get_state(tc).values.get("user_feedback", "")
            if user_feedback:
                st.session_state.agent_status["finalizer_reshape"] = "running"
            else:
                st.session_state.agent_status["finalizer_complete"] = "running"

    st.session_state.phase = "running"

    # Helper to push minimap update immediately
    def _update_minimap():
        if minimap_placeholder is not None:
            with minimap_placeholder.container():
                render_minimap()

    import contextlib
    
    try:
        node_start_time = time.time()

        # Show initial running state immediately
        _update_minimap()

        # Safely run the graph while suppressing stdout to avoid I/O crashes on Windows
        with contextlib.redirect_stdout(io.StringIO()):
            with get_openai_callback() as cb:
                # Stream events from the graph
                for event in graph.stream(input_data, tc, stream_mode="values"):
                    agent = event.get("current_agent", "")
                    
                    # We ignore init events and pause nodes
                    if not agent or agent == "init" or agent in ["ask_human", "ask_human_review"]:
                        continue

                    # Mark agent as done and save metrics
                    duration = time.time() - node_start_time
                    node_start_time = time.time() # Reset for next node
                    
                    agent_key = agent
                        
                    st.session_state.agent_status[agent_key] = "done"
                    
                    # Calculate incremental cost and tokens
                    current_cost = cb.total_cost - st.session_state.total_cost
                    current_tokens = cb.total_tokens - st.session_state.total_tokens
                    
                    st.session_state.total_cost = cb.total_cost
                    st.session_state.total_tokens = cb.total_tokens
                    
                    # Save simple metrics
                    st.session_state.node_metrics.append({
                        "node": agent_key,
                        "duration": duration,
                        "tokens": current_tokens,
                        "cost": current_cost
                    })
                    
                    # Mark the NEXT agent as "running" IMMEDIATELY so the UI reacts
                    idx = next((i for i, v in enumerate(AGENT_SEQUENCE) if v[0] == agent_key), -1)
                    if idx != -1 and idx + 1 < len(AGENT_SEQUENCE):
                        next_agent = AGENT_SEQUENCE[idx+1][0]
                        # Set to running to give immediate feedback during loop
                        st.session_state.agent_status[next_agent] = "running"

                    # Push UI update to the placeholder
                    _update_minimap()

        # Check where the graph stopped
        gs = graph.get_state(tc)
        
        # Clear any falsely predicted running agents if they aren't actually next
        for k in list(st.session_state.agent_status.keys()):
            if st.session_state.agent_status[k] == "running":
                st.session_state.agent_status[k] = "pending"
                
        if gs.next:
            next_node = gs.next[0]
            if next_node not in ["ask_human", "ask_human_review"]:
                st.session_state.agent_status[next_node] = "running"

        # Final UI update
        _update_minimap()

        # Check where the graph stopped
        gs = graph.get_state(tc)
        ctx = gs.values.get("context")

        if gs.next:
            next_node = gs.next[0]
            if next_node == "ask_human":
                st.session_state.phase = "questions"
                new_qs = ctx.questions[-3:]
                
                # Build a visual confidence summary for the UI
                conf_pct = int(ctx.context_confidence * 100)
                progress_color = "green" if ctx.context_confidence >= config.CONFIDENCE_THRESHOLD else "orange"
                
                q_text = f"📊 **Grau de Confiança do Contexto: :{progress_color}[{conf_pct}%]** (Limiar: {int(config.CONFIDENCE_THRESHOLD*100)}%)\n\n"
                
                # Add dimension breakdown in a small list
                dim_summary = []
                for d_key, d_label, d_max in [
                    ("business_objective", "Negócio", 20),
                    ("technical_constraints", "Técnico", 20),
                    ("security_requirements", "Segurança", 15),
                    ("integration_points", "Integração", 15)
                ]:
                    score = ctx.dimension_scores.get(d_key, 0)
                    dim_summary.append(f"{d_label}: {int(score)}/{d_max}")
                
                q_text += f"_{' | '.join(dim_summary)}_\n\n---\n\n"
                q_text += f"🔍 **Ronda de Clarificação {ctx.question_rounds}:**\n\n"
                for i, q in enumerate(new_qs, 1):
                    q_text += f"**{i}. [{q.get('category', '')}]** {q.get('question', '')}\n   _({q.get('rationale', '')})_\n\n"
                
                q_text += "--- \n💡 *Responda às questões acima ou escreva **'avançar'** para prosseguir com a informação atual.*"
                st.session_state.messages.append({"role": "assistant", "content": q_text})

            elif next_node == "ask_human_review":
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
        chat_container = st.container(height=650, border=False)
        with chat_container:
            for msg in st.session_state.messages:
                with st.chat_message(msg["role"]):
                    st.markdown(msg["content"])
                
        if user_input := st.chat_input("Descreva o pedido ou responda às perguntas..."):
            st.session_state.messages.append({"role": "user", "content": user_input})
            with chat_container:
                with st.chat_message("user"):
                    st.markdown(user_input)
            
            phase = st.session_state.phase
            if phase == "idle":
                full_input = user_input
                if uploaded_files:
                    docs_text = "\n\n--- DOCUMENTOS DE SUPORTE ANEXADOS ---\n"
                    for f in uploaded_files:
                        docs_text += f"\n[Documento: {f.name}]\n{extract_text_from_file(f)}\n"
                    full_input += docs_text

                st.session_state.messages.append({"role": "assistant", "content": "🚀 Pipeline iniciado..."})
                with chat_container:
                    with st.chat_message("assistant"):
                        st.markdown("🚀 Pipeline iniciado... (Acompanhe o estado dos agentes no painel lateral)")
                execute_pipeline(initial_input=full_input, minimap_placeholder=minimap_placeholder)
                
            elif phase == "questions":
                tc = st.session_state.thread_config
                gs = st.session_state.graph.get_state(tc)
                ctx = gs.values["context"]
                q_summary = "; ".join([q.get("question", "") for q in ctx.questions[-3:]])
                ctx.raw_input += f"\n\n[Perguntas: {q_summary}]\n[Resposta: {user_input}]\n"
                st.session_state.graph.update_state(tc, {"context": ctx})
                
                st.session_state.messages.append({"role": "assistant", "content": "🚀 Retomando pipeline..."})
                with chat_container:
                    with st.chat_message("assistant"):
                        st.markdown("🚀 Retomando pipeline...")
                execute_pipeline(minimap_placeholder=minimap_placeholder)
                
            elif phase == "review":
                tc = st.session_state.thread_config
                # Detect approval or feedback
                feedback = "" if user_input.strip().lower() in ["ok", "sim", "yes", "aprovar", "aprovado"] else user_input
                st.session_state.graph.update_state(tc, {"user_feedback": feedback})
                
                msg = "🔄 Feedback recebido. A reformular o parecer..." if feedback else "✨ Parecer aprovado! A finalizar documento..."
                st.session_state.messages.append({"role": "assistant", "content": msg})
                with chat_container:
                    with st.chat_message("assistant"):
                        st.markdown(msg)
                
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
