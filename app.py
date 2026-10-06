import streamlit as st
import pandas as pd
import psycopg2
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
import plotly.express as px
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
from gtts import gTTS
import io
import os

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Controle Financeiro Integrado", layout="wide", page_icon="📊")

# --- CONFIGURAÇÃO DA API GEMINI ---
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)

# --- CONEXÃO COM O NEON POSTGRESQL ---
DATABASE_URL = st.secrets.get("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

def get_connection():
    if not DATABASE_URL:
        st.error("⚠️ URL do banco de dados (DATABASE_URL) não encontrada nos Secrets do Streamlit!")
        st.stop()
    return psycopg2.connect(DATABASE_URL)

def init_db():
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS lancamentos (
                id SERIAL PRIMARY KEY,
                data VARCHAR(10),
                descricao TEXT,
                categoria TEXT,
                tipo VARCHAR(10),
                valor NUMERIC(12,2),
                status VARCHAR(10)
            );
        ''')
        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        st.error(f"Erro ao ligar ao Neon PostgreSQL: {str(e)}")

def carregar_dados():
    try:
        conn = get_connection()
        df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data ASC, id ASC", conn)
        conn.close()
        if not df.empty:
            df['valor'] = df['valor'].astype(float)
        return df
    except Exception:
        return pd.DataFrame()

def salvar_lancamentos(df_novos):
    conn = get_connection()
    c = conn.cursor()
    for _, row in df_novos.iterrows():
        c.execute('''
            INSERT INTO lancamentos (data, descricao, categoria, tipo, valor, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (str(row['data']), str(row['descricao']), str(row['categoria']), str(row['tipo']), float(row['valor']), str(row['status'])))
    conn.commit()
    c.close()
    conn.close()

def atualizar_status(id_registro, novo_status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE lancamentos SET status = %s WHERE id = %s", (novo_status, int(id_registro)))
    conn.commit()
    c.close()
    conn.close()

def excluir_registro(id_registro):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lancamentos WHERE id = %s", (int(id_registro),))
    conn.commit()
    c.close()
    conn.close()

# --- FUNÇÃO DE FORMATAÇÃO EM REAIS (BRL) ---
def formata_brl(valor):
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# --- ESTILIZAÇÃO CSS AVANÇADA ---
st.markdown("""
    <style>
    .block-container {
        padding-top: 1.8rem !important;
        padding-bottom: 2rem !important;
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* KPI Cards - Estilo SaaS Clean */
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 16px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
        transition: all 0.2s ease-in-out;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
        border-color: #CBD5E1;
    }
    .kpi-title {
        color: #64748B;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.45rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.2;
    }
    .kpi-sub {
        color: #64748B;
        font-size: 0.72rem;
        margin-top: 6px;
        font-weight: 500;
    }

    /* Estilização das Abas (Tabs) */
    button[data-baseweb="tab"] {
        border-radius: 6px 6px 0 0 !important;
        padding: 8px 16px !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #F1F5F9 !important;
        color: #1E293B !important;
        border-bottom: 3px solid #2563EB !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- RELATÓRIO PDF (Compatível com fpdf2 e fpdf1) ---
class RelatorioPDF(FPDF):
    def __init__(self, titulo_periodo):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.titulo_periodo = titulo_periodo

    def header(self):
        self.set_fill_color(31, 78, 121)
        self.rect(0, 0, 210, 22, 'F')
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(255, 255, 255)
        self.cell(0, 6, 'RELATÓRIO DE CONTROLE FINANCEIRO', align='C', ln=1)
        self.set_font('Helvetica', 'I', 9)
        self.cell(0, 5, f'Período: {self.titulo_periodo}', align='C', ln=1)
        self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Gerado em {datetime.today().strftime("%d/%m/%Y às %H:%M")} | Página {self.page_no()}/{{nb}}', align='C')

def gerar_pdf_isolado(df_periodo, titulo_periodo, total_ent, total_sai, saldo, aberto):
    pdf = RelatorioPDF(titulo_periodo)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(0, 7, 'RESUMO DO PERÍODO', ln=1)
    
    pdf.set_font('Helvetica', '', 9)
    pdf.set_text_color(0, 0, 0)
    pdf.set_fill_color(245, 247, 250)
    pdf.set_draw_color(210, 215, 220)
    pdf.rect(10, pdf.get_y(), 190, 18, 'FD')
    
    y_start = pdf.get_y() + 3
    pdf.set_y(y_start)
    pdf.cell(47.5, 5, f'Entradas: {formata_brl(total_ent)}', align='C')
    pdf.cell(47.5, 5, f'Saídas: {formata_brl(total_sai)}', align='C')
    pdf.cell(47.5, 5, f'Saldo Líquido: {formata_brl(saldo)}', align='C')
    pdf.cell(47.5, 5, f'Em Aberto: {formata_brl(aberto)}', align='C')
    
    pdf.set_y(y_start + 18)

    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(31, 78, 121)
    pdf.cell(0, 7, 'DETALHAMENTO DOS LANÇAMENTOS', ln=1)
    pdf.ln(1)

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(31, 78, 121)
    pdf.set_text_color(255, 255, 255)
    
    larguras = [22, 68, 35, 18, 27, 20]
    colunas = ['Data', 'Descrição', 'Categoria', 'Tipo', 'Valor', 'Status']
    
    for idx, col in enumerate(colunas):
        align = 'R' if col == 'Valor' else ('C' if col in ['Data', 'Tipo', 'Status'] else 'L')
        pdf.cell(larguras[idx], 7, col, fill=True, border=1, align=align)
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    
    fill = False
    for _, row in df_periodo.iterrows():
        try:
            data_str = datetime.strptime(str(row['data']), '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            data_str = str(row['data'])
            
        valor_str = formata_brl(float(row['valor']))
        pdf.set_fill_color(248, 249, 250) if fill else pdf.set_fill_color(255, 255, 255)
        
        pdf.cell(larguras[0], 6.5, data_str, border=1, align='C', fill=fill)
        pdf.cell(larguras[1], 6.5, str(row['descricao'])[:36], border=1, align='L', fill=fill)
        pdf.cell(larguras[2], 6.5, str(row['categoria'])[:20], border=1, align='L', fill=fill)
        pdf.cell(larguras[3], 6.5, str(row['tipo']), border=1, align='C', fill=fill)
        pdf.cell(larguras[4], 6.5, valor_str, border=1, align='R', fill=fill)
        pdf.cell(larguras[5], 6.5, str(row['status']), border=1, align='C', fill=fill)
        pdf.ln()
        fill = not fill

    # Tratamento seguro para FPDF1 e FPDF2
    out = pdf.output()
    if isinstance(out, str):
        return out.encode('latin1')
    return bytes(out)

# Inicialização da base de dados no Neon
init_db()

meses_pt = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

# --- SIDEBAR ---
st.sidebar.title("⚙️ Painel de Controle")
st.sidebar.markdown("---")

df_todos = carregar_dados()

if not df_todos.empty:
    df_todos['datetime'] = pd.to_datetime(df_todos['data'])
    df_todos['Ano'] = df_todos['datetime'].dt.year
    df_todos['Mês_Num'] = df_todos['datetime'].dt.month
    df_todos['Mês_Nome'] = df_todos['Mês_Num'].map(meses_pt)

    st.sidebar.subheader("📌 Filtros do Relatório")
    anos_disp = sorted(list(df_todos['Ano'].unique()), reverse=True)
    ano_sel = st.sidebar.selectbox("Ano de Referência", anos_disp, key="side_ano")
    
    opcao_periodo = st.sidebar.radio("Visão Visual", ["Mensal", "Ano Todo (Acumulado)"], key="side_visao")
    
    if opcao_periodo == "Mensal":
        meses_disp = [meses_pt[m] for m in sorted(df_todos[df_todos['Ano'] == ano_sel]['Mês_Num'].unique())]
        mes_sel_nome = st.sidebar.selectbox("Mês de Referência", meses_disp, key="side_mes")
    else:
        mes_sel_nome = "Todos"

    aberto_total = df_todos[df_todos['status'] == 'Aberto']['valor'].sum()
    if aberto_total > 0:
        st.sidebar.markdown("---")
        st.sidebar.warning(f"⚠️ **Atenção:** Possui **{formata_brl(aberto_total)}** em contas pendentes!")

# --- CORPO PRINCIPAL ---
st.title("💼 Dashboard de Gestão Financeira")

if not df_todos.empty:
    total_entradas = df_todos[df_todos['tipo'] == 'Entrada']['valor'].sum()
    total_saidas = df_todos[df_todos['tipo'] == 'Saída']['valor'].sum()
    saldo_atual = total_entradas - total_saidas
    em_aberto = df_todos[df_todos['status'] == 'Aberto']['valor'].sum()
    pago_fechado = df_todos[df_todos['status'] == 'Pago']['valor'].sum()

    cor_saldo_texto = "#15803D" if saldo_atual >= 0 else "#B91C1C"
    cor_saldo_borda = "#16A34A" if saldo_atual >= 0 else "#DC2626"

    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        st.markdown(f"""
            <div class="kpi-card" style="border-left: 4px solid #16A34A;">
                <div class="kpi-title">Total Entradas</div>
                <div class="kpi-value" style="color: #15803D;">{formata_brl(total_entradas)}</div>
                <div class="kpi-sub">📈 Receitas confirmadas</div>
            </div>
        """, unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
            <div class="kpi-card" style="border-left: 4px solid #DC2626;">
                <div class="kpi-title">Total Saídas</div>
                <div class="kpi-value" style="color: #B91C1C;">{formata_brl(total_saidas)}</div>
                <div class="kpi-sub">📉 Despesas executadas</div>
            </div>
        """, unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
            <div class="kpi-card" style="border-left: 4px solid {cor_saldo_borda};">
                <div class="kpi-title">Saldo Líquido</div>
                <div class="kpi-value" style="color: {cor_saldo_texto};">{formata_brl(saldo_atual)}</div>
                <div class="kpi-sub">⚖️ Balanço geral</div>
            </div>
        """, unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
            <div class="kpi-card" style="border-left: 4px solid #D97706;">
                <div class="kpi-title">Contas em Aberto</div>
                <div class="kpi-value" style="color: #B45309;">{formata_brl(em_aberto)}</div>
                <div class="kpi-sub">⏳ Pendente de baixa</div>
            </div>
        """, unsafe_allow_html=True)

    with c5:
        st.markdown(f"""
            <div class="kpi-card" style="border-left: 4px solid #2563EB;">
                <div class="kpi-title">Contas Pagas</div>
                <div class="kpi-value" style="color: #1D4ED8;">{formata_brl(pago_fechado)}</div>
                <div class="kpi-sub">✅ Baixas efetuadas</div>
            </div>
        """, unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# --- NAVEGAÇÃO POR ABAS ---
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "➕ Novo Lançamento", 
    "🔄 Parcelamento", 
    "📋 Contas & Baixas",
    "📊 Relatórios & Gráficos",
    "🤖 Assistente IA (Texto/Voz)"
])

# ABA 1: LANÇAMENTO ÚNICO
with aba1:
    st.subheader("Registrar Lançamento Avulso")
    col1, col2 = st.columns(2)
    with col1:
        data_u = st.date_input("Data de Vencimento", value=datetime.today(), key="data_u")
        desc_u = st.text_input("Descrição", key="desc_u", placeholder="Ex: Conta de Luz")
        cat_u = st.text_input("Categoria", key="cat_u", placeholder="Ex: Utilidades")
    with col2:
        tipo_u = st.selectbox("Tipo", ["Saída", "Entrada"], key="tipo_u")
        valor_u = st.number_input("Valor (R$)", min_value=0.01, value=100.00, format="%.2f", key="val_u")
        status_u = st.selectbox("Status Inicial", ["Aberto", "Pago"], key="st_u")

    if st.button("💾 Salvar Lançamento", use_container_width=True):
        if not desc_u:
            st.warning("Preencha a descrição antes de salvar.")
        else:
            novo = pd.DataFrame([{
                "data": data_u.strftime("%Y-%m-%d"),
                "descricao": desc_u,
                "categoria": cat_u,
                "tipo": tipo_u,
                "valor": float(valor_u),
                "status": status_u
            }])
            salvar_lancamentos(novo)
            st.success("Lançamento guardado com sucesso!")
            st.rerun()

# ABA 2: PARCELADO
with aba2:
    st.subheader("Registrar Parcelamento ou Recorrência")
    col_l, col_r = st.columns(2)
    with col_l:
        data_p = st.date_input("Data da 1ª Parcela", value=datetime.today(), key="data_p")
        desc_p = st.text_input("Descrição Base", key="desc_p", placeholder="Ex: Compra Equipamentos")
        cat_p = st.text_input("Categoria", key="cat_p", placeholder="Ex: Investimentos")
        tipo_p = st.selectbox("Tipo", ["Saída", "Entrada"], key="tipo_p")
    with col_r:
        regra_val = st.radio("Cálculo do Valor:", ["Valor Total (Dividir pelas parcelas)", "Valor Fixo por Parcela"], key="regra_v")
        valor_dig = st.number_input("Valor (R$)", min_value=0.01, value=1200.00, format="%.2f", key="val_p")
        qtd_p = st.number_input("Quantidade de Parcelas", min_value=1, value=12, step=1, key="qtd_p")
        status_1a = st.selectbox("Status da 1ª Parcela", ["Aberto", "Pago"], key="st_p")

    if st.button("🔄 Gerar Parcelamento", use_container_width=True):
        if not desc_p:
            st.warning("Preencha a descrição base.")
        else:
            val_calc = (valor_dig / qtd_p) if regra_val == "Valor Total (Dividir pelas parcelas)" else valor_dig
            lista = []
            for i in range(int(qtd_p)):
                venc = data_p + relativedelta(months=i)
                st_parc = status_1a if i == 0 else "Aberto"
                lista.append({
                    "data": venc.strftime("%Y-%m-%d"),
                    "descricao": f"{desc_p} ({i+1}/{int(qtd_p)})",
                    "categoria": cat_p,
                    "tipo": tipo_p,
                    "valor": round(val_calc, 2),
                    "status": st_parc
                })
            salvar_lancamentos(pd.DataFrame(lista))
            st.success(f"Registradas {int(qtd_p)} parcelas com sucesso!")
            st.rerun()

# ABA 3: EXTRATO E BAIXAS
with aba3:
    st.subheader("📋 Gestão de Extrato e Baixa Manual")
    df_e = carregar_dados()
    
    if not df_e.empty:
        df_e['datetime'] = pd.to_datetime(df_e['data'])
        df_e['Ano'] = df_e['datetime'].dt.year
        df_e['Mês_Nome'] = df_e['datetime'].dt.month.map(meses_pt)

        f1, f2, f3 = st.columns([2, 2, 3])
        with f1:
            st_filtro = st.multiselect("Filtrar Status", df_e['status'].unique(), default=df_e['status'].unique())
        with f2:
            tp_filtro = st.multiselect("Filtrar Tipo", df_e['tipo'].unique(), default=df_e['tipo'].unique())
        with f3:
            busca = st.text_input("🔍 Pesquisar por Descrição ou Categoria", placeholder="Digite algo...")

        df_f = df_e[(df_e['status'].isin(st_filtro)) & (df_e['tipo'].isin(tp_filtro))]
        if busca:
            df_f = df_f[df_f['descricao'].str.contains(busca, case=False) | df_f['categoria'].str.contains(busca, case=False)]

        st.markdown("---")
        if not df_f.empty:
            opts = {f"ID {r['id']} | {r['data']} | {r['descricao']} - {formata_brl(r['valor'])} [{r['status']}]": r['id'] for _, r in df_f.iterrows()}
            
            c_sel, c_btn1, c_btn2 = st.columns([5, 2, 2])
            with c_sel:
                item_sel = st.selectbox("Selecione um lançamento para alterar:", list(opts.keys()))
                id_target = opts[item_sel]
            with c_btn1:
                st.write("")
                st.write("")
                if st.button("✅ Dar Baixa (PAGO)", use_container_width=True):
                    atualizar_status(id_target, "Pago")
                    st.success("Atualizado para Pago!")
                    st.rerun()
            with c_btn2:
                st.write("")
                st.write("")
                if st.button("🗑️ Excluir", use_container_width=True):
                    excluir_registro(id_target)
                    st.warning("Registro excluído!")
                    st.rerun()

            st.dataframe(
                df_f[['id', 'data', 'descricao', 'categoria', 'tipo', 'valor', 'status']],
                column_config={"valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f")},
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("Nenhum lançamento encontrado com os filtros selecionados.")
    else:
        st.info("Nenhum lançamento cadastrado.")

# ABA 4: RELATÓRIOS & GRÁFICOS
with aba4:
    if not df_todos.empty:
        df_p = df_todos[df_todos['Ano'] == ano_sel]
        if opcao_periodo == "Mensal" and mes_sel_nome != "Todos":
            df_p = df_p[df_p['Mês_Nome'] == mes_sel_nome]

        ent_m = df_p[df_p['tipo'] == 'Entrada']['valor'].sum()
        sai_m = df_p[df_p['tipo'] == 'Saída']['valor'].sum()
        saldo_m = ent_m - sai_m
        aberto_m = df_p[df_p['status'] == 'Aberto']['valor'].sum()

        st.subheader(f"📊 Análise Visual: {mes_sel_nome if opcao_periodo == 'Mensal' else 'Ano ' + str(ano_sel)}")
        
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            df_barras = df_p.groupby('tipo')['valor'].sum().reset_index()
            if not df_barras.empty:
                fig_bar = px.bar(
                    df_barras, x='tipo', y='valor', color='tipo',
                    color_discrete_map={'Entrada': '#16A34A', 'Saída': '#DC2626'},
                    title="Entradas vs. Saídas (Período)",
                    labels={'valor': 'Total (R$)', 'tipo': 'Tipo'}
                )
                fig_bar.update_layout(showlegend=False, margin=dict(l=20, r=20, t=40, b=20), height=320)
                st.plotly_chart(fig_bar, use_container_width=True)
            else:
                st.info("Sem dados para o gráfico comparativo.")

        with col_g2:
            df_cat = df_p[df_p['tipo'] == 'Saída'].groupby('categoria')['valor'].sum().reset_index()
            if not df_cat.empty:
                fig_pie = px.pie(
                    df_cat, values='valor', names='categoria', hole=0.4,
                    title="Distribuição de Saídas por Categoria"
                )
                fig_pie.update_layout(margin=dict(l=20, r=20, t=40, b=20), height=320)
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Nenhuma saída registrada no período.")

        st.markdown("---")
        st.subheader("📋 Detalhamento em Tabela")
        
        df_exp = df_p[['data', 'descricao', 'categoria', 'tipo', 'valor', 'status']].copy()
        st.dataframe(df_exp, use_container_width=True, hide_index=True)

        tit_doc = f"{mes_sel_nome} de {ano_sel}" if opcao_periodo == "Mensal" else f"Ano Completo {ano_sel}"
        
        if st.button("⚙ Gerar Relatório PDF Profissional", use_container_width=True):
            pdf_bytes = gerar_pdf_isolado(df_exp, tit_doc, ent_m, sai_m, saldo_m, aberto_m)
            st.session_state['pdf_pronto'] = pdf_bytes
            st.session_state['pdf_nome'] = f"relatorio_{ano_sel}_{mes_sel_nome}.pdf"
            st.rerun()

        if 'pdf_pronto' in st.session_state:
            st.download_button(
                label="📥 Baixar PDF Formatado",
                data=st.session_state['pdf_pronto'],
                file_name=st.session_state['pdf_nome'],
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("Nenhum dado cadastrado para gerar relatórios.")

# ABA 5: ASSISTENTE IA (TEXTO E VOZ)
with aba5:
    st.subheader("🤖 Copiloto Financeiro Inteligente")
    st.markdown("Faça perguntas sobre o seu saldo, dívidas em aberto ou relatórios do sistema.")

    col_mic, col_txt = st.columns([1, 4])
    pergunta_final = ""

    with col_mic:
        st.write("🎙️ **Gravar Voz:**")
        audio_bytes = audio_recorder(text="", recording_color="#e84c3d", neutral_color="#303030", icon_size="2x")
        
        if audio_bytes:
            st.audio(audio_bytes, format="audio/wav")
            st.info("💡 Gravado! Digite ou envie a confirmação para consultar.")

    with col_txt:
        pergunta_texto = st.text_input("💬 **Digite sua pergunta:**", placeholder="Ex: Qual é o meu saldo atual e quais contas tenho a pagar?")
        if pergunta_texto:
            pergunta_final = pergunta_texto

    if pergunta_final:
        with st.spinner("A consultar dados e gerar resposta com o Gemini..."):
            resposta = consultar_ia_gemini(pergunta_final)
            
            st.markdown("### 🤖 Resposta:")
            st.success(resposta)
            
            # Síntese de Voz (gTTS)
            try:
                tts = gTTS(text=resposta, lang='pt', tld='com.br')
                fp = io.BytesIO()
                tts.write_to_fp(fp)
                fp.seek(0)
                
                st.write("🔊 **Ouvir resposta em áudio:**")
                st.audio(fp, format='audio/mp3')
            except Exception:
                st.caption("Não foi possível gerar áudio no momento.")