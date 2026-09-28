import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# Configuração da página
st.set_page_config(page_title="Controle Financeiro", layout="wide", page_icon="💰")

# --- CONEXÃO E CRIAÇÃO DO BANCO DE DADOS ---
def get_connection():
    return sqlite3.connect("financeiro.db")

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
    df = pd.read_sql_query("SELECT * FROM lancamentos ORDER BY data ASC, id ASC", conn)
    conn.close()
    return df

def salvar_lancamentos(df_novos):
    conn = get_connection()
    df_novos.to_sql("lancamentos", conn, if_exists="append", index=False)
    conn.commit()
    conn.close()

def atualizar_status(id_registro, novo_status):
    conn = get_connection()
    c = conn.cursor()
    c.execute("UPDATE lancamentos SET status = ? WHERE id = ?", (novo_status, id_registro))
    conn.commit()
    conn.close()

def excluir_registro(id_registro):
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM lancamentos WHERE id = ?", (id_registro,))
    conn.commit()
    conn.close()

# --- CLASSE PARA GERAÇÃO DO PDF PROFISSIONAL ---
class RelatorioPDF(FPDF):
    def __init__(self, titulo_periodo):
        super().__init__(orientation='P', unit='mm', format='A4')
        self.titulo_periodo = titulo_periodo

    def header(self):
        self.set_fill_color(31, 78, 121)
        self.rect(0, 0, 210, 25, 'F')
        self.set_font('Helvetica', 'B', 16)
        self.set_text_color(255, 255, 255)
        _ = self.cell(0, 8, 'RELATÓRIO FINANCEIRO', align='C', new_x='LMARGIN', new_y='NEXT')
        self.set_font('Helvetica', 'I', 10)
        _ = self.cell(0, 5, f'Período: {self.titulo_periodo}', align='C', new_x='LMARGIN', new_y='NEXT')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.set_text_color(128, 128, 128)
        _ = self.cell(0, 10, f'Gerado em {datetime.today().strftime("%d/%m/%Y às %H:%M")} | Página {self.page_no()}/{{nb}}', align='C')

