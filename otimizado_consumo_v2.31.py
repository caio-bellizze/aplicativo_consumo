import pandas as pd
#import numpy as np
import streamlit as st
import plotly.graph_objects as go
import requests
import time
from calendar import monthrange
#import re
#import psutil  # Para monitorar o uso de memória
import gc  # Garbage collector
import os

# Configuração da página
st.set_page_config(
    layout="wide", 
    initial_sidebar_state="collapsed", 
    page_title="Análise de Consumo de Energia", 
    page_icon="⚡"
    #menu_items={'About': "Análise de Consumo de Energia - CCEE\n\n"}
    
    )
#st.markdown("<style>body{background-color: #f0f2f5;}</style>", unsafe_allow_html=True)
st.title("&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;📊 **Análise de Consumo de Energia**")
#st.write("Uso de memória", f"{psutil.Process().memory_info().rss / (1024 * 1024):.1f} MB")
st.markdown("<br>",unsafe_allow_html=True)  # Espaço em branco

#st.sidebar.metric("Uso de memória", f"{psutil.Process().memory_info().rss / (1024 * 1024):.1f} MB")
#st.sidebar.metric("Uso de CPU", f"{psutil.cpu_percent(interval=1)} %")
#st.sidebar.title("Analise de dados da API")
#st.sidebar.slider("Ajuste o uso de memória", min_value=1, max_value=100, value=30, step=1)
#st.sidebar.write("Ajuste o uso de memória para otimizar o desempenho do aplicativo.")

# ------- OTIMIZAÇÕES DE MEMÓRIA -------

# Função para otimizar tipos de dados em um DataFrame
def optimize_dtypes(df):
    """Otimiza os tipos de dados para reduzir o uso de memória."""
    if df.empty:
        return df
    
    # Modificar in-place em vez de criar uma cópia
    for col in df.columns:
        if col in ['NOME_EMPRESARIAL', 'CIDADE', 'ESTADO_UF', 'SUBMERCADO', 'SIGLA_PARCELA_CARGA']:
            df[col] = df[col].astype('category')
        elif df[col].dtype == 'float64':
            df[col] = pd.to_numeric(df[col], downcast='float')
        elif df[col].dtype == 'int64':
            df[col] = pd.to_numeric(df[col], downcast='integer')
    
    return df

# Função para liberar memória
def clear_memory():
    """Força a liberação de memória não utilizada."""
    gc.collect()

# ------- FUNÇÕES DE CARREGAMENTO DE DADOS -------

# URLs das APIs
resource_id_2025 = "c88d04a6-fe42-413b-b7bf-86e390494fb0"
base_url_2025 = f"https://dadosabertos.ccee.org.br/api/3/action/datastore_search?resource_id={resource_id_2025}"

# Função para carregar apenas nomes das empresas
@st.cache_data(show_spinner=False, ttl=3600)  # Cache expira após 1 hora
def carregar_nomes_empresas():
    """Carrega apenas os nomes das empresas de todos os arquivos."""
    empresas = set()
    
    # Carregar nomes das empresas de cada arquivo Parquet
    arquivos = [
        "base_de_dados_nacional_2022.parquet",
        "base_de_dados_nacional_2023.parquet", 
        "base_de_dados_nacional_2024.parquet"
    ]
    
    for arquivo in arquivos:
        try:
            if os.path.exists(arquivo):
                # Ler todo o arquivo de uma vez para obter apenas as empresas
                df_empresas = pd.read_parquet(arquivo, engine="pyarrow")
                
                if "NOME_EMPRESARIAL" in df_empresas.columns:
                    empresas.update(df_empresas["NOME_EMPRESARIAL"].unique())
                
                # Liberar memória
                del df_empresas
                clear_memory()
            else:
                st.warning(f"Arquivo {arquivo} não encontrado.")
        except Exception as e:
            st.warning(f"Erro ao carregar empresas do arquivo {arquivo}: {e}")
    
    # Carregar nomes das empresas da API de 2025
    try:
        response = requests.get(f"{base_url_2025}&limit=1000", timeout=30)
        if response.status_code == 200:
            data = response.json()
            records = data.get("result", {}).get("records", [])
            if records and "NOME_EMPRESARIAL" in records[0]:
                empresas_api = {r["NOME_EMPRESARIAL"] for r in records if "NOME_EMPRESARIAL" in r}
                empresas.update(empresas_api)
    except Exception as e:
        st.warning(f"Erro ao carregar empresas da API: {e}")
    
    return sorted(list(empresas))


