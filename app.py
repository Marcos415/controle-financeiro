import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# Configuração da página
st.set_page_config(page_title="Controle Financeiro", layout="wide", page_icon="💰")

# --- ESTILIZAÇÃO CSS AVANÇADA E CLEAN ---
st.markdown("""
    <style>
    /* Remove margens topo da página */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
    }
    
    /* Esconde menu nativo e rodapé do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* KPI Cards - Tema Clean/Light */
    .kpi-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px 18px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
        transition: all 0.25s ease-in-out;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 6px 15px rgba(0, 0, 0, 0.08);
        border-color: #CBD5E1;
    }
    .kpi-title {
        color: #64748B;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 6px;
    }
    .kpi-value {
        color: #1E293B;
        font-size: 1.6rem;
        font-weight: 700;
        margin: 0;
        line-height: 1.2;
    }
    .kpi-sub {
        color: #64748B;
        font-size: 0.75rem;
        margin-top: 8px;
        font-weight: 500;
    }

    /* Estilização Customizada das Abas */
    button[data-baseweb="tab"] {
        border-radius: 8px 8px 0 0 !important;
        padding: 10px 16px !important;
        font-weight: 600 !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #F1F5F9 !important;
        color: #0F172A !important;
        border-bottom: 3px solid #2563EB !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- NAVEGAÇÃO POR ABAS ---
aba1, aba2, aba3, aba4 = st.tabs([
    "➕ Lançamento Único", 
    "🔄 Lançamento Parcelado / Recorrente", 
    "📋 Contas e Baixa de Pagamentos",
    "📅 Relatórios Mensais / Anuais"
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
# ABA 3: EXTRATO E BAIXAS
# -------------------------------------------------------------
with aba3:
    st.header("📋 Gerenciamento de Contas e Baixa de Pagamentos")
    
    df_exibicao = carregar_dados()
    
    if not df_exibicao.empty:
        df_exibicao['datetime'] = pd.to_datetime(df_exibicao['data'])
        df_exibicao['Ano'] = df_exibicao['datetime'].dt.year
        df_exibicao['Mês_Num'] = df_exibicao['datetime'].dt.month
        df_exibicao['Mês_Nome'] = df_exibicao['Mês_Num'].map(meses_pt)

        st.subheader("🔍 Filtros de Busca")
        
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        
        anos_disponiveis = ["Todos"] + sorted(list(df_exibicao['Ano'].unique()), reverse=True)
        with col_f1:
            filtro_ano = st.selectbox("Filtrar por Ano:", anos_disponiveis, key="extrato_ano")
            
        with col_f2:
            if filtro_ano != "Todos":
                meses_disp = [meses_pt[m] for m in sorted(df_exibicao[df_exibicao['Ano'] == filtro_ano]['Mês_Num'].unique())]
                meses_opcoes = ["Todos"] + meses_disp
            else:
                meses_opcoes = ["Todos"] + list(meses_pt.values())
            filtro_mes = st.selectbox("Filtrar por Mês:", meses_opcoes, key="extrato_mes")
            
        with col_f3:
            filtro_status = st.multiselect(
                "Filtrar por Status", 
                options=list(df_exibicao["status"].unique()), 
                default=list(df_exibicao["status"].unique()),
                key="extrato_status"
            )
            
        with col_f4:
            filtro_tipo = st.multiselect(
                "Filtrar por Tipo", 
                options=list(df_exibicao["tipo"].unique()), 
                default=list(df_exibicao["tipo"].unique()),
                key="extrato_tipo"
            )
            
        df_filtrado = df_exibicao[
            (df_exibicao["status"].isin(filtro_status)) & 
            (df_exibicao["tipo"].isin(filtro_tipo))
        ]
        
        if filtro_ano != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Ano'] == filtro_ano]
            
        if filtro_mes != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Mês_Nome'] == filtro_mes]

        st.divider()

        st.subheader("⚡ Dar Baixa ou Alterar Status")
        
        if not df_filtrado.empty:
            col_a1, col_a2, col_a3 = st.columns([4, 2, 2])
            
            opcoes_filtradas = {
                f"ID {row['id']} | {row['data']} | {row['descricao']} - R$ {row['valor']:.2f} [{row['status']}]": row['id']
                for _, row in df_filtrado.iterrows()
            }
            
            with col_a1:
                item_selecionado = st.selectbox(
                    "Selecione o lançamento (baseado nos filtros atuais):",
                    options=list(opcoes_filtradas.keys())
                )
                id_target = opcoes_filtradas[item_selecionado]
                
            with col_a2:
                st.write(" ")
                st.write(" ")
                if st.button("✅ Marcar como PAGO"):
                    atualizar_status(id_target, "Pago")
                    st.success("Status alterado para PAGO!")
                    st.rerun()

            with col_a3:
                st.write(" ")
                st.write(" ")
                if st.button("🗑️ Excluir Lançamento"):
                    excluir_registro(id_target)
                    st.warning("Lançamento excluído com sucesso!")
                    st.rerun()
        else:
            st.info("Nenhum lançamento encontrado para os filtros selecionados.")

        st.divider()
        st.subheader("📊 Extrato de Contas")

        with st.container(height=380):
            st.dataframe(
                df_filtrado[['id', 'data', 'descricao', 'categoria', 'tipo', 'valor', 'status']],
                column_config={
                    "id": "ID",
                    "data": "Data Vencimento",
                    "descricao": "Descrição",
                    "categoria": "Categoria",
                    "tipo": "Tipo",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                    "status": "Status"
                },
                hide_index=True
            )

    else:
        st.info("Nenhum lançamento registrado até o momento.")

# -------------------------------------------------------------
# ABA 4: RELATÓRIOS MENSAIS E ANUAIS
# -------------------------------------------------------------
with aba4:
    st.header("📅 Relatórios e Movimentação por Mês/Ano")
    
    df_relatorio = carregar_dados()
    
    if not df_relatorio.empty:
        df_relatorio['datetime'] = pd.to_datetime(df_relatorio['data'])
        df_relatorio['Ano'] = df_relatorio['datetime'].dt.year
        df_relatorio['Mês_Num'] = df_relatorio['datetime'].dt.month
        df_relatorio['Mês_Nome'] = df_relatorio['Mês_Num'].map(meses_pt)
        
        col_r1, col_r2, col_r3 = st.columns(3)
        
        anos_disponiveis = sorted(df_relatorio['Ano'].unique(), reverse=True)
        with col_r1:
            ano_sel = st.selectbox("Selecione o Ano:", anos_disponiveis, key="rel_ano")
            
        with col_r2:
            opcao_periodo = st.radio("Visão do Relatório:", ["Mensal", "Ano Todo (Acumulado)"], horizontal=True, key="rel_opcao")
            
        with col_r3:
            if opcao_periodo == "Mensal":
                meses_do_ano = [meses_pt[m] for m in sorted(df_relatorio[df_relatorio['Ano'] == ano_sel]['Mês_Num'].unique())]
                mes_sel_nome = st.selectbox("Selecione o Mês:", meses_do_ano, key="rel_mes")
            else:
                mes_sel_nome = "Todos"

        df_filtrado_periodo = df_relatorio[df_relatorio['Ano'] == ano_sel]
        if opcao_periodo == "Mensal" and mes_sel_nome != "Todos":
            df_filtrado_periodo = df_filtrado_periodo[df_filtrado_periodo['Mês_Nome'] == mes_sel_nome]

        st.divider()

        ent_m = df_filtrado_periodo[df_filtrado_periodo['tipo'] == 'Entrada']['valor'].sum()
        sai_m = df_filtrado_periodo[df_filtrado_periodo['tipo'] == 'Saída']['valor'].sum()
        saldo_m = ent_m - sai_m
        aberto_m = df_filtrado_periodo[df_filtrado_periodo['status'] == 'Aberto']['valor'].sum()

        st.subheader(f"📌 Resumo: {mes_sel_nome if opcao_periodo == 'Mensal' else 'Ano ' + str(ano_sel)}")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Entradas no Período", f"R$ {ent_m:,.2f}")
        c2.metric("Saídas no Período", f"R$ {sai_m:,.2f}")
        c3.metric("Saldo do Período", f"R$ {saldo_m:,.2f}")
        c4.metric("A Vencer / Em Aberto", f"R$ {aberto_m:,.2f}")

        st.divider()
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            st.subheader("📊 Entradas vs. Saídas")
            df_totais_tipo = df_filtrado_periodo.groupby('tipo')['valor'].sum().reset_index()
            if not df_totais_tipo.empty:
                st.bar_chart(df_totais_tipo.set_index('tipo'))
            else:
                st.info("Sem dados suficientes para o gráfico.")

        with col_g2:
            st.subheader("🏷️ Saídas por Categoria")
            df_saidas_cat = df_filtrado_periodo[df_filtrado_periodo['tipo'] == 'Saída'].groupby('categoria')['valor'].sum().reset_index()
            if not df_saidas_cat.empty:
                st.bar_chart(df_saidas_cat.set_index('categoria'))
            else:
                st.info("Nenhuma saída registrada no período.")

        st.divider()
        st.subheader("📋 Tabela do Período Selecionado")
        
        df_export = df_filtrado_periodo[['data', 'descricao', 'categoria', 'tipo', 'valor', 'status']].copy()
        
        with st.container(height=350):
            st.dataframe(
                df_export,
                column_config={
                    "data": "Data Vencimento",
                    "descricao": "Descrição",
                    "categoria": "Categoria",
                    "tipo": "Tipo",
                    "valor": st.column_config.NumberColumn("Valor (R$)", format="R$ %.2f"),
                    "status": "Status"
                },
                hide_index=True
            )

        st.divider()
        titulo_doc = f"{mes_sel_nome} de {ano_sel}" if opcao_periodo == "Mensal" else f"Ano Completo {ano_sel}"

        if st.button("⚙️ Gerar Relatório PDF"):
            pdf_data = gerar_pdf_isolado(df_export, titulo_doc, ent_m, sai_m, saldo_m, aberto_m)
            st.session_state['pdf_pronto'] = pdf_data
            st.session_state['pdf_nome'] = f"relatorio_financeiro_{ano_sel}_{mes_sel_nome}.pdf"
            st.rerun()

        if 'pdf_pronto' in st.session_state:
            st.download_button(
                label="📥 Baixar Relatório Profissional em PDF",
                data=st.session_state['pdf_pronto'],
                file_name=st.session_state['pdf_nome'],
                mime="application/pdf"
            )
        
    else:
        st.info("Nenhum dado disponível para gerar relatórios.")