def construir_pdf_bytes(df_periodo, titulo_periodo, total_ent, total_sai, saldo, aberto):
    pdf = RelatorioPDF(titulo_periodo)
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Quadro Resumo
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(31, 78, 121)
    _ = pdf.cell(0, 8, 'RESUMO DO PERÍODO', new_x='LMARGIN', new_y='NEXT')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(0, 0, 0)
    
    pdf.set_fill_color(240, 243, 246)
    pdf.set_draw_color(200, 200, 200)
    pdf.rect(10, pdf.get_y(), 190, 20, 'FD')
    
    y_start = pdf.get_y() + 4
    pdf.set_y(y_start)
    _ = pdf.cell(47.5, 6, f'Entradas: R$ {total_ent:,.2f}', align='C')
    _ = pdf.cell(47.5, 6, f'Saídas: R$ {total_sai:,.2f}', align='C')
    _ = pdf.cell(47.5, 6, f'Saldo Líquido: R$ {saldo:,.2f}', align='C')
    _ = pdf.cell(47.5, 6, f'Em Aberto: R$ {aberto:,.2f}', align='C')
    
    pdf.set_y(y_start + 20)

    # Tabela
    pdf.set_font('Helvetica', 'B', 11)
    pdf.set_text_color(31, 78, 121)
    _ = pdf.cell(0, 8, 'DETALHAMENTO DOS LANÇAMENTOS', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(2)

    pdf.set_font('Helvetica', 'B', 9)
    pdf.set_fill_color(31, 78, 121)
    pdf.set_text_color(255, 255, 255)
    
    larguras = [25, 65, 35, 20, 25, 20]
    colunas = ['Data', 'Descrição', 'Categoria', 'Tipo', 'Valor', 'Status']
    
    for idx, col in enumerate(colunas):
        align = 'R' if col == 'Valor' else ('C' if col in ['Data', 'Tipo', 'Status'] else 'L')
        _ = pdf.cell(larguras[idx], 8, col, fill=True, border=1, align=align)
    pdf.ln()

    pdf.set_font('Helvetica', '', 8)
    pdf.set_text_color(0, 0, 0)
    
    fill = False
    for _, row in df_periodo.iterrows():
        try:
            data_str = datetime.strptime(str(row['data']), '%Y-%m-%d').strftime('%d/%m/%Y')
        except Exception:
            data_str = str(row['data'])
            
        valor_str = f"R$ {row['valor']:,.2f}"
        
        pdf.set_fill_color(245, 247, 250) if fill else pdf.set_fill_color(255, 255, 255)
        
        _ = pdf.cell(larguras[0], 7, data_str, border=1, align='C', fill=fill)
        _ = pdf.cell(larguras[1], 7, str(row['descricao'])[:35], border=1, align='L', fill=fill)
        _ = pdf.cell(larguras[2], 7, str(row['categoria'])[:20], border=1, align='L', fill=fill)
        _ = pdf.cell(larguras[3], 7, str(row['tipo']), border=1, align='C', fill=fill)
        _ = pdf.cell(larguras[4], 7, valor_str, border=1, align='R', fill=fill)
        _ = pdf.cell(larguras[5], 7, str(row['status']), border=1, align='C', fill=fill)
        pdf.ln()
        fill = not fill

    return bytes(pdf.output())

# Inicializa o banco de dados
init_db()

st.title("💰 Controle Financeiro Integrado")

# --- RESUMO PAINEL DE MÉTRICAS ---
df_todos = carregar_dados()

st.markdown("### 📊 Visão Geral do Caixa (Geral)")
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
    st.info("Nenhum lançamento registrado até o momento.")

st.divider()

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
        st.subheader("⚡ Dar Baixa ou Alterar Status")
        col_a1, col_a2, col_a3 = st.columns([4, 2, 2])
        
        opcoes_todas = {
            f"ID {row['id']} | {row['data']} | {row['descricao']} - R$ {row['valor']:.2f} [{row['status']}]": row['id']
            for _, row in df_exibicao.iterrows()
        }
        
        with col_a1:
            item_selecionado = st.selectbox(
                "Selecione o lançamento:",
                options=list(opcoes_todas.keys())
            )
            id_target = opcoes_todas[item_selecionado]
            
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

        st.divider()
        st.subheader("📊 Extrato de Contas")

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_status = st.multiselect("Filtrar por Status", options=list(df_exibicao["status"].unique()), default=list(df_exibicao["status"].unique()))
        with col_f2:
            filtro_tipo = st.multiselect("Filtrar por Tipo", options=list(df_exibicao["tipo"].unique()), default=list(df_exibicao["tipo"].unique()))
            
        df_filtrado = df_exibicao[
            (df_exibicao["status"].isin(filtro_status)) & 
            (df_exibicao["tipo"].isin(filtro_tipo))
        ]

        with st.container(height=350):
            st.dataframe(
                df_filtrado,
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
        
        meses_pt = {
            1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
            5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
            9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro"
        }
        df_relatorio['Mês_Nome'] = df_relatorio['Mês_Num'].map(meses_pt)
        
        # Filtros
        col_r1, col_r2, col_r3 = st.columns(3)
        
        anos_disponiveis = sorted(df_relatorio['Ano'].unique(), reverse=True)
        with col_r1:
            ano_sel = st.selectbox("Selecione o Ano:", anos_disponiveis)
            
        with col_r2:
            opcao_periodo = st.radio("Visão do Relatório:", ["Mensal", "Ano Todo (Acumulado)"], horizontal=True)
            
        with col_r3:
            if opcao_periodo == "Mensal":
                meses_do_ano = [meses_pt[m] for m in sorted(df_relatorio[df_relatorio['Ano'] == ano_sel]['Mês_Num'].unique())]
                mes_sel_nome = st.selectbox("Selecione o Mês:", meses_do_ano)
            else:
                mes_sel_nome = "Todos"

        # Filtragem dos Dados
        df_filtrado_periodo = df_relatorio[df_relatorio['Ano'] == ano_sel]
        if opcao_periodo == "Mensal" and mes_sel_nome != "Todos":
            df_filtrado_periodo = df_filtrado_periodo[df_filtrado_periodo['Mês_Nome'] == mes_sel_nome]

        st.divider()

        # Métricas do Período
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

        # Gráficos na tela
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

        # Download do PDF sem vazamento de retorno no Streamlit
        titulo_doc = f"{mes_sel_nome} de {ano_sel}" if opcao_periodo == "Mensal" else f"Ano Completo {ano_sel}"
        bytes_pdf = construir_pdf_bytes(df_export, titulo_doc, ent_m, sai_m, saldo_m, aberto_m)

        st.download_button(
            label="📄 Baixar Relatório Profissional em PDF",
            data=bytes_pdf,
            file_name=f"relatorio_financeiro_{ano_sel}_{mes_sel_nome}.pdf",
            mime="application/pdf"
        )
        
    else:
        st.info("Nenhum dado disponível para gerar relatórios.")