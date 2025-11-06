import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# URL base da API
API_URL = "https://dadosabertos.camara.leg.br/api/v2"

# Função para buscar o ID do deputado pelo nome
# Usamos o @st.cache_data para evitar fazer a mesma busca várias vezes
@st.cache_data
def buscar_deputado_id(nome):
    """Busca um deputado pelo nome e retorna seu ID, nome oficial, partido e UF."""
    try:
        url_busca = f"{API_URL}/deputados"
        params = {'nome': nome, 'ordem': 'ASC', 'ordenarPor': 'nome'}
        
        response = requests.get(url_busca, params=params)
        response.raise_for_status() # Verifica se houve erro na requisição
        
        dados = response.json()
        
        if dados['dados']:
            # Pega o primeiro resultado da busca
            primeiro_resultado = dados['dados'][0]
            return {
                'id': primeiro_resultado['id'],
                'nome': primeiro_resultado['nome'],
                'partido': primeiro_resultado['siglaPartido'],
                'uf': primeiro_resultado['siglaUf']
            }
        else:
            return None
            
    except requests.exceptions.RequestException as e:
        st.error(f"Erro ao buscar deputado: {e}")
        return None

# Função para buscar TODAS as despesas de um deputado
# Usamos o @st.cache_data para guardar o resultado
@st.cache_data
def buscar_todas_despesas(deputado_id):
    """Busca todas as despesas de um deputado, paginando os resultados."""
    todas_despesas = []
    pagina = 1
    
    # Loop para percorrer todas as páginas de resultados
    while True:
        try:
            url_despesas = f"{API_URL}/deputados/{deputado_id}/despesas"
            # Pedimos 100 itens por página (o máximo)
            params = {'pagina': pagina, 'itens': 100, 'ordenarPor': 'dataDocumento'}
            
            response = requests.get(url_despesas, params=params)
            response.raise_for_status()
            
            dados = response.json()
            
            if dados['dados']:
                todas_despesas.extend(dados['dados'])
                # Verifica se há uma próxima página (link 'next')
                links = {link['rel']: link['href'] for link in dados['links']}
                if 'next' not in links:
                    break # Se não há 'next', saímos do loop
                pagina += 1
            else:
                break # Se 'dados' está vazio, saímos
                
        except requests.exceptions.RequestException as e:
            st.error(f"Erro ao buscar despesas (página {pagina}): {e}")
            break # Interrompe em caso de erro
            
    return todas_despesas


# --- Início da Interface do Streamlit ---

st.set_page_config(layout="wide")
st.title("📊 Analisador de Despesas de Deputados Federais")

# Campo de busca
nome_deputado = st.text_input("Digite o nome do deputado(a):", placeholder="Ex: Maria do Rosário")

if st.button("Pesquisar Despesas"):
    if not nome_deputado:
        st.warning("Por favor, digite um nome para a busca.")
    else:
        # 1. Buscar o Deputado
        with st.spinner(f"Buscando por '{nome_deputado}'..."):
            info_deputado = buscar_deputado_id(nome_deputado)
        
        if not info_deputado:
            st.error("Nenhum deputado encontrado com esse nome. Tente novamente.")
        else:
            id_encontrado = info_deputado['id']
            nome_encontrado = info_deputado['nome']
            partido_uf = f"{info_deputado['partido']}-{info_deputado['uf']}"
            
            st.success(f"Deputado encontrado: **{nome_encontrado} ({partido_uf})**")
            
            # 2. Buscar as Despesas
            with st.spinner(f"Buscando todas as despesas de {nome_encontrado}... (Isso pode levar um momento)"):
                lista_despesas = buscar_todas_despesas(id_encontrado)
            
            if not lista_despesas:
                st.info("Este deputado não possui registros de despesas.")
            else:
                # 3. Processar e Plotar
                st.info(f"Total de {len(lista_despesas)} registros de despesa encontrados.")
                
                # Criar um DataFrame do Pandas
                df = pd.DataFrame(lista_despesas)
                
                # Garantir que o valor líquido é numérico
                df['valorLiquido'] = pd.to_numeric(df['valorLiquido'])
                
                # Agrupar por categoria (tipoDespesa) e somar os valores
                despesas_agrupadas = df.groupby('tipoDespesa')['valorLiquido'].sum().reset_index()
                
                # Renomear colunas para o gráfico
                despesas_agrupadas.columns = ['Tipo de Despesa', 'Valor Total (R$)']
                
                # Ordenar do maior para o menor
                despesas_agrupadas = despesas_agrupadas.sort_values(by='Valor Total (R$)', ascending=False)
                
                # 4. Criar o Gráfico com Plotly
                fig = px.bar(
                    despesas_agrupadas,
                    x='Tipo de Despesa',
                    y='Valor Total (R$)',
                    title=f"Total de Despesas por Categoria - {nome_encontrado}",
                    labels={'Valor Total (R$)': 'Valor Total (R$)', 'Tipo de Despesa': 'Categoria'},
                    hover_data=['Tipo de Despesa', 'Valor Total (R$)']
                )
                
                # Adiciona formatação de moeda ao "hover"
                fig.update_traces(hovertemplate='<b>%{x}</b><br>Valor: R$ %{y:,.2f}')
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Opcional: Mostrar tabela com os dados
                st.subheader("Dados Agrupados")
                st.dataframe(despesas_agrupadas.style.format({'Valor Total (R$)': 'R$ {:,.2f}'}))
