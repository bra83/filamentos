import streamlit as st
import pandas as pd
import plotly.express as px
import re
from thefuzz import process, fuzz

# === CONFIGURAÇÃO DA PÁGINA ===
st.set_page_config(page_title="BCRUZ 3D Market", layout="wide", page_icon="🚀")

# === LINK DA PLANILHA (CSV PUBLICADO) ===
DEFAULT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRIXvkHql1pQlHUKnmldEbGlU6GFOmimyin4yLAuhrtuCIPb7ist587wNOYKs_L8RJF_MpRiq2e2mgu/pub?gid=444101812&single=true&output=csv"

# === FUNÇÕES ===
def limpar_preco(valor):
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    texto = str(valor).upper().replace("R$", "").strip()
    texto = re.sub(r'[^\d,.]', '', texto)
    try:
        if ',' in texto:
            texto = texto.replace('.', '').replace(',', '.')
        return float(texto)
    except:
        return 0.0

def limpar_vendas(valor):
    if pd.isna(valor): return 0
    texto = str(valor).lower().strip()
    multiplicador = 1
    if 'mil' in texto or 'k' in texto:
        multiplicador = 1000
    texto = re.sub(r'[^\d,.]', '', texto)
    try:
        if ',' in texto:
            texto = texto.replace('.', '').replace(',', '.')
        return int(float(texto) * multiplicador)
    except:
        return 0

@st.cache_data(ttl=30)
def carregar_dados(url):
    try:
        df = pd.read_csv(url, on_bad_lines='skip')
        df.columns = [str(c).upper().strip() for c in df.columns]
        
        # Identificação inteligente de colunas
        col_preco = next((c for c in df.columns if any(x in c for x in ['PREÇ', 'PRICE', '(R$)'])), None)
        col_nome = next((c for c in df.columns if any(x in c for x in ['PRODUT', 'NOME', 'TITULO'])), None)
        col_vendas = next((c for c in df.columns if any(x in c for x in ['VENDA', 'SOLD', 'REVIEW'])), None)
        col_link = next((c for c in df.columns if any(x in c for x in ['LINK', 'URL'])), None)
        
        if col_preco and col_nome:
            df['Preco_Num'] = df[col_preco].apply(limpar_preco)
            df['Produto_Nome'] = df[col_nome]
            df['Link_Url'] = df[col_link] if col_link else "#"
            
            if col_vendas:
                df['Vendas_Num'] = df[col_vendas].apply(limpar_vendas)
            else:
                df['Vendas_Num'] = 0
            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar CSV: {e}")
        return pd.DataFrame()

# === INTERFACE ===
st.title("🚀 Painel de Inteligência de Mercado 3D")

with st.sidebar:
    st.header("⚙️ Controle")
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    busca_principal = st.text_input("🔍 Filtro Geral:", placeholder="Ex: Vaso")

df = carregar_dados(DEFAULT_URL)

if not df.empty:
    df_foco = df.copy()
    if busca_principal:
        df_foco = df_foco[df_foco['Produto_Nome'].str.contains(busca_principal, case=False, na=False)]

    # Métricas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Produtos Listados", len(df_foco))
    if len(df_foco) > 0:
        media = df_foco['Preco_Num'].mean()
        c2.metric("Preço Médio", f"R$ {media:.2f}")
        c3.metric("Menor Preço", f"R$ {df_foco['Preco_Num'].min():.2f}")
        c4.metric("Maior Preço", f"R$ {df_foco['Preco_Num'].max():.2f}")

    st.markdown("---")
    
    tab1, tab2, tab3 = st.tabs(["📊 Visão de Mercado", "🎯 Oportunidades", "⚔️ Comparador IA"])

    # ABA 1: Visão Geral
    with tab1:
        col_g1, col_g2 = st.columns([2, 1])
        with col_g1:
            st.subheader("Distribuição de Preços")
            fig_hist = px.histogram(df_foco, x="Preco_Num", nbins=20, title="Faixas de Preço Mais Comuns")
            fig_hist.add_vline(x=media, line_dash="dash", line_color="red", annotation_text="Média")
            st.plotly_chart(fig_hist, use_container_width=True)
        with col_g2:
            st.subheader("Dispersão")
            fig_scat = px.scatter(df_foco, x="Preco_Num", y="Vendas_Num", size="Preco_Num", color="Preco_Num", hover_name="Produto_Nome")
            st.plotly_chart(fig_scat, use_container_width=True)

    # ABA 2: Oportunidades (Abaixo da média)
    with tab2:
        st.subheader("💎 Produtos Abaixo da Média de Mercado")
        limite = media * 0.85 # 15% abaixo da média
        df_baratos = df_foco[df_foco['Preco_Num'] < limite].sort_values("Preco_Num")
        
        if not df_baratos.empty:
            st.dataframe(
                df_baratos[['Produto_Nome', 'Preco_Num', 'Link_Url']],
                column_config={
                    "Link_Url": st.column_config.LinkColumn("Link para Compra"),
                    "Preco_Num": st.column_config.NumberColumn("Preço", format="R$ %.2f")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Nenhum produto muito barato encontrado nesta busca.")

    # ABA 3: Comparador Fuzzy
    with tab3:
        st.subheader("🔍 Agrupar Similares")
        produtos_unicos = df_foco['Produto_Nome'].unique()
        if len(produtos_unicos) > 0:
            base = st.selectbox("Escolha um produto base:", options=produtos_unicos)
            if base:
                # Busca similares
                matches = process.extract(base, produtos_unicos, limit=15, scorer=fuzz.token_set_ratio)
                similares = [m[0] for m in matches if m[1] > 50]
                
                df_comp = df_foco[df_foco['Produto_Nome'].isin(similares)].sort_values("Preco_Num")
                
                fig_bar = px.bar(df_comp, x="Produto_Nome", y="Preco_Num", color="Preco_Num", text="Preco_Num", title="Comparativo Direto", color_continuous_scale="RdYlGn_r")
                fig_bar.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
                st.plotly_chart(fig_bar, use_container_width=True)

else:
    st.warning("Carregando dados... Se demorar, clique em 'Atualizar Dados'.")