@st.cache_data(show_spinner=False, ttl=3600)  # Cache expira após 1 hora
def obter_informacoes_base():
    """Obtém informações básicas da base de dados sem carregar todos os registros."""
    info = {
        "data_mais_antiga": None,
        "data_mais_recente": None,
        "total_registros": 0
    }
    
    # Lista de arquivos a verificar
    arquivos = [
        "base_de_dados_nacional_2022.parquet",
        "base_de_dados_nacional_2023.parquet", 
        "base_de_dados_nacional_2024.parquet"
    ]
    
    # Verificar cada arquivo
    for arquivo in arquivos:
        if os.path.exists(arquivo):
            try:
                # Carregar apenas as primeiras linhas para verificar estrutura
                df_amostra = pd.read_parquet(arquivo, engine="pyarrow")
                
                # Contar registros
                info["total_registros"] += len(df_amostra)
                
                # Verificar datas
                if "MES_REFERENCIA" in df_amostra.columns:
                    df_amostra["MES_REFERENCIA"] = pd.to_datetime(df_amostra["MES_REFERENCIA"], errors="coerce", dayfirst=True)
                    
                    min_date = df_amostra["MES_REFERENCIA"].min()
                    max_date = df_amostra["MES_REFERENCIA"].max()
                    
                    if info["data_mais_antiga"] is None or (min_date is not pd.NaT and min_date < info["data_mais_antiga"]):
                        info["data_mais_antiga"] = min_date
                    
                    if info["data_mais_recente"] is None or (max_date is not pd.NaT and max_date > info["data_mais_recente"]):
                        info["data_mais_recente"] = max_date
                
                # Liberar memória
                del df_amostra
                clear_memory()
            
            except Exception as e:
                st.warning(f"Erro ao obter informações do arquivo {arquivo}: {e}")
    
    # Verificar API de 2025
    try:
        response = requests.get(f"{base_url_2025}&limit=10", timeout=30)
        if response.status_code == 200:
            data = response.json()
            
            # Obter total de registros da API
            total_api = data.get("result", {}).get("total", 0)
            info["total_registros"] += total_api
            
            # Obter registros para verificar datas
            records = data.get("result", {}).get("records", [])
            if records and "MES_REFERENCIA" in records[0]:
                # Fazer uma consulta adicional para obter a data mais recente
                try:
                    response_recente = requests.get(f"{base_url_2025}&limit=1&sort=MES_REFERENCIA desc", timeout=30)
                    data_recente = response_recente.json()
                    records_recente = data_recente.get("result", {}).get("records", [])
                    
                    if records_recente and "MES_REFERENCIA" in records_recente[0]:
                        data_str = records_recente[0]["MES_REFERENCIA"]
                        data_formatada = f"01/{data_str[4:6]}/{data_str[:4]}"
                        data_api = pd.to_datetime(data_formatada, dayfirst=True)
                        
                        if info["data_mais_recente"] is None or data_api > info["data_mais_recente"]:
                            info["data_mais_recente"] = data_api
                except:
                    pass
    except Exception as e:
        st.warning(f"Erro ao obter informações da API: {e}")
    
    return info

@st.cache_data(show_spinner=False, ttl=3600)  # Cache expira após 1 hora
def carregar_dados_api(url, ano, empresa=None, data_inicio=None, data_fim=None, max_requests=50):
    """Carrega dados da API com filtros aplicados."""
    all_records = []
    limit = 1000
    offset = 0
    request_count = 0
    
    #with st.spinner(f"Carregando dados de {ano} da API..."):
    api_url = url
    if empresa:
        # Extrair parte do nome para consultar a API (evita problemas com aspas e caracteres especiais)
        # Pegando apenas os primeiros 20 caracteres ou até o primeiro espaço como filtro aproximado
        empresa_simples = empresa.split()[0][:20]
        
        # Adicionar filtro aproximado na consulta da API
        api_url = f"{url}&q={{\"NOME_EMPRESARIAL\":\"{empresa_simples}\"}}"
    
    while request_count < max_requests:
        try:
            current_url = f"{api_url}&limit={limit}&offset={offset}"
            #st.write(f"Consultando API: {current_url}") # Temporário para debug
            
            response = requests.get(current_url, timeout=30)
            response.raise_for_status()
            data = response.json()
            records = data.get("result", {}).get("records", [])
            
            if not records:
                break
            
            all_records.extend(records)
            offset += limit
            request_count += 1
            
            # Se não houver mais dados, pare
            if len(records) < limit:
                break
                
        except requests.exceptions.RequestException as e:
            st.warning(f"Erro ao carregar dados da API: {e}")
            time.sleep(2)
            break
    
    df = pd.DataFrame(all_records)
    
    # Agora aplicamos um filtro exato no DataFrame
    if not df.empty and empresa and "NOME_EMPRESARIAL" in df.columns:
        # Manter apenas registros com nome exato da empresa
        df = df[df["NOME_EMPRESARIAL"] == empresa]
        #st.write(f"Após filtro exato por '{empresa}': {df.shape[0]} registros")
    
    if not df.empty and "MES_REFERENCIA" in df.columns:
        df["MES_REFERENCIA"] = df["MES_REFERENCIA"].astype(str)
        df["MES_REFERENCIA"] = df["MES_REFERENCIA"].apply(lambda x: f"01/{x[4:6]}/{x[:4]}")
        df["MES_REFERENCIA"] = pd.to_datetime(df["MES_REFERENCIA"], dayfirst=True)
        
        # Aplicar filtros de data
        if data_inicio:
            df = df[df["MES_REFERENCIA"] >= pd.to_datetime(data_inicio)]
        if data_fim:
            df = df[df["MES_REFERENCIA"] <= pd.to_datetime(data_fim)]
    
    return optimize_dtypes(df)

