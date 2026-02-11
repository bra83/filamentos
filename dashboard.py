import streamlit as st
import pandas as pd
import plotly.express as px
import re
from thefuzz import process, fuzz

# === CONFIGURAÇÃO DA PÁGINA ===
st.set_page_config(page_title="BCRUZ 3D Master Dashboard", layout="wide", page_icon="🚀")

# === SEU LINK FIXO ===
DEFAULT_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vRIXvkHql1pQlHUKnmldEbGlU6GFOmimyin4yLAuhrtuCIPb7ist587wNOYKs_L8RJF_MpRiq2e2mgu/pub?gid=444101812&single=true&output=csv"

# === FUNÇÕES DE LIMPEZA ===
def limpar_preco(valor):
    if pd.isna(valor) or str(valor).strip() == "": return 0.0
    texto = str(valor).upper().replace("R$", "").strip()
    texto = re.sub(r'[^\d,.]', '', texto)
    try:
        if ',' in texto: texto = texto.replace('.', '').replace(',', '.')
        return float(texto)
    except: return 0.0

def limpar_vendas(valor):
    if pd.isna(valor): return 0
    texto = str(valor).lower().strip()
    multiplicador = 1
    if 'mil' in texto or 'k' in texto: multiplicador = 1000
    texto = re.sub(r'[^\d,.]', '', texto)
    try:
        if ',' in texto: texto = texto.replace('.', '').replace(',', '.')
        return int(float(texto) * multiplicador)
    except: return 0

