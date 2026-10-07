import streamlit as st
import pandas as pd
import psycopg2
import plotly.express as px
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
import google.generativeai as genai
import io
from gtts import gTTS

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Controle Financeiro Pessoal",
    page_icon="💰",
    layout="wide"
)

# --- ESTILIZAÇÃO CSS CUSTOMIZADA ---
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    h1, h2, h3 {
        color: #1f4e79 !important;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    .kpi-card {
        background-color: #ffffff;
        border-radius: 12px;
        padding: 18px 22px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border-left: 5px solid #1f4e79;
        margin-bottom: 10px;
    }
    .kpi-card-entrada { border-left-color: #2ecc71; }
    .kpi-card-saida { border-left-color: #e74c3c; }
    .kpi-card-saldo { border-left-color: #3498db; }
    .kpi-card-pendente { border-left-color: #f39c12; }
    
    .kpi-title {
        font-size: 0.85rem;
        color: #7f8c8d;
        font-weight: 600;
        text-transform: uppercase;
        margin-bottom: 4px;
    }
    .kpi-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #2c3e50;
    }
</style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS ---
def get_db_connection():
    try:
        return psycopg2.connect(st.secrets["DATABASE_URL"])
    except Exception as e:
        st.error(f"Erro de conexão com o banco de dados: {e}")
        st.stop()

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS financas (
            id SERIAL PRIMARY KEY,
            data DATE NOT NULL,
            descricao TEXT NOT NULL,
            categoria TEXT NOT NULL,
            tipo TEXT NOT NULL,
            valor NUMERIC(10, 2) NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    cur.close()
    conn.close()

init_db()

# --- FUNÇÕES UTILITÁRIAS ---
def carregar_dados():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM financas ORDER BY data DESC, id DESC", conn)
    conn.close()
    if not df.empty:
        df['data'] = pd.to_datetime(df['data'])
    return df

def salvar_lancamento(data, descricao, categoria, tipo, valor, status, parcelas=1):
    conn = get_db_connection()
    cur = conn.cursor()
    valor_parcela = round(valor / parcelas, 2)
    
    for i in range(parcelas):
        data_parcela = data + relativedelta(months=i)
        desc_final = f"{descricao} ({i+1}/{parcelas})" if parcelas > 1 else descricao
        cur.execute("""
            INSERT INTO financas (data, descricao, categoria, tipo, valor, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (data_parcela, desc_final, categoria, tipo, valor_parcela, status))
        
    conn.commit()
    cur.close()
    conn.close()

def excluir_lancamento(id_registro):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM financas WHERE id = %s", (id_registro,))
    conn.commit()
    cur.close()
    conn.close()

def formata_brl(valor):
    if pd.isna(valor) or valor is None:
        return "R$ 0,00"
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"

# --- CLASSE E GERAÇÃO DO PDF (ISOLADA DE MAGIC COMMANDS) ---
class RelatorioPDF(FPDF):
    def __init__(self, titulo_periodo):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.titulo_periodo = titulo_periodo

    def header(self):
        self.set_fill_color(31, 78, 121)
        self.rect(0, 0, 210, 22, 'F')
        self.set_font('Helvetica', 'B', 15)
        self.set_text_color(255, 255, 255)
        _ = self.cell(0, 6, 'RELATORIO DE CONTROLE FINANCEIRO', align='C', ln=True)
        self.set_font('Helvetica', 'I', 9)
        _ = self.cell(0, 5, f'Periodo: {self.titulo_periodo}', align='C', ln=True)
        _ = self.ln(8)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        _ = self.cell(0, 10, f'Gerado em {datetime.today().strftime("%d/%m/%Y")} | Pagina {self.page_no()}', align='C')

@st.cache_data(show_spinner=False)
def gerar_bytes_pdf(df_json, titulo_periodo):
    # Uso explícito de io.StringIO para ler a string JSON sem buscar arquivo em disco
    df_periodo = pd.read_json(io.StringIO(df_json))
    pdf = RelatorioPDF(titulo_periodo)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_text_color(31, 78, 121)
    _ = pdf.cell(0, 7, 'DETALHAMENTO DOS LANCAMENTOS', ln=True)
    _ = pdf.ln(1)

    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(31, 78, 121)
    pdf.set_text_color(255, 255, 255)
    
    larguras = [22, 68, 35, 18, 27, 20]
    colunas = ['Data', 'Descricao', 'Categoria', 'Tipo', 'Valor', 'Status']
    
    for i in range(len(colunas)):
        col = colunas[i]
        w = larguras[i]
        align = 'R' if col == 'Valor' else ('C' if col in ['Data', 'Tipo', 'Status'] else 'L')
        _ = pdf.cell(w, 7, col, fill=True, border=1, align=align)
    _ = pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    
    fill = False
    for _, row in df_periodo.iterrows():
        try:
            data_str = pd.to_datetime(row['data']).strftime('%d/%m/%Y')
        except Exception:
            data_str = str(row['data']) if pd.notna(row['data']) else ""
            
        valor_str = formata_brl(row['valor'])
        pdf.set_fill_color(248, 249, 250) if fill else pdf.set_fill_color(255, 255, 255)
        
        desc = str(row['descricao']) if pd.notna(row['descricao']) else ""
        cat = str(row['categoria']) if pd.notna(row['categoria']) else ""
        tp = str(row['tipo']) if pd.notna(row['tipo']) else ""
        st_val = str(row['status']) if pd.notna(row['status']) else ""

        _ = pdf.cell(larguras[0], 6.5, data_str, border=1, align='C', fill=fill)
        _ = pdf.cell(larguras[1], 6.5, desc[:35], border=1, align='L', fill=fill)
        _ = pdf.cell(larguras[2], 6.5, cat[:18], border=1, align='L', fill=fill)
        _ = pdf.cell(larguras[3], 6.5, tp, border=1, align='C', fill=fill)
        _ = pdf.cell(larguras[4], 6.5, valor_str, border=1, align='R', fill=fill)
        _ = pdf.cell(larguras[5], 6.5, st_val, border=1, align='C', fill=fill)
        _ = pdf.ln()
        fill = not fill

    out = pdf.output(dest='S')
    if isinstance(out, str):
        return out.encode('latin1', errors='ignore')
    return bytes(out)

# --- APLICAÇÃO PRINCIPAL ---
st.title("📊 Controle Financeiro Pessoal")
df = carregar_dados()

# MENU LATERAL
st.sidebar.header("➕ Novo Lançamento")
with st.sidebar.form("form_lancamento", clear_on_submit=True):
    data_input = st.date_input("Data Inicial", datetime.today())
    desc_input = st.text_input("Descrição")
    cat_input = st.selectbox("Categoria", [
        "Alimentação", "Moradia", "Transporte", "Lazer", "Saúde", 
        "Educação", "Salário", "Investimentos", "Outros"
    ])
    tipo_input = st.selectbox("Tipo", ["Entrada", "Saída"])
    valor_input = st.number_input("Valor Total (R$)", min_value=0.01, step=10.0, format="%.2f")
    parcelas_input = st.number_input("Número de Parcelas", min_value=1, max_value=72, value=1, step=1)
    status_input = st.selectbox("Status da 1ª Parcela", ["Pago", "Pendente"])
    
    submetido = st.form_submit_button("💾 Salvar Lançamento", use_container_width=True)
    if submetido:
        if desc_input.strip() == "":
            st.sidebar.error("Preencha a descrição.")
        else:
            salvar_lancamento(data_input, desc_input, cat_input, tipo_input, valor_input, status_input, parcelas_input)
            st.sidebar.success("Lançamento salvo!")
            st.rerun()

# ABAS
aba1, aba2, aba3, aba4, aba5 = st.tabs([
    "📈 Visão Geral", 
    "📝 Gerenciar Registros", 
    "🤖 Assistente IA", 
    "📄 Relatórios PDF", 
    "⚙️ Configurações"
])

meses_nome = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril", 5: "Maio", 6: "Junho",
    7: "Julho", 8: "Agosto", 9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
}

# ABA 1: VISÃO GERAL
with aba1:
    st.subheader("Painel Geral")
    if df.empty:
        st.info("Nenhum lançamento cadastrado.")
    else:
        df['ano'] = df['data'].dt.year
        df['mes'] = df['data'].dt.month
        
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            anos_disp = sorted(df['ano'].dropna().unique().astype(int), reverse=True)
            ano_sel = st.selectbox("Selecione o Ano", anos_disp, key="vg_ano")
        with c_f2:
            df_ano = df[df['ano'] == ano_sel]
            meses_disp = sorted(df_ano['mes'].dropna().unique().astype(int))
            meses_opcoes = [meses_nome[m] for m in meses_disp if m in meses_nome]
            mes_sel_nome = st.selectbox("Selecione o Mês", meses_opcoes, key="vg_mes")
            mes_sel = [k for k, v in meses_nome.items() if v == mes_sel_nome][0]
            
        df_filtrado = df[(df['ano'] == ano_sel) & (df['mes'] == mes_sel)]
        
        ent = df_filtrado[df_filtrado['tipo'] == 'Entrada']['valor'].sum()
        sai = df_filtrado[df_filtrado['tipo'] == 'Saída']['valor'].sum()
        saldo = ent - sai
        pendente = df_filtrado[df_filtrado['status'] == 'Pendente']['valor'].sum()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.markdown(f'<div class="kpi-card kpi-card-entrada"><div class="kpi-title">💵 Entradas</div><div class="kpi-value">{formata_brl(ent)}</div></div>', unsafe_allow_html=True)
        m2.markdown(f'<div class="kpi-card kpi-card-saida"><div class="kpi-title">💸 Saídas</div><div class="kpi-value">{formata_brl(sai)}</div></div>', unsafe_allow_html=True)
        m3.markdown(f'<div class="kpi-card kpi-card-saldo"><div class="kpi-title">🏦 Saldo Líquido</div><div class="kpi-value">{formata_brl(saldo)}</div></div>', unsafe_allow_html=True)
        m4.markdown(f'<div class="kpi-card kpi-card-pendente"><div class="kpi-title">⏳ A Receber / Pagar</div><div class="kpi-value">{formata_brl(pendente)}</div></div>', unsafe_allow_html=True)
        
        st.divider()
        cg1, cg2 = st.columns(2)
        with cg1:
            st.subheader("Despesas por Categoria")
            df_saida = df_filtrado[df_filtrado['tipo'] == 'Saída']
            if not df_saida.empty:
                fig_cat = px.pie(df_saida, names='categoria', values='valor', hole=0.45)
                st.plotly_chart(fig_cat, use_container_width=True)
            else:
                st.write("Sem saídas no período.")
                
        with cg2:
            st.subheader("Entradas vs Saídas")
            if not df_filtrado.empty:
                fig_bar = px.bar(
                    df_filtrado.groupby('tipo')['valor'].sum().reset_index(),
                    x='tipo', y='valor', color='tipo',
                    color_discrete_map={'Entrada': '#2ecc71', 'Saída': '#e74c3c'}
                )
                st.plotly_chart(fig_bar, use_container_width=True)

# ABA 2: GERENCIAR
with aba2:
    st.subheader("Lançamentos Registrados")
    if df.empty:
        st.info("Nenhum dado encontrado.")
    else:
        df_exibir = pd.DataFrame({
            'ID': df['id'],
            'Data': df['data'].dt.strftime('%d/%m/%Y'),
            'Descrição': df['descricao'],
            'Categoria': df['categoria'],
            'Tipo': df['tipo'],
            'Valor': df['valor'].apply(formata_brl),
            'Status': df['status']
        })
        
        st.dataframe(df_exibir, use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🗑️ Excluir Lançamento")
        col_e1, col_e2 = st.columns([3, 1])
        with col_e1:
            id_excluir = st.number_input("Digite o ID do lançamento:", min_value=1, step=1)
        with col_e2:
            st.write("")
            st.write("")
            if st.button("Confirmar Exclusão", use_container_width=True):
                excluir_lancamento(id_excluir)
                st.success(f"Registro #{id_excluir} excluído!")
                st.rerun()

# ABA 3: IA
with aba3:
    st.subheader("🤖 Consultar IA sobre Finanças")
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        prompt_user = st.text_area("Faça uma pergunta sobre a sua situação financeira:")
        if st.button("💡 Analisar com IA"):
            if prompt_user.strip() != "":
                contexto_dados = df.to_csv(index=False)
                prompt_completo = f"Analise as finanças:\n{contexto_dados}\nPergunta: {prompt_user}"
                with st.spinner("Analisando..."):
                    try:
                        model = genai.GenerativeModel('gemini-2.5-flash')
                        resposta = model.generate_content(prompt_completo)
                        txt = resposta.text
                        st.markdown("### Resposta:")
                        st.write(txt)
                        
                        tts = gTTS(text=txt, lang='pt', tld='com.br')
                        sound_file = io.BytesIO()
                        tts.write_to_fp(sound_file)
                        st.audio(sound_file, format='audio/mp3')
                    except Exception as e:
                        st.error(f"Erro na IA: {e}")
            else:
                st.warning("Escreva uma pergunta.")
    else:
        st.warning("Chave GEMINI_API_KEY não configurada nos secrets.")

# ABA 4: RELATÓRIOS PDF
with aba4:
    st.subheader("📋 Gerar e Baixar Relatório PDF")
    if df.empty:
        st.info("Sem dados para relatório.")
    else:
        df['ano'] = df['data'].dt.year
        df['mes'] = df['data'].dt.month
        
        cr1, cr2, cr3 = st.columns(3)
        with cr1:
            opcao_periodo = st.radio("Filtro", ["Mensal", "Anual"])
        with cr2:
            anos_p = sorted(df['ano'].dropna().unique().astype(int), reverse=True)
            ano_pdf = st.selectbox("Ano", anos_p, key="pdf_ano")
        with cr3:
            if opcao_periodo == "Mensal":
                df_ano_p = df[df['ano'] == ano_pdf]
                meses_p = sorted(df_ano_p['mes'].dropna().unique().astype(int))
                meses_opc = [meses_nome[m] for m in meses_p if m in meses_nome]
                if meses_opc:
                    mes_pdf_nome = st.selectbox("Mês", meses_opc, key="pdf_mes")
                    mes_pdf = [k for k, v in meses_nome.items() if v == mes_pdf_nome][0]
                else:
                    mes_pdf_nome = "Janeiro"
                    mes_pdf = 1

        if opcao_periodo == "Mensal":
            df_pdf = df[(df['ano'] == ano_pdf) & (df['mes'] == mes_pdf)].copy()
            tit_doc = f"{mes_pdf_nome} de {ano_pdf}"
        else:
            df_pdf = df[df['ano'] == ano_pdf].copy()
            tit_doc = f"Ano Completo {ano_pdf}"

        st.subheader("📋 Tabela do Relatório")
        
        df_tabela_pdf = pd.DataFrame({
            'Data': df_pdf['data'].dt.strftime('%d/%m/%Y'),
            'Descrição': df_pdf['descricao'],
            'Categoria': df_pdf['categoria'],
            'Tipo': df_pdf['tipo'],
            'Valor': df_pdf['valor'].apply(formata_brl),
            'Status': df_pdf['status']
        })
        
        st.dataframe(df_tabela_pdf, use_container_width=True, hide_index=True)
        st.divider()

        df_json = df_pdf.to_json()
        pdf_bytes = gerar_bytes_pdf(df_json, tit_doc)
        
        st.download_button(
            label="📥 Baixar Relatório PDF",
            data=pdf_bytes,
            file_name=f"relatorio_financeiro_{ano_pdf}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

# ABA 5: CONFIGURAÇÕES
with aba5:
    st.subheader("⚙️ Status do Sistema")
    st.success("Conexão ativa com o banco PostgreSQL.")
    st.write(f"Total de registros armazenados: **{len(df)}**")