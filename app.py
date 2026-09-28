import streamlit as st
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

st.set_page_config(page_title="Controle Financeiro", layout="wide")

st.title("💰 Controle Financeiro")

# Navegação por abas
aba1, aba2 = st.tabs(["Lançamento Único", "Lançamento Parcelado / Recorrente"])

with aba1:
    st.header("Novo Lançamento Único")
    # Lógica do Lançamento Único
    col1, col2 = st.columns(2)
    with col1:
        data_unica = st.date_input("Data", value=datetime.today(), key="data_unica")
        descricao_unica = st.text_input("Descrição", key="desc_unica")
        categoria_unica = st.text_input("Categoria", key="cat_unica")
    with col2:
        tipo_unico = st.selectbox("Tipo", ["Entrada", "Saída"], key="tipo_unico")
        valor_unico = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", key="valor_unico")
        status_unico = st.selectbox("Status", ["Pago", "Aberto"], key="status_unico")

    if st.button("Salvar Lançamento Único"):
        st.success("Lançamento único guardado com sucesso!")

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

    # Botão para gerar e salvar as parcelas
    if st.button("Gerar e Salvar Parcelamento"):
        if not descricao:
            st.warning("Por favor, preencha a descrição.")
        else:
            # Cálculo do valor por parcela
            if regra_valor == "Valor Total (Dividir pelas parcelas)":
                valor_parcela = valor_digitado / qtd_parcelas
            else:
                valor_parcela = valor_digitado

            parcelas_geradas = []
            for i in range(int(qtd_parcelas)):
                # Calcula a data de cada parcela (mês a mês)
                data_vencimento = data_1a_parcela + relativedelta(months=i)
                num_parcela_str = f"{i + 1}/{int(qtd_parcelas)}"
                
                # A primeira parcela assume o status selecionado; as demais ficam em 'Aberto'
                st_parcela = status_1a_parcela if i == 0 else "Aberto"
                
                parcelas_geradas.append({
                    "Data": data_vencimento.strftime("%Y-%m-%d"),
                    "Descrição": f"{descricao} ({num_parcela_str})",
                    "Categoria": categoria,
                    "Tipo": tipo,
                    "Valor": round(valor_parcela, 2),
                    "Status": st_parcela
                })
            
            # Exibe a confirmação e a prévia dentro do bloco do botão
            st.success(f"Geradas {int(qtd_parcelas)} parcelas com sucesso!")
            st.dataframe(pd.DataFrame(parcelas_geradas))