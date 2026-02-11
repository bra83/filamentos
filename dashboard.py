import streamlit as st
import pandas as pd
import plotly.express as px
import re
from thefuzz import process, fuzz

# === CONFIGURAÇÃO DA PÁGINA ===
st.set_page_config(page_title="BCRUZ 3D Monitor", layout="wide", page_icon="📉")

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

@st.cache_data(ttl=10)
def carregar_dados_com_historico(url):
    try:
        df = pd.read_csv(url, on_bad_lines='skip')
        df.columns = [str(c).upper().strip() for c in df.columns]

        # Mapeamento de colunas
        col_preco = next((c for c in df.columns if any(x in c for x in ['PREÇ', 'PRICE', '(R$)'])), None)
        col_nome = next((c for c in df.columns if any(x in c for x in ['PRODUT', 'NOME', 'TITULO'])), None)
        col_data = next((c for c in df.columns if any(x in c for x in ['DATA', 'DATE', 'TIME'])), None)
        col_link = next((c for c in df.columns if any(x in c for x in ['LINK', 'URL'])), None)

        if col_preco and col_nome:
            df['Preco_Num'] = df[col_preco].apply(limpar_preco)
            df['Produto_Nome'] = df[col_nome]
            df['Link_Url'] = df[col_link] if col_link else "#"
            
            # Tratamento de Data (Tenta converter, se falhar usa o índice original como ordem cronológica)
            if col_data:
                try:
                    df['Data_Formatada'] = pd.to_datetime(df[col_data], dayfirst=True, errors='coerce')
                except:
                    df['Data_Formatada'] = df.index 
            else:
                df['Data_Formatada'] = df.index # Usa a ordem das linhas se não tiver data

            return df
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao ler CSV: {e}")
        return pd.DataFrame()

def calcular_quedas(df):
    # 1. Ordena por Nome e Data (Do mais recente para o mais antigo)
    # Se 'Data_Formatada' for NaT, usa o índice (últimas linhas = mais recentes)
    df = df.sort_values(by=['Produto_Nome', 'Data_Formatada'], ascending=[True, False]) # False = Mais recente primeiro

    # 2. Cria coluna com o preço da linha de baixo (que é o registro anterior temporalmente)
    df['Preco_Anterior'] = df.groupby('Produto_Nome')['Preco_Num'].shift(-1)
    
    # 3. Filtra onde o Preço Atual é MENOR que o Anterior
    # (Ignora preço 0 para evitar erros de leitura)
    quedas = df[
        (df['Preco_Num'] < df['Preco_Anterior']) & 
        (df['Preco_Num'] > 0) &
        (df['Preco_Anterior'] > 0)
    ].copy()

    # 4. Calcula o desconto
    quedas['Desconto_R$'] = quedas['Preco_Anterior'] - quedas['Preco_Num']
    quedas['Queda_%'] = ((quedas['Preco_Anterior'] - quedas['Preco_Num']) / quedas['Preco_Anterior']) * 100
    
    return quedas

# === INTERFACE ===
st.title("📉 Monitor de Queda de Preços 3D")

with st.sidebar:
    st.header("⚙️ Controle")
    if st.button("🔄 Atualizar Agora"):
        st.cache_data.clear()
        st.rerun()
    st.info("O sistema compara o último preço capturado com o penúltimo para detectar promoções.")

df = carregar_dados_com_historico(DEFAULT_URL)

if not df.empty:
    # Processa as quedas
    df_quedas = calcular_quedas(df)
    
    # Última data capturada (aproximada)
    ultima_captura = df['Data_Formatada'].max()
    
    # Métricas de Alerta
    c1, c2, c3 = st.columns(3)
    c1.metric("Itens Monitorados", len(df))
    c2.metric("🔥 Quedas Detectadas", len(df_quedas))
    if not df_quedas.empty:
        maior_queda = df_quedas['Queda_%'].max()
        c3.metric("Melhor Oportunidade", f"-{maior_queda:.1f}%")

    st.markdown("---")

    # === ABA PRINCIPAL: SÓ O QUE CAIU ===
    tab1, tab2 = st.tabs(["🔥 PROMOÇÕES RECENTES", "📋 Tabela Geral"])

    with tab1:
        if not df_quedas.empty:
            st.success(f"Encontramos {len(df_quedas)} produtos que baixaram de preço desde a última atualização!")
            
            # Ordena pelas maiores quedas percentuais
            df_display = df_quedas.sort_values(by='Queda_%', ascending=False)
            
            for index, row in df_display.iterrows():
                with st.expander(f"⬇️ {row['Queda_%']:.0f}% OFF | {row['Produto_Nome']} (R$ {row['Preco_Num']:.2f})"):
                    c_kpi1, c_kpi2, c_kpi3, c_btn = st.columns([1,1,1,2])
                    c_kpi1.metric("Preço Antigo", f"R$ {row['Preco_Anterior']:.2f}")
                    c_kpi2.metric("Preço Novo", f"R$ {row['Preco_Num']:.2f}", delta=f"- R$ {row['Desconto_R$']:.2f}")
                    c_kpi3.metric("Data", str(row['Data_Formatada'])[:10]) # Tenta mostrar só a data
                    
                    if row['Link_Url'] != "#":
                        c_btn.markdown(f"[🛒 **IR PARA O ANÚNCIO**]({row['Link_Url']})", unsafe_allow_html=True)
        else:
            st.info("🤷‍♂️ Nenhuma queda de preço detectada hoje. Os preços mantiveram-se iguais ou subiram.")

    with tab2:
        st.write("Visão completa de todos os dados capturados:")
        st.dataframe(df, use_container_width=True)

else:
    st.warning("Carregando dados...")