@st.cache_data(ttl=30)
def carregar_dados(url):
    try:
        df = pd.read_csv(url, on_bad_lines='skip')
        df.columns = [str(c).upper().strip() for c in df.columns]
        
        col_preco = next((c for c in df.columns if any(x in c for x in ['PREÇ', 'PRICE', '(R$)'])), None)
        col_nome = next((c for c in df.columns if any(x in c for x in ['PRODUT', 'NOME', 'TITULO'])), None)
        col_vendas = next((c for c in df.columns if any(x in c for x in ['VENDA', 'SOLD'])), None)
        col_link = next((c for c in df.columns if any(x in c for x in ['LINK', 'URL'])), None)
        col_data = next((c for c in df.columns if any(x in c for x in ['DATA', 'DATE', 'TIME'])), None)
        
        if col_preco and col_nome:
            df['Preco_Num'] = df[col_preco].apply(limpar_preco)
            df['Produto_Nome'] = df[col_nome]
            df['Link_Url'] = df[col_link] if col_link else "#"
            
            if col_vendas: df['Vendas_Num'] = df[col_vendas].apply(limpar_vendas)
            else: df['Vendas_Num'] = 0
            
            # Tratamento de Data para o Histórico
            if col_data:
                try: df['Data_Formatada'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')
                except: df['Data_Formatada'] = df.index
            else:
                df['Data_Formatada'] = df.index

            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao carregar CSV: {e}")
        return pd.DataFrame()

def calcular_quedas(df_in):
    # Lógica de Queda: Ordena por Nome e Data Inversa
    df = df_in.copy()
    # Se Data_Formatada for nulo, usa o index
    df['Sort_Key'] = df['Data_Formatada'].fillna(pd.Series(df.index))
    
    df = df.sort_values(by=['Produto_Nome', 'Sort_Key'], ascending=[True, False])
    
    # Shift(-1) pega o valor da linha "abaixo" (que é o registro anterior no tempo)
    df['Preco_Anterior'] = df.groupby('Produto_Nome')['Preco_Num'].shift(-1)
    
    # Filtra onde houve queda
    quedas = df[
        (df['Preco_Num'] < df['Preco_Anterior']) & 
        (df['Preco_Num'] > 0) &
        (df['Preco_Anterior'] > 0)
    ].copy()
    
    if not quedas.empty:
        quedas['Queda_%'] = ((quedas['Preco_Anterior'] - quedas['Preco_Num']) / quedas['Preco_Anterior']) * 100
        quedas['Desconto_R$'] = quedas['Preco_Anterior'] - quedas['Preco_Num']
        
    return quedas

# === INTERFACE ===
st.title("🚀 Painel de Inteligência de Mercado 3D")

with st.sidebar:
    st.header("⚙️ Controle")
    if st.button("🔄 Atualizar Dados"):
        st.cache_data.clear()
        st.rerun()
    st.divider()
    busca_principal = st.text_input("🔍 Filtro Global:", placeholder="Ex: Vaso, Suporte")

df = carregar_dados(DEFAULT_URL)

if not df.empty:
    # 1. Filtro Global
    df_foco = df.copy()
    if busca_principal:
        df_foco = df_foco[df_foco['Produto_Nome'].str.contains(busca_principal, case=False, na=False)]

    # 2. Cálculo de Quedas (Baseado no filtro atual)
    df_quedas = calcular_quedas(df_foco)

    # 3. Métricas Gerais
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Itens na Tela", len(df_foco))
    if len(df_foco) > 0:
        media = df_foco['Preco_Num'].mean()
        c2.metric("Preço Médio", f"R$ {media:.2f}")
        c3.metric("Quedas Detectadas", len(df_quedas))
        
        melhor_queda = df_quedas['Queda_%'].max() if not df_quedas.empty else 0
        c4.metric("Maior Desconto", f"{melhor_queda:.1f}%")

    st.markdown("---")

    # === ABAS ===
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🔥 PROMOÇÕES (Quedas)", 
        "📊 Visão de Mercado", 
        "🎯 Radar de Oportunidades", 
        "⚔️ Comparador IA",
        "📂 Dados Brutos"
    ])

    # --- ABA 1: QUEDAS DE PREÇO ---
    with tab1:
        st.header("🔥 Alerta de Preços Baixos")
        if not df_quedas.empty:
            st.success(f"Encontramos {len(df_quedas)} produtos que ficaram mais baratos recentemente!")
            df_quedas = df_quedas.sort_values(by='Queda_%', ascending=False)
            
            for i, row in df_quedas.iterrows():
                with st.expander(f"⬇️ {row['Queda_%']:.0f}% OFF | {row['Produto_Nome']} (R$ {row['Preco_Num']:.2f})"):
                    k1, k2, k3, k4 = st.columns([1,1,1,2])
                    k1.metric("Era", f"R$ {row['Preco_Anterior']:.2f}")
                    k2.metric("Ficou", f"R$ {row['Preco_Num']:.2f}", delta=f"- R$ {row['Desconto_R$']:.2f}", delta_color="normal")
                    k3.write(f"📅 {str(row['Data_Formatada'])[:10]}")
                    if row['Link_Url'] != "#":
                        k4.markdown(f"[🛒 **VER ANÚNCIO**]({row['Link_Url']})", unsafe_allow_html=True)
        else:
            st.info("Nenhuma queda de preço detectada nos itens filtrados (comparado ao histórico anterior).")

    # --- ABA 2: VISÃO GERAL ---
    with tab2:
        st.header("📊 Análise do Mercado")
        if not df_foco.empty:
            col_g1, col_g2 = st.columns([2, 1])
            with col_g1:
                st.subheader("Distribuição de Preços")
                fig_hist = px.histogram(df_foco, x="Preco_Num", nbins=20, title="Faixas de Preço Mais Comuns", color_discrete_sequence=['#3366CC'])
                fig_hist.add_vline(x=media, line_dash="dash", line_color="red", annotation_text="Média")
                st.plotly_chart(fig_hist, use_container_width=True)
            with col_g2:
                st.subheader("Preço x Vendas")
                fig_scat = px.scatter(df_foco, x="Preco_Num", y="Vendas_Num", size="Preco_Num", color="Preco_Num", hover_name="Produto_Nome", title="Quem vende mais?")
                st.plotly_chart(fig_scat, use_container_width=True)
        else:
            st.warning("Sem dados para exibir gráficos.")

    # --- ABA 3: RADAR (ABAIXO DA MÉDIA) ---
    with tab3:
        st.header("🎯 Oportunidades (Abaixo da Média)")
        if not df_foco.empty:
            limite = media * 0.85 # 15% abaixo da média
            df_baratos = df_foco[df_foco['Preco_Num'] < limite].sort_values("Preco_Num")
            
            if not df_baratos.empty:
                # CORREÇÃO AQUI: Forçamos o valor máximo a ser um número inteiro comum (int)
                max_vendas = int(df['Vendas_Num'].max()) if df['Vendas_Num'].max() > 0 else 100

                st.dataframe(
                    df_baratos[['Produto_Nome', 'Preco_Num', 'Vendas_Num', 'Link_Url']],
                    column_config={
                        "Link_Url": st.column_config.LinkColumn("Link"),
                        "Preco_Num": st.column_config.NumberColumn("Preço", format="R$ %.2f"),
                        "Vendas_Num": st.column_config.ProgressColumn(
                            "Vendas", 
                            min_value=0, 
                            max_value=max_vendas, # Agora usando a variável convertida
                            format="%d"
                        )
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Nenhum produto muito barato encontrado.")
    # --- ABA 4: COMPARADOR FUZZY ---
    with tab4:
        st.header("⚔️ Comparador Inteligente")
        produtos_unicos = df_foco['Produto_Nome'].unique()
        if len(produtos_unicos) > 0:
            base = st.selectbox("Escolha um produto para comparar:", options=produtos_unicos)
            if base:
                matches = process.extract(base, produtos_unicos, limit=15, scorer=fuzz.token_set_ratio)
                similares = [m[0] for m in matches if m[1] > 50]
                
                df_comp = df_foco[df_foco['Produto_Nome'].isin(similares)].sort_values("Preco_Num")
                
                fig_bar = px.bar(df_comp, x="Produto_Nome", y="Preco_Num", color="Preco_Num", text="Preco_Num", title="Variação de Preço entre Similares", color_continuous_scale="RdYlGn_r")
                fig_bar.update_traces(texttemplate='R$ %{text:.2f}', textposition='outside')
                st.plotly_chart(fig_bar, use_container_width=True)

    # --- ABA 5: DADOS BRUTOS ---
    with tab5:
        st.dataframe(df_foco, use_container_width=True)

else:
    st.warning("Carregando dados... Se demorar, verifique o link da planilha.")

