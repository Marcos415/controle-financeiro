import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Configuração da página
st.set_page_config(page_title="Controle Financeiro", layout="wide", page_icon="💰")

# --- CONEXÃO E CRIAÇÃO DO BANCO DE DADOS ---
def get_connection():
    conn = sqlite3.connect("financeiro.db")
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS lancamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data TEXT,
            descricao TEXT,
            categoria TEXT,
            tipo TEXT,
            valor REAL,
            status TEXT
        )
    ''')
    conn.commit()
    conn.close()

def carregar_dados():
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data DESC", conn)
    conn.close()
    return df

def salvar_lancamentos(df_novos):
    conn = get_connection()
    df_novos.to_sql("lancamentos", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()

# Inicializa o banco de dados
init_db()

st.title("💰 Controle Financeiro Integrado")

# --- RESUMO PAINEL DE MÉTRICAS (METRICS) ---
df_todos = carregar_dados()

st.markdown("### 📊 Visão Geral do Caixa")
if not df_todos.empty:
    total_entradas = df_todos[df_todos['tipo'] == 'Entrada']['valor'].sum()
    total_saidas = df_todos[df_todos['tipo'] == 'Saída']['valor'].sum()
    saldo_atual = total_entradas - total_saidas
    
    em_aberto = df_todos[df_todos['status'] == 'Aberto']['valor'].sum()
    pago_fechado = df_todos[df_todos['status'] == 'Pago']['valor'].sum()

    col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
    col_m1.metric("Total Entradas", f"R$ {total_entradas:,.2f}")
    col_m2.metric("Total Saídas", f"R$ {total_saidas:,.2f}")
    col_m3.metric("Saldo Líquido", f"R$ {saldo_atual:,.2f}")
    col_m4.metric("Contas em Aberto ⚠️", f"R$ {em_aberto:,.2f}")
    col_m5.metric("Contas Pagas/Fechadas ✅", f"R$ {pago_fechado:,.2f}")
else:
    st.info("Nenhum lançamento registado até ao momento.")

st.divider()

# --- NAVEGAÇÃO POR ABAS ---
aba1, aba2, aba3 = st.tabs([
    "➕ Lançamento Único", 
    "🔄 Lançamento Parcelado / Recorrente", 
    "📋 Contas e Extrato Geral"
])

# -------------------------------------------------------------
# ABA 1: LANÇAMENTO ÚNICO
# -------------------------------------------------------------
with aba1:
    st.header("Novo Lançamento Único")
    col1, col2 = st.columns(2)
    
    with col1:
        data_unica = st.date_input("Data", value=datetime.today(), key="data_unica")
        descricao_unica = st.text_input("Descrição", key="desc_unica")
        categoria_unica = st.text_input("Categoria", key="cat_unica")
        
    with col2:
        tipo_unico = st.selectbox("Tipo", ["Saída", "Entrada"], key="tipo_unico")
        valor_unico = st.number_input("Valor (R$)", min_value=0.01, value=100.00, format="%.2f", key="valor_unico")
        status_unico = st.selectbox("Status", ["Aberto", "Pago"], key="status_unico")

    if st.button("Salvar Lançamento Único"):
        if not descricao_unica:
            st.warning("Preencha a descrição do lançamento.")
        else:
            novo_registro = pd.DataFrame([{
                "data": data_unica.strftime("%Y-%m-%d"),
                "descricao": descricao_unica,
                "categoria": categoria_unica,
                "tipo": tipo_unico,
                "valor": float(valor_unico),
                "status": status_unico
            }])
            salvar_lancamentos(novo_registro)
            st.success("Lançamento guardado com sucesso!")
            st.rerun()

# -------------------------------------------------------------
# ABA 2: LANÇAMENTO PARCELADO / RECORRENTE
# -------------------------------------------------------------
with aba2:
    st.header("Novo Lançamento Parcelado / Recorrente")
    
    col_left, col_right = st.columns(2)
    
    with col_left:
        data_1a_parcela = st.date_input("Data da 1ª Parcela", value=datetime.today(), key="data_parc")
        descricao = st.text_input("Descrição (ex: Compra Notebook)", key="desc_parc")
        categoria = st.text_input("Categoria", key="cat_parc")
        tipo = st.selectbox("Tipo", ["Saída", "Entrada"], key="tipo_parc")

    with col_right:
        regra_valor = st.radio(
            "Regra de Valor:",
            ["Valor Total (Dividir pelas parcelas)", "Valor Fixado por Parcela"],
            key="regra_valor"
        )
        valor_digitado = st.number_input("Valor Digitado (R$)", min_value=0.01, value=2000.00, step=100.0, format="%.2f", key="valor_digitado")
        qtd_parcelas = st.number_input("Quantidade de Parcelas", min_value=1, value=12, step=1, key="qtd_parcelas")
        status_1a_parcela = st.selectbox("Status da 1ª Parcela", ["Aberto", "Pago"], key="status_parc")

    if st.button("Gerar e Salvar Parcelamento"):
        if not descricao:
            st.warning("Por favor, preencha a descrição do parcelamento.")
        else:
            if regra_valor == "Valor Total (Dividir pelas parcelas)":
                valor_parcela = valor_digitado / qtd_parcelas
            else:
                valor_parcela = valor_digitado

            parcelas_geradas = []
            for i in range(int(qtd_parcelas)):
                data_vencimento = data_1a_parcela + relativedelta(months=i)
                num_parcela_str = f"{i + 1}/{int(qtd_parcelas)}"
                
                st_parcela = status_1a_parcela if i == 0 else "Aberto"
                
                parcelas_geradas.append({
                    "data": data_vencimento.strftime("%Y-%m-%d"),
                    "descricao": f"{descricao} ({num_parcela_str})",
                    "categoria": categoria,
                    "tipo": tipo,
                    "valor": round(valor_parcela, 2),
                    "status": st_parcela
                })
            
            df_parcelas = pd.DataFrame(parcelas_geradas)
            salvar_lancamentos(df_parcelas)
            
            st.success(f"Geradas e gravadas {int(qtd_parcelas)} parcelas com sucesso!")
            st.rerun()

# -------------------------------------------------------------
# ABA 3: EXTRATO GERAL E CONTAS
# -------------------------------------------------------------
with aba3:
    st.header("📋 Histórico de Lançamentos e Contas")
    
    df_exibicao = carregar_dados()
    
    if not df_exibicao.empty:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_status = st.multiselect("Filtrar por Status", options=df_exibicao["status"].unique(), default=df_exibicao["status"].unique())
        with col_f2:
            filtro_tipo = st.multiselect("Filtrar por Tipo", options=df_exibicao["tipo"].unique(), default=df_exibicao["tipo"].unique())
            
        df_filtrado = df_exibicao[
            (df_exibicao["status"].isin(filtro_status)) & 
            (df_exibicao["tipo"].isin(filtro_tipo))
        ]
        
        st.dataframe(
            df_filtrado[['id', 'data', 'descricao', 'categoria', 'tipo', 'valor', 'status']], 
            use_container_width=True
        )
    else:
        st.info("Nenhum registro encontrado.")