@st.cache_data(show_spinner=False, ttl=3600)  # Cache expira após 1 hora
def carregar_dados_parquet(nome_arquivo, empresa=None, data_inicio=None, data_fim=None):
    """Carrega dados Parquet com filtros aplicados."""
    if not os.path.exists(nome_arquivo):
        st.warning(f"Arquivo {nome_arquivo} não encontrado.")
        return pd.DataFrame()
    
    try:
        #with st.spinner(f"Carregando dados de {nome_arquivo}..."):
        # Ler o arquivo Parquet
        df = pd.read_parquet(nome_arquivo, engine="pyarrow")
        
        # Filtrar para a empresa desejada se especificada
        if empresa and "NOME_EMPRESARIAL" in df.columns:
            df = df[df["NOME_EMPRESARIAL"] == empresa]
        
        # Processar datas e aplicar filtros
        if not df.empty and "MES_REFERENCIA" in df.columns:
            df["MES_REFERENCIA"] = pd.to_datetime(df["MES_REFERENCIA"], errors="coerce", dayfirst=True)
            
            # Aplicar filtros de data
            if data_inicio:
                df = df[df["MES_REFERENCIA"] >= pd.to_datetime(data_inicio)]
            if data_fim:
                df = df[df["MES_REFERENCIA"] <= pd.to_datetime(data_fim)]
        
        return optimize_dtypes(df)
    
    except Exception as e:
        st.error(f"Erro ao carregar {nome_arquivo}: {e}")
        return pd.DataFrame()

# ------- INTERFACE DE USUÁRIO -------

# Carregar lista de empresas
with st.spinner("Carregando lista de empresas..."):
    
    empresas_disponiveis = carregar_nomes_empresas()

# Obter informações básicas da base
info_base = obter_informacoes_base()

# Mostrar informações básicas
if info_base["data_mais_antiga"] is not None and info_base["data_mais_recente"] is not None:
    mes_mais_antigo = info_base["data_mais_antiga"].strftime("%m/%Y")
    mes_mais_recente = info_base["data_mais_recente"].strftime("%m/%Y")
    st.success(f"Base de Dados Atualizada ({mes_mais_antigo} até {mes_mais_recente})")

#if info_base["total_registros"] > 0:
#    st.write(f"Base completa tem {info_base['total_registros']} registros.")
# Inputs
empresas_selecionadas = st.multiselect(
    label="Selecione as empresas desejadas",
    options=empresas_disponiveis,
    default=None,
    format_func=lambda x: x,#.lower(),
    key="empresas_selecionadas",
    help="Selecione uma ou mais empresas para análise. Se nenhuma empresa for selecionada, todos os dados serão carregados.",
    on_change=None,
    args=None,
    kwargs=None,
    max_selections=None,  # Limitar a 10 seleções
    placeholder="Selecione as empresas desejadas",
    disabled=False,
    label_visibility="visible",
    accept_new_options=False
)

col1, col2, col3 = st.columns([1, 1, 1], gap='small', )
with col1:
    data_inicio = st.date_input("Data inicial", value=pd.to_datetime("2022-01-01"),format='DD/MM/YYYY')
with col2:
    data_fim = st.date_input("Data final", value=info_base["data_mais_recente"], format='DD/MM/YYYY')
with col3:
    flex_user = st.slider("Flexibilidade (%)", min_value=1, max_value=100, value=30)
#with col4:

mostrar_contornos = st.checkbox(
    "**Mostrar contornos**", value=False, 
    help="Habilita contornos coloridos que destacam cada empresa nas barras empilhadas"
)

st.markdown("<br/>", unsafe_allow_html=True)  # Espaço em branco
# ------- PROCESSAMENTO DE DADOS -------

