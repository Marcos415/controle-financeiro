import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import plotly.express as px
from weasyprint import HTML
import json

# ==========================================================
# CONFIGURAÇÃO GOOGLE SHEETS (SUPORTE LOCAL E NUVEM)
# ==========================================================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def conectar_google_sheets():
    """Conecta no Google Sheets usando Secrets (Nuvem) ou credentials.json (Local)"""
    if "gcp_service_account" in st.secrets:
        # Puxa das Secrets do Streamlit Cloud
        creds_dict = json.loads(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    else:
        # Puxa do arquivo local
        creds = Credentials.from_service_account_file("credentials.json", scopes=SCOPES)
    
    client = gspread.authorize(creds)
    planilha = client.open("Controle Financeiro")
    return planilha.worksheet("Transacoes")

try:
    aba = conectar_google_sheets()
except Exception as e:
    st.error("Erro ao conectar com o Google Sheets. Verifique suas credenciais e permissões na planilha.")
    st.stop()

# ==========================================================
# FUNÇÕES DE MANIPULAÇÃO DE DADOS
# ==========================================================
def carregar_dados():
    dados = aba.get_all_records()
    if len(dados) == 0:
        return pd.DataFrame(
            columns=["Data", "Descricao", "Categoria", "Tipo", "Valor"]
        )

    df = pd.DataFrame(dados)
    df["Data"] = pd.to_datetime(df["Data"], errors='coerce')
    df["Valor"] = pd.to_numeric(df["Valor"], errors='coerce').fillna(0.0)
    df = df.dropna(subset=["Data"])
    return df

def salvar_transacao(data, descricao, categoria, tipo, valor):
    aba.append_row([
        str(data),
        descricao,
        categoria,
        tipo,
        valor
    ])

def colorir_tipo(val):
    if val == "Saída":
        return 'color: #ff2b2b; font-weight: bold;'
    elif val == "Entrada":
        return 'color: #00c853; font-weight: bold;'
    return ''

def gerar_pdf_relatorio(df_relatorio, titulo_periodo, entradas_tot, saidas_tot, saldo_tot):
    """Gera o arquivo PDF do relatório financeiro"""
    linhas_html = ""
    for _, row in df_relatorio.iterrows():
        data_str = row["Data"].strftime('%d/%m/%Y')
        cor_tipo = "#ff2b2b" if row["Tipo"] == "Saída" else "#00c853"
        linhas_html += f"""
        <tr>
            <td>{data_str}</td>
            <td>{row["Descricao"]}</td>
            <td>{row["Categoria"]}</td>
            <td style="color: {cor_tipo}; font-weight: bold;">{row["Tipo"]}</td>
            <td style="text-align: right;">R$ {row["Valor"]:,.2f}</td>
        </tr>
        """

    cor_saldo = "#00c853" if saldo_tot >= 0 else "#ff2b2b"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>Relatório Financeiro</title>
        <style>
            @page {{ size: A4; margin: 15mm; }}
            body {{ font-family: Arial, sans-serif; color: #333; margin: 0; padding: 0; }}
            .header {{ border-bottom: 2px solid #00c853; padding-bottom: 10px; margin-bottom: 20px; }}
            .header h1 {{ margin: 0; color: #1a1a1a; font-size: 22px; }}
            .header p {{ margin: 5px 0 0 0; color: #666; font-size: 13px; }}
            .cards {{ display: table; width: 100%; margin-bottom: 25px; }}
            .card {{ display: table-cell; width: 32%; background-color: #f8f9fa; border: 1px solid #e9ecef; border-radius: 6px; padding: 12px; text-align: center; }}
            .card-title {{ font-size: 12px; color: #666; text-transform: uppercase; margin-bottom: 5px; }}
            .card-value {{ font-size: 18px; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 12px; }}
            th {{ background-color: #f1f3f5; color: #495057; text-align: left; padding: 8px; border-bottom: 2px solid #dee2e6; }}
            td {{ padding: 8px; border-bottom: 1px solid #e9ecef; }}
            .footer {{ margin-top: 30px; text-align: center; font-size: 10px; color: #888; border-top: 1px solid #eee; padding-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>📊 Relatório Financeiro</h1>
            <p><strong>Período:</strong> {titulo_periodo} | <strong>Gerado em:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M')}</p>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-title">Total Entradas</div>
                <div class="card-value" style="color: #00c853;">R$ {entradas_tot:,.2f}</div>
            </div>
            <div class="card" style="margin-left: 2%;">
                <div class="card-title">Total Saídas</div>
                <div class="card-value" style="color: #ff2b2b;">R$ {saidas_tot:,.2f}</div>
            </div>
            <div class="card" style="margin-left: 2%;">
                <div class="card-title">Saldo do Período</div>
                <div class="card-value" style="color: {cor_saldo};">R$ {saldo_tot:,.2f}</div>
            </div>
        </div>

        <h3>Detalhamento das Transações</h3>
        <table>
            <thead>
                <tr>
                    <th>Data</th>
                    <th>Descrição</th>
                    <th>Categoria</th>
                    <th>Tipo</th>
                    <th style="text-align: right;">Valor</th>
                </tr>
            </thead>
            <tbody>
                {linhas_html}
            </tbody>
        </table>

        <div class="footer">
            Sistema de Controle Financeiro • Gerado automaticamente
        </div>
    </body>
    </html>
    """
    
    return HTML(string=html_content).write_pdf()

# ==========================================================
# INTERFACE STREAMLIT
# ==========================================================
st.set_page_config(page_title="Controle Financeiro", layout="wide")
st.title("💰 Controle Financeiro")

# --- FORMULÁRIO DE CADASTRO ---
with st.expander("➕ Nova Transação", expanded=True):
    col1, col2 = st.columns(2)
    with col1:
        data = st.date_input("Data")
        descricao = st.text_input("Descrição")
        categoria = st.text_input("Categoria")
    with col2:
        tipo = st.selectbox("Tipo", ["Entrada", "Saída"])
        valor = st.number_input("Valor", min_value=0.0, format="%.2f")

if st.button("Salvar Transação"):
    if descricao and valor > 0:
        salvar_transacao(data, descricao, categoria, tipo, valor)
        st.success("Transação salva com sucesso!")
        st.rerun()
    else:
        st.warning("Preencha a descrição e um valor maior que zero.")

# --- DASHBOARD E FILTROS ---
df = carregar_dados()

if not df.empty:
    entradas = df[df["Tipo"] == "Entrada"]["Valor"].sum()
    saidas = df[df["Tipo"] == "Saída"]["Valor"].sum()
    saldo = entradas - saidas

    st.subheader("📊 Dashboard")
    c1, c2, c3 = st.columns(3)

    c1.metric("Entradas", f"R$ {entradas:,.2f}")
    c2.metric("Saídas (Despesas)", f"R$ {saidas:,.2f}")

    if saldo >= 0:
        c3.success(f"Saldo Atual: R$ {saldo:,.2f}")
    else:
        c3.error(f"Saldo Atual: R$ {saldo:,.2f}")

    # --- FILTROS ---
    st.subheader("Filtros")
    anos_disponiveis = sorted(df["Data"].dt.year.unique(), reverse=True)
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        ano = st.selectbox("Ano", anos_disponiveis)
    with col_f2:
        meses = ["Todos", "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", 
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes = st.selectbox("Mês", meses)

    df_filtrado = df[df["Data"].dt.year == ano].copy()

    cores_mapa = {
        "Entrada": "#00c853",
        "Saída": "#ff2b2b"
    }

    # --- GRÁFICO DINÂMICO ---
    if mes == "Todos":
        df_filtrado["Eixo_X"] = df_filtrado["Data"].dt.to_period("M").astype(str)
        resumo = df_filtrado.groupby(["Eixo_X", "Tipo"])["Valor"].sum().reset_index()
        titulo_grafico = f"Entradas vs Saídas por Mês ({ano})"
        label_x = "Mês"
        titulo_periodo = f"Ano de {ano}"
    else:
        numero_mes = meses.index(mes)
        df_filtrado = df_filtrado[df_filtrado["Data"].dt.month == numero_mes]
        df_filtrado["Eixo_X"] = df_filtrado["Data"].dt.strftime('%d/%m')
        resumo = df_filtrado.groupby(["Eixo_X", "Tipo"])["Valor"].sum().reset_index()
        titulo_grafico = f"Entradas vs Saídas por Dia - {mes}/{ano}"
        label_x = "Dia"
        titulo_periodo = f"{mes} / {ano}"

    if not resumo.empty:
        grafico = px.bar(
            resumo,
            x="Eixo_X",
            y="Valor",
            color="Tipo",
            color_discrete_map=cores_mapa,
            barmode="group",
            title=titulo_grafico,
            labels={"Eixo_X": label_x, "Valor": "Valor (R$)"}
        )
        grafico.update_xaxes(type='category')
        st.plotly_chart(grafico, use_container_width=True)
    else:
        st.info("Nenhuma transação encontrada para o período selecionado.")

    # --- HISTÓRICO E EXPORTAÇÃO DE PDF ---
    st.subheader("📄 Histórico")
    
    col_search, col_pdf = st.columns([3, 1])
    with col_search:
        busca = st.text_input("Pesquisar descrição")

    if busca:
        df_filtrado = df_filtrado[
            df_filtrado["Descricao"].str.contains(busca, case=False, na=False)
        ]

    ent_f = df_filtrado[df_filtrado["Tipo"] == "Entrada"]["Valor"].sum()
    sai_f = df_filtrado[df_filtrado["Tipo"] == "Saída"]["Valor"].sum()
    sal_f = ent_f - sai_f

    pdf_bytes = gerar_pdf_relatorio(
        df_filtrado.sort_values(by="Data"), 
        titulo_periodo, 
        ent_f, 
        sai_f, 
        sal_f
    )

    with col_pdf:
        st.write("")
        st.download_button(
            label="🖨️ Imprimir / Baixar PDF",
            data=pdf_bytes,
            file_name=f"Relatorio_{titulo_periodo.replace(' ', '_').replace('/', '-')}.pdf",
            mime="application/pdf",
            use_container_width=True
        )

    df_exibicao = df_filtrado.copy()
    df_exibicao["Data"] = df_exibicao["Data"].dt.strftime('%d/%m/%Y')

    st.dataframe(
        df_exibicao[["Data", "Descricao", "Categoria", "Tipo", "Valor"]].style.map(
            colorir_tipo, subset=["Tipo"]
        ),
        use_container_width=True
    )
else:
    st.info("Nenhuma transação cadastrada até o momento.")