if st.button(":red[Gerar Gráfico]") and empresas_selecionadas:
    # Agora carregamos dados apenas para as empresas selecionadas
    df_total_filtrado = pd.DataFrame()
    
    # Função para processar cada arquivo e empresa
    def processar_arquivo(arquivo, ano, empresa, data_inicio, data_fim):
        if arquivo.startswith("http"):
            return carregar_dados_api(arquivo, ano, empresa, data_inicio, data_fim)
        else:
            return carregar_dados_parquet(arquivo, empresa, data_inicio, data_fim)
    
    # Processar cada empresa selecionada
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    for i, empresa in enumerate(empresas_selecionadas):
        progress_text.text(f"Processando dados para: {empresa}")
        progress_bar.progress(i / len(empresas_selecionadas))
        
        # Carregar dados de cada fonte
        df_2022 = processar_arquivo("base_de_dados_nacional_2022.parquet", 2022, empresa, data_inicio, data_fim)
        df_2023 = processar_arquivo("base_de_dados_nacional_2023.parquet", 2023, empresa, data_inicio, data_fim)
        df_2024 = processar_arquivo("base_de_dados_nacional_2024.parquet", 2024, empresa, data_inicio, data_fim)
        df_2025 = processar_arquivo(base_url_2025, 2025, empresa, data_inicio, data_fim)
         
        
        # Diagnóstico dos dados da API
        #with st.sidebar.expander("Diagnóstico dos dados da API", icon="🔍"):
        #    st.write(f"Shape dos dados da API: {df_2025.shape}")
        #    
        #    if not df_2025.empty:
        #        st.write(f"Colunas disponíveis na API: {df_2025.columns.tolist()}")
        #        st.write(f"Amostra dos dados da API:")
        #        st.dataframe(df_2025.head(df_2025.shape[0]))
        #        
        #        if "MES_REFERENCIA" in df_2025.columns:
        #            st.write(f"Período dos dados: {df_2025['MES_REFERENCIA'].min()} a {df_2025['MES_REFERENCIA'].max()}")
        #          
        #        # Verificar coluna de consumo
        #        consumo_cols = [col for col in df_2025.columns if "CONSUMO" in col.upper()]
        #        if consumo_cols:
        #            st.write(f"Colunas de consumo encontradas: {consumo_cols}")
        #            for col in consumo_cols:
        #                st.write(f"Valor médio de {col}: {df_2025[col].mean()}")
        #        else:
        #            st.warning("Nenhuma coluna de consumo encontrada nos dados da API")
        #    else:
        #        st.warning("Nenhum dado retornado da API")

        # Combinar dados da empresa - filtrar DataFrames vazios antes de concatenar
        dataframes_validos = [df for df in [df_2022, df_2023, df_2024, df_2025] if not df.empty]

        if dataframes_validos:
            # Concatenar apenas os DataFrames que não estão vazios
            df_empresa = pd.concat(dataframes_validos, ignore_index=True)
            
            # Adicionar ao DataFrame total apenas se tivermos dados válidos
            if not df_empresa.empty:
                if df_total_filtrado.empty:
                    df_total_filtrado = df_empresa.copy()
                else:
                    # Garantir que as colunas estejam alinhadas antes da concatenação
                    colunas_comuns = list(set(df_total_filtrado.columns) & set(df_empresa.columns))
                    df_total_filtrado = pd.concat(
                        [df_total_filtrado[colunas_comuns], df_empresa[colunas_comuns]], 
                        ignore_index=True
                    )
        else:
            # Se não houver dados válidos, criar um DataFrame vazio com as colunas necessárias
            df_empresa = pd.DataFrame()
        
        # Liberar memória
        del df_2022, df_2023, df_2024, df_2025, df_empresa
        clear_memory()

    progress_bar.progress(1.0)
    progress_text.text("Processamento concluído!")
    
    if df_total_filtrado.empty:
        st.warning("Não foram encontrados dados para as empresas selecionadas no período especificado.")
        st.stop()
    
    # Ordenar e processar dados
    df_total_filtrado["MES_REFERENCIA"] = pd.to_datetime(df_total_filtrado["MES_REFERENCIA"], errors="coerce")
    df_total_ord = df_total_filtrado.sort_values(by="MES_REFERENCIA", ascending=False)
    
    # Remover colunas desnecessárias
    if "id" in df_total_ord.columns:
        df_total_ord = df_total_ord.drop(columns=["id"])
    
    # Calcular horas no mês e consumo em MWm
    df_total_ord["HORAS_NO_MES"] = df_total_ord["MES_REFERENCIA"].apply(
        lambda x: monthrange(x.year, x.month)[1] * 24
    )
    
    col_consumo = next((col for col in df_total_ord.columns if "CONSUMO" in col.upper() and "TOTAL" in col.upper()), None)
    if col_consumo:
        df_total_ord["CONSUMO_MWm"] = pd.to_numeric(df_total_ord[col_consumo], errors="coerce") / df_total_ord["HORAS_NO_MES"]
    
    # Análise mensal - modificado para separar por empresa e manter indicação de flexibilização
    df_total_ord["Ano_Mes"] = df_total_ord["MES_REFERENCIA"].dt.to_period("M")
    
    # Calcular limites para o consumo total
    df_total_mensal = df_total_ord.groupby("Ano_Mes", observed=True)["CONSUMO_MWm"].sum().reset_index()
    df_total_mensal["Ano_Mes"] = df_total_mensal["Ano_Mes"].dt.to_timestamp()
    
    media_inicial = df_total_mensal["CONSUMO_MWm"].mean()
    flex_valor = media_inicial * (flex_user / 100)
    lim_sup_user = media_inicial + flex_valor
    lim_inf_user = media_inicial - flex_valor
    
    df_total_mensal["fora_faixa"] = ~df_total_mensal["CONSUMO_MWm"].between(lim_inf_user, lim_sup_user)
    media_consumo_ajustada = df_total_mensal.loc[~df_total_mensal["fora_faixa"], "CONSUMO_MWm"].mean()
    
    flex_valor = media_consumo_ajustada * (flex_user / 100)
    lim_sup_user = media_consumo_ajustada + flex_valor
    lim_inf_user = media_consumo_ajustada - flex_valor
    
    df_total_mensal["fora_faixa"] = ~df_total_mensal["CONSUMO_MWm"].between(lim_inf_user, lim_sup_user)
    
    # Agrupar por empresa e mês para o gráfico empilhado
    df_mensal_empresa = df_total_ord.groupby(["NOME_EMPRESARIAL", "Ano_Mes"], observed=True)["CONSUMO_MWm"].sum().reset_index()
    df_mensal_empresa["Ano_Mes"] = df_mensal_empresa["Ano_Mes"].dt.to_timestamp()
    
    # Juntar as informações de "fora_faixa" do total com os dados por empresa
    df_mensal_empresa = df_mensal_empresa.merge(
        df_total_mensal[["Ano_Mes", "fora_faixa"]], 
        on="Ano_Mes",
        how="left"
    )
    
    # ------- VISUALIZAÇÃO -------
    
    # Importar módulo para paleta de cores
    import plotly.express as px
    
    # Gráfico de consumo mensal empilhado por empresa com indicação de flexibilização
    fig = go.Figure()
    # Dicionário para tradução dos meses
    meses_pt = {
        'Jan': 'Jan', 'Feb': 'Fev', 'Mar': 'Mar', 'Apr': 'Abr',
        'May': 'Mai', 'Jun': 'Jun', 'Jul': 'Jul', 'Aug': 'Ago',
        'Sep': 'Set', 'Oct': 'Out', 'Nov': 'Nov', 'Dec': 'Dez'
    }
    
    # Função para traduzir datas no formato '%b-%Y'
    def traduzir_data(data):
        if isinstance(data, pd.Timestamp):
            mes_en = data.strftime('%b')
            if mes_en in meses_pt:
                return f"{meses_pt[mes_en]}-{data.strftime('%Y')}"
        return data
    # Verificar se temos mais de uma empresa
    multiplas_empresas = len(empresas_selecionadas) > 1
    
    # Gerar paleta de cores para as empresas apenas se tivermos múltiplas empresas
    empresas_unicas = df_mensal_empresa["NOME_EMPRESARIAL"].unique()
    
    if multiplas_empresas:
        # Usando paletas que evitam tons de azul e vermelho para os contornos
        cores_contorno = px.colors.qualitative.Safe + px.colors.qualitative.Prism + px.colors.qualitative.Vivid
        cores_contorno = [cor for cor in cores_contorno if not ('blue' in cor.lower() or 'red' in cor.lower())]
        
        # Se ainda não tivermos cores suficientes, usamos mais algumas paletas
        if len(empresas_unicas) > len(cores_contorno):
            cores_extras = px.colors.qualitative.Dark24 + px.colors.qualitative.Light24
            cores_extras = [cor for cor in cores_extras if not ('blue' in cor.lower() or 'red' in cor.lower())]
            cores_contorno = cores_contorno + cores_extras
        
        # Garantir que temos cores suficientes
        cores_contorno = cores_contorno[:len(empresas_unicas)]
        
        # Criar mapeamento de empresa para cor
        cores_dict = dict(zip(empresas_unicas, cores_contorno))
    
    # Pivot para ordenar corretamente os dados
    pivot_meses = sorted(df_mensal_empresa["Ano_Mes"].unique())
    
    # Adicionar barras para cada empresa, mantendo a indicação de flexibilização
    for i, empresa in enumerate(empresas_unicas):
        df_empresa = df_mensal_empresa[df_mensal_empresa["NOME_EMPRESARIAL"] == empresa]
        
        # Preparar dados para esse trace
        dados_x = []
        dados_y = []
        cores_barras = []
        
        # Garantir que todos os meses estejam representados (preenchendo com zeros onde necessário)
        for mes in pivot_meses:
            row = df_empresa[df_empresa["Ano_Mes"] == mes]
            
            if len(row) > 0:
                dados_x.append(mes)
                dados_y.append(row["CONSUMO_MWm"].values[0])
                
                # Definir cor de preenchimento baseada na flexibilização
                if row["fora_faixa"].values[0]:
                    cores_barras.append("rgba(220, 20, 60, 1)")  # Crimson com transparência
                else:
                    cores_barras.append("rgba(65, 105, 225, 1)")  # RoyalBlue com transparência
            else:
                dados_x.append(mes)
                dados_y.append(0)
                cores_barras.append("rgba(65, 105, 225, 0.7)")  # RoyalBlue com transparência
        
        # Configurações específicas baseadas no número de empresas
        if multiplas_empresas:
            # Definir contorno com base na preferência do usuário
            cor_contorno_atual = cores_contorno[i % len(cores_contorno)]
            
            # Configurar linha de contorno condicional
            if mostrar_contornos:
                linha_contorno = dict(
                    color=cor_contorno_atual,  # Cor do contorno específica para empresa
                    width=1.5                  # Largura fina mas visível
                )
            else:
                linha_contorno = dict(
                    color="rgba(0,0,0,0)",  # Cor completamente transparente
                    width=0                 # Largura zero - remove completamente a linha
                )
            
            # Com múltiplas empresas: usar barras com contornos coloridos
            fig.add_trace(go.Bar(
                x=dados_x,
                y=dados_y,
                name=empresa,
                marker=dict(
                    color=cores_barras,
                    line=linha_contorno
                ),
                hovertemplate="Empresa: %s <br>Consumo: %%{y:.2f} MWm<extra></extra>" % empresa
            ))
        else:
            # Com uma única empresa: manter o estilo original
            fig.add_trace(go.Bar(
                x=dados_x,
                y=dados_y,
                name=empresa,
                marker_color=cores_barras,
                hovertemplate="Empresa: %s <br> Consumo: %%{y:.2f} MWm<extra></extra>" % empresa
            ))
    
    # Configurar como empilhado apenas se tivermos múltiplas empresas
    if multiplas_empresas:
        fig.update_layout(barmode='stack')
    
    # Adicionar linhas de limite e média
    fig.add_trace(go.Scatter(
        x=pivot_meses,  # Em vez de df_total_mensal["Ano_Mes"]
        y=[media_consumo_ajustada]*len(pivot_meses),
        mode="lines",
        name=f"Média: {media_consumo_ajustada:.2f}",
        line=dict(color="white", dash="dash", width=2),
        hovertemplate="Média: %.2f MWm<extra></extra>" % media_consumo_ajustada
    ))
    
    fig.add_trace(go.Scatter(
        x=pivot_meses,  # Em vez de df_total_mensal["Ano_Mes"]
        y=[lim_sup_user]*len(pivot_meses),
        mode="lines",
        name=f"Limite Superior (+{flex_user}%): {lim_sup_user:.2f}",
        line=dict(color="orange", dash="dot", width=2),
        hovertemplate= "Limite Superior: %.2f MWm<extra></extra>" % lim_sup_user
    ))
    
    fig.add_trace(go.Scatter(
        x=pivot_meses,  # Em vez de df_total_mensal["Ano_Mes"]
        y=[lim_inf_user]*len(pivot_meses),
        mode="lines",
        name=f"Limite Inferior (-{flex_user}%): {lim_inf_user:.2f}",
        line=dict(color="orange", dash="dot", width=2),
        hovertemplate= "Limite Inferior: %.2f MWm<extra></extra>" % lim_inf_user
    ))
    
    # Linhas verticais entre os anos - Versão corrigida
    anos = df_total_mensal["Ano_Mes"].dt.year.unique()
    linhas_verticais = []

    for i, ano in enumerate(anos[:-1]):
        # Encontrar dezembro do ano atual e janeiro do próximo ano
        dezembro = [d for d in pivot_meses if d.year == ano and d.month == 12]
        janeiro = [d for d in pivot_meses if d.year == ano+1 and d.month == 1]
        
        if dezembro and janeiro:
            # Calcular a posição entre dezembro e janeiro
            dezembro = dezembro[0]
            janeiro = janeiro[0]
            
            # Índices dos meses no eixo x para posicionar a linha entre eles
            idx_dezembro = pivot_meses.index(dezembro)
            idx_janeiro = pivot_meses.index(janeiro)
            
            # Posição exata entre as barras
            pos_linha = idx_dezembro + 0.5  # Posição entre dezembro e janeiro
            
            linhas_verticais.append(
                dict(
                    type="line",
                    x0=pos_linha,  # Posição entre as barras
                    x1=pos_linha,  
                    y0=0,
                    y1=1,
                    xref="x",  # Usar coordenadas do eixo x
                    yref="paper",
                    line=dict(color="gray", width=2, dash="dash"),
                    layer="below"
                )
            )

    fig.update_layout(shapes=linhas_verticais)
    
    # Adicionar uma legenda para as cores de flexibilização
    fig.add_trace(go.Bar(
        x=[None],
        y=[None],
        name="Dentro da Flexibilização",
        marker_color="rgba(65, 105, 225, 0.7)",
        showlegend=True
    ))
    
    fig.add_trace(go.Bar(
        x=[None],
        y=[None],
        name="Fora da Flexibilização",
        marker_color="rgba(220, 20, 60, 0.7)",
        showlegend=True
    ))
    
    # Definir o título com base no número de empresas
    if multiplas_empresas:
        # Limitar a quantidade de empresas exibidas no título para evitar títulos muito longos
        if len(empresas_selecionadas) <= 4:
            empresas_titulo = " + ".join(empresas_selecionadas)
            titulo_grafico = f"Histórico de Consumo Mensal - {empresas_titulo}"
        else:
            # Se houver mais de 3 empresas, mostrar as primeiras 2 e indicar quantas mais
            empresas_titulo = f"{' + '.join(empresas_selecionadas[:2])} e mais {len(empresas_selecionadas)-2}"
            titulo_grafico = f"Histórico de Consumo Mensal - {empresas_titulo}"
    else:
        titulo_grafico = f"Histórico de Consumo Mensal - {empresas_selecionadas[0]}"
    
    # Converter dados para um formato adequado para categorias de eixo
    anos_no_grafico = sorted(list(df_total_mensal["Ano_Mes"].dt.year.unique()))
    meses_curtos_pt = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun', 
                      7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}

    # Criar categorias e ticktext personalizados
    # Primeiro extrair o mês e ano de cada timestamp
    categories = []
    ticktext = []
    tickvals = []

    for data in pivot_meses:
        year = data.year
        month = data.month
        categories.append(f"{year}-{month:02d}")
        ticktext.append(meses_curtos_pt[month])
        tickvals.append(data)

    # Configuração do layout com eixo X personalizado 
    fig.update_layout(
        title=titulo_grafico,
        xaxis_title="",  # Remover título do eixo X para melhor visualização
        yaxis_title="Consumo (MWm)",
        template="plotly_white",
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=-0.4,
            xanchor="center", 
            x=0.5,
            font=dict(size=10)
        ),
        hovermode="x unified",
        height=600,
        yaxis=dict(showgrid=False)
    )

    # Configurar eixo X para mostrar meses agrupados por ano com linhas divisórias
    fig.update_xaxes(
        type='category',
        tickvals=tickvals,
        ticktext=ticktext,
        tickangle=0,
        tickmode='array',
        showticklabels=True,
        ticks="outside",  # Mostrar os ticks para fora
        ticklen=6,        # Comprimento do tick aumentado
        tickwidth=1,      # Largura do tick
        tickcolor='white', # Manter cor branca
        linecolor='white', # Manter cor branca
        linewidth=1       # Largura da linha do eixo
    )

    # Adicionar linhas divisórias tracejadas entre dezembro e janeiro
    for i, ano in enumerate(anos[:-1]):
        # Encontrar dezembro do ano atual e janeiro do próximo ano
        dezembro = [d for d in pivot_meses if d.year == ano and d.month == 12]
        janeiro = [d for d in pivot_meses if d.year == ano+1 and d.month == 1]
        
        if dezembro and janeiro:
            # Adicionar uma linha vertical estendida da área de plotagem até o rótulo dos anos
            dezembro = dezembro[0]
            janeiro = janeiro[0]
            
            # Índices dos meses no eixo x para posicionar a linha entre eles
            idx_dezembro = pivot_meses.index(dezembro)
            
            # Adicionar uma linha de extensão tracejada no eixo X
            fig.add_shape(
                type="line",
                x0=idx_dezembro + 0.5,  # Posição entre dezembro e janeiro
                x1=idx_dezembro + 0.5,
                y0=0,          # Começa na base do gráfico
                y1=-0.25,      # Vai além do rótulo do ano
                xref="x",
                yref="paper",
                line=dict(color="gray", width=1.5, dash="dash"),  # Linha branca tracejada
                layer="below"
            )
    
    # Ajustar a adição de rótulos de anos - remover o traço horizontal (por volta da linha 700-720)
    for ano in anos_no_grafico:
        # Encontrar os meses do ano
        meses_do_ano = [d for d in pivot_meses if d.year == ano]
        if meses_do_ano:
            middle_point = meses_do_ano[len(meses_do_ano)//2]
            
            # Rótulo do ano - sem a linha horizontal acima
            fig.add_annotation(
                x=middle_point,
                y=-0.18,
                xref="x", 
                yref="paper",
                text=f"<b>{ano}</b>",
                showarrow=False,
                font=dict(size=14),
            )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Comparação de crescimento ano a ano
    df_mensal_empresa["Ano"] = df_mensal_empresa["Ano_Mes"].dt.year

    # Primeiro somar os consumos de todas as empresas por mês
    soma_mensal = df_mensal_empresa.groupby(["Ano", "Ano_Mes"], observed=True)["CONSUMO_MWm"].sum().reset_index()

    # Depois calcular a média anual dos meses somados
    media_anuais = soma_mensal.groupby("Ano", observed=True)["CONSUMO_MWm"].mean().reset_index()
    media_anuais.columns = ["Ano", "Média Mensal de Consumo (MWm)"]

    media_anuais["Variação (%)"] = media_anuais["Média Mensal de Consumo (MWm)"].pct_change() * 100
    
    st.subheader("📈 Crescimento Anual do Consumo")
    st.dataframe(
        media_anuais.style.format({
            "Média Mensal de Consumo (MWm)": "{:.2f}",
            "Variação (%)": "{:+.2f} %"
        }),
        use_container_width=False,
        hide_index=True
    )
    
    # Filtrar os últimos 12 meses para análise detalhada
    data_limite = df_total_ord["MES_REFERENCIA"].max() - pd.DateOffset(months=12)
    df_ultimos_12_meses = df_total_ord[df_total_ord["MES_REFERENCIA"] >= data_limite].copy()
    
    if not df_ultimos_12_meses.empty:
        # Usar vectorized operations em vez de apply para formatar CNPJs
        if "CNPJ_CARGA" in df_ultimos_12_meses.columns:
            mask = ~df_ultimos_12_meses["CNPJ_CARGA"].isna()
            df_ultimos_12_meses.loc[mask, "CNPJ_CARGA"] = (
                df_ultimos_12_meses.loc[mask, "CNPJ_CARGA"]
                #.astype(float).astype(int).astype(str).str.zfill(14) conversão desnecessária porque foi aplicado as bases de dados
                .str.replace(r'(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})', r'\1.\2.\3/\4-\5', regex=True)
            )

        
        # Resumo de empresas
        resumo_dados = []
        
        for empresa in empresas_selecionadas:
            df_emp_12m = df_ultimos_12_meses[df_ultimos_12_meses["NOME_EMPRESARIAL"] == empresa].copy()
            
            if not df_emp_12m.empty:
                if "SIGLA_PARCELA_CARGA" in df_emp_12m.columns:
                    unidades = df_emp_12m["SIGLA_PARCELA_CARGA"].nunique()
                else:
                    unidades = "N/D"
                    
                if "SUBMERCADO" in df_emp_12m.columns:
                    sub_misto = "Sim" if df_emp_12m["SUBMERCADO"].nunique() > 1 else "Não"
                else:
                    sub_misto = "N/D"
                
                # Determinar centro decisório se tivermos CNPJ_CARGA
                if "CNPJ_CARGA" in df_emp_12m.columns:
                    df_emp_12m["MATRIZ"] = df_emp_12m["CNPJ_CARGA"].str[11:15] == "0001"
                    
                    if "CONSUMO_MWm" in df_emp_12m.columns:
                        consumo_por_cnpj = df_emp_12m.groupby("CNPJ_CARGA", observed=True)["CONSUMO_MWm"].mean().reset_index()
                        df_emp_12m = df_emp_12m.merge(consumo_por_cnpj, on="CNPJ_CARGA", suffixes=("", "_MEDIO"))
                    
                    if "MATRIZ" in df_emp_12m.columns and df_emp_12m["MATRIZ"].any():
                        filtro_matriz = df_emp_12m[df_emp_12m["MATRIZ"]]
                        if not filtro_matriz.empty:
                            centro = filtro_matriz[["CIDADE", "ESTADO_UF", "CNPJ_CARGA"]].iloc[0]
                        else:
                            centro = {"CIDADE": "N/D", "ESTADO_UF": "N/D", "CNPJ_CARGA": ""}
                    else:
                        try:
                            if "CONSUMO_MWm_MEDIO" in df_emp_12m.columns:
                                idx_maior_consumo = df_emp_12m["CONSUMO_MWm_MEDIO"].idxmax()
                                centro = df_emp_12m.loc[idx_maior_consumo, ["CIDADE", "ESTADO_UF", "CNPJ_CARGA"]]
                            else:
                                centro = {"CIDADE": "N/D", "ESTADO_UF": "N/D", "CNPJ_CARGA": ""}
                        except:
                            centro = {"CIDADE": "N/D", "ESTADO_UF": "N/D", "CNPJ_CARGA": ""}
                else:
                    centro = {"CIDADE": "N/D", "ESTADO_UF": "N/D", "CNPJ_CARGA": ""}
                
                resumo_dados.append({
                    "Empresa": empresa,
                    "Unidades": unidades,
                    "Submercado Misto": sub_misto,
                    "Possível Centro Decisório": f"{centro['CIDADE']} / {centro['ESTADO_UF']}",
                    "CNPJ do Centro Decisório": centro["CNPJ_CARGA"]
                })
        
        if resumo_dados:
            resumo_df = pd.DataFrame(resumo_dados)
            st.write("### 📋 Resumo da(s) Empresa(s)")
            st.dataframe(resumo_df, hide_index=True)
        
        # Tabela de percentual de consumo por submercado
        if "SUBMERCADO" in df_ultimos_12_meses.columns and "CONSUMO_MWm" in df_ultimos_12_meses.columns:
            consumo_por_sub = df_ultimos_12_meses.groupby("SUBMERCADO", observed=True).agg({
                "CONSUMO_MWm": "sum"
            }).reset_index()
            
            if "SIGLA_PARCELA_CARGA" in df_ultimos_12_meses.columns:
                unidades_por_sub = df_ultimos_12_meses.groupby("SUBMERCADO", observed=True)["SIGLA_PARCELA_CARGA"].nunique().reset_index()
                consumo_por_sub = consumo_por_sub.merge(unidades_por_sub, on="SUBMERCADO")
                consumo_por_sub.rename(columns={"SIGLA_PARCELA_CARGA": "Unidades"}, inplace=True)
            
            total_consumo = consumo_por_sub["CONSUMO_MWm"].sum()
            consumo_por_sub["Consumo Médio Mensal (MWm)"] = consumo_por_sub["CONSUMO_MWm"] / 12
            
            if total_consumo > 0:
                consumo_por_sub["% do Total"] = (consumo_por_sub["CONSUMO_MWm"] / total_consumo) * 100
            else:
                consumo_por_sub["% do Total"] = 0
            
            consumo_por_sub["% do Total"] = consumo_por_sub["% do Total"].map("{:.2f}%".format)
            consumo_por_sub = consumo_por_sub.drop(columns=["CONSUMO_MWm"])
            
            st.write("### 🌎 Percentual de Consumo por Submercado")
            st.dataframe(consumo_por_sub, hide_index=True)
        
        # Detalhamento por unidade
        if "SIGLA_PARCELA_CARGA" in df_ultimos_12_meses.columns:
            dados_unidades = []
            unidades = df_ultimos_12_meses["SIGLA_PARCELA_CARGA"].unique()
            
            for unidade in unidades:
                df_unidade = df_ultimos_12_meses[df_ultimos_12_meses["SIGLA_PARCELA_CARGA"] == unidade]
                
                if not df_unidade.empty:
                    try:
                        info_unidade = {
                            "Unidade": unidade
                        }
                        
                        # Adicionar informações disponíveis
                        for campo, col in [
                            ("CNPJ", "CNPJ_CARGA"),
                            ("Cidade", "CIDADE"),
                            ("Estado", "ESTADO_UF"),
                            ("Submercado", "SUBMERCADO"),
                            ("Data de Migração", "DATA_MIGRACAO"),
                            ("Demanda", "CAPACIDADE_CARGA")
                        ]:
                            if col in df_unidade.columns:
                                info_unidade[campo] = df_unidade[col].iloc[0]
                            else:
                                info_unidade[campo] = "N/D"
                                
                        # Calcular consumo médio se disponível
                        if "CONSUMO_MWm" in df_unidade.columns:
                            info_unidade["Consumo 12m (MWm)"] = round(df_unidade["CONSUMO_MWm"].mean(), 2)
                        else:
                            info_unidade["Consumo 12m (MWm)"] = "N/D"
                        
                        dados_unidades.append(info_unidade)
                    except Exception as e:
                        st.warning(f"Erro ao processar unidade {unidade}: {e}")
            
            if dados_unidades:
                tabela_unidades = pd.DataFrame(dados_unidades)
                st.write("🏭 Ver Detalhamento por Unidade")
                st.dataframe(tabela_unidades, hide_index=True)


    # Liberar memória ao final
    clear_memory()
else:
    st.info("Selecione pelo menos uma empresa e clique em 'Gerar Gráfico' para visualizar os dados.",icon=":material/info:")
#x = st.sidebar.markdown("<br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br><br>", unsafe_allow_html=True)
#
#col1, col2 = st.sidebar.columns(2, gap="small", vertical_alignment="center",border=False)
#with col1:
#    versao = st.write("Versão: 2.31", unsafe_allow_html=True)