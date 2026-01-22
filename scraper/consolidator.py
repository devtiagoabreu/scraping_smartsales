# consolidator.py - Consolida CSVs de forma robusta
import os
import pandas as pd
from datetime import datetime
import logging
import traceback

logger = logging.getLogger(__name__)

def parsear_descricao_produto(descricao):
    """Extrai informações da descrição do produto"""
    try:
        # Exemplo: "000014 - VELUDO CONFORT - COR: 5 - BLACK"
        partes = descricao.split(' - ')
        
        if len(partes) >= 3:
            # Pegar código e nome do produto (primeiras partes)
            codigo_produto = partes[0]
            nome_produto = partes[1]
            
            # Juntar a parte da cor
            cor_info = ' - '.join(partes[2:])
            
            # Formatar como solicitado
            produto_formatado = f"{codigo_produto} - {nome_produto} - {cor_info}"
            return produto_formatado
        
        return descricao
    except Exception as e:
        logger.warning(f"Erro ao parsear descrição '{descricao}': {e}")
        return descricao

def converter_valor_brasileiro(val):
    """Converte valores no formato brasileiro para numérico"""
    try:
        if pd.isna(val):
            return 0.0
        
        # Converter string
        val_str = str(val).strip()
        
        # Remover pontos de milhar e substituir vírgula decimal por ponto
        if ',' in val_str and '.' in val_str:
            # Formato brasileiro: 1.234,56
            val_str = val_str.replace('.', '').replace(',', '.')
        elif ',' in val_str:
            # Formato com apenas vírgula como decimal
            val_str = val_str.replace(',', '.')
        
        # Tentar converter para float
        return float(val_str)
    except Exception as e:
        logger.warning(f"Erro ao converter valor '{val}': {e}")
        return 0.0

def formatar_valor_brasileiro(val):
    """Formata valor numérico para formato brasileiro"""
    try:
        if pd.isna(val):
            return "0,00"
        
        # Arredondar para 2 casas decimais
        val = round(float(val), 2)
        
        # Formatar com separador de milhar e vírgula decimal
        if val.is_integer():
            return f"{int(val):,}".replace(",", "X").replace(".", ",").replace("X", ".") + ",00"
        else:
            parts = f"{val:,.2f}".split('.')
            inteira = parts[0].replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{inteira},{parts[1]}"
    except Exception as e:
        logger.warning(f"Erro ao formatar valor {val}: {e}")
        return "0,00"

def ordenar_previsao(val):
    """Função para ordenar previsões na ordem desejada"""
    if pd.isna(val):
        return (0, "")  # Primeiro: nulos
    
    val_str = str(val).strip().upper()
    
    # Pronta entrega primeiro
    if 'PRONTA ENTREGA' in val_str:
        return (1, "0000-00-00")  # Primeira posição
    
    try:
        # Tentar parsear data no formato DD/MM/YYYY
        if '/' in val_str:
            day, month, year = map(int, val_str.split('/'))
            return (2, f"{year:04d}-{month:02d}-{day:02d}")
    except:
        pass
    
    # Para outros formatos, manter como string
    return (3, val_str)

def consolidar_dados_estruturados():
    """Consolida todos os CSVs em formato limpo e organizado"""
    try:
        # Verificar se a pasta csv existe
        if not os.path.exists('csv'):
            return None, "Pasta 'csv' não encontrada"
        
        # Listar arquivos CSV
        csv_files = [f for f in os.listdir('csv') if f.endswith('.csv')]
        
        if not csv_files:
            return None, "Nenhum arquivo CSV encontrado na pasta 'csv'"
        
        logger.info(f"📊 Processando {len(csv_files)} arquivos CSV...")
        
        # Ler e consolidar todos os CSVs
        dfs = []
        arquivos_processados = []
        
        for csv_file in csv_files:
            try:
                filepath = os.path.join('csv', csv_file)
                logger.info(f"  → Lendo: {csv_file}")
                
                # Ler CSV com encoding apropriado
                df = pd.read_csv(filepath, delimiter=';', encoding='utf-8-sig')
                
                if not df.empty:
                    # Filtrar apenas colunas necessárias
                    colunas_necessarias = ['Produto / Situação / Cor / Desenho / Variante', 
                                         'Previsão', 'Estoque', 'Pedidos', 'Disponível']
                    
                    # Verificar se temos todas as colunas necessárias
                    colunas_disponiveis = [col for col in colunas_necessarias if col in df.columns]
                    
                    if len(colunas_disponiveis) >= 4:  # Pelo menos as colunas principais
                        # Manter apenas colunas necessárias
                        df = df[colunas_disponiveis].copy()
                        
                        # Renomear coluna do produto
                        df.rename(columns={'Produto / Situação / Cor / Desenho / Variante': 'Produto / Cor'}, 
                                inplace=True)
                        
                        # Parsear e formatar a descrição do produto
                        df['Produto / Cor'] = df['Produto / Cor'].apply(parsear_descricao_produto)
                        
                        # Converter valores para numérico para ordenação correta
                        for col in ['Estoque', 'Pedidos', 'Disponível']:
                            if col in df.columns:
                                df[f'{col}_num'] = df[col].apply(converter_valor_brasileiro)
                        
                        dfs.append(df)
                        arquivos_processados.append(csv_file)
                        
                        logger.info(f"    ✓ {len(df)} registros")
                    else:
                        logger.warning(f"    ✗ Colunas insuficientes em {csv_file}")
                else:
                    logger.warning(f"    ✗ Arquivo vazio: {csv_file}")
                    
            except Exception as e:
                logger.error(f"    ✗ Erro ao processar {csv_file}: {e}")
                continue
        
        if not dfs:
            return None, "Nenhum dado válido encontrado nos arquivos CSV"
        
        # Concatenar todos os DataFrames
        logger.info("Concatenando dados...")
        df_final = pd.concat(dfs, ignore_index=True, sort=False)
        
        # Remover duplicatas
        logger.info("Removendo duplicatas...")
        df_final = df_final.drop_duplicates()
        
        # Ordenar dados
        logger.info("Ordenando dados...")
        
        # Primeiro, ordenar por produto/cor
        if 'Produto / Cor' in df_final.columns:
            df_final = df_final.sort_values('Produto / Cor')
            
            # Adicionar coluna temporária para ordenação de previsão
            df_final['_previsao_ordem'] = df_final['Previsão'].apply(ordenar_previsao)
            
            # Ordenar por produto/cor e previsão
            df_final = df_final.sort_values(['Produto / Cor', '_previsao_ordem'])
            
            # Remover coluna temporária
            df_final = df_final.drop('_previsao_ordem', axis=1)
        
        # Formatar valores no padrão brasileiro
        logger.info("Formatando valores...")
        for col in ['Estoque', 'Pedidos', 'Disponível']:
            if col in df_final.columns and f'{col}_num' in df_final.columns:
                # Manter o formato original ou formatar se necessário
                # Remover a coluna numérica temporária
                df_final = df_final.drop(f'{col}_num', axis=1)
        
        # Gerar timestamp para nome dos arquivos
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Salvar CSV consolidado
        csv_filename = f"consolidado_organizado_{timestamp}.csv"
        csv_path = os.path.join('csv', csv_filename)
        
        # Salvar apenas colunas necessárias na ordem correta
        colunas_saida = ['Produto / Cor', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        colunas_saida = [col for col in colunas_saida if col in df_final.columns]
        
        df_saida = df_final[colunas_saida].copy()
        df_saida.to_csv(csv_path, sep=';', index=False, encoding='utf-8-sig')
        logger.info(f"✅ CSV consolidado organizado salvo: {csv_filename}")
        
        # Criar Excel com abas por produto
        excel_filename = f"consolidado_organizado_{timestamp}.xlsx"
        excel_path = os.path.join('xlsx', excel_filename)
        
        logger.info("Criando arquivo Excel...")
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Aba com todos os dados
            df_saida.to_excel(writer, sheet_name='TODOS OS DADOS', index=False)
            logger.info("  ✓ Aba 'TODOS OS DADOS' criada")
            
            # Criar abas por produto (limitar a 50 produtos para não exceder limite do Excel)
            if 'Produto / Cor' in df_final.columns:
                # Extrair código do produto para agrupamento
                def extrair_codigo_produto(descricao):
                    try:
                        # Exemplo: "000014 - VELUDO CONFORT - COR: 5 - BLACK"
                        partes = descricao.split(' - ')
                        return partes[0] if len(partes) > 0 else descricao
                    except:
                        return descricao
                
                df_final['codigo_produto'] = df_final['Produto / Cor'].apply(extrair_codigo_produto)
                produtos_unicos = df_final['codigo_produto'].unique()
                
                if len(produtos_unicos) > 0:
                    produtos_unicos = produtos_unicos[:50]  # Limitar a 50 abas
                    
                    for produto in produtos_unicos:
                        try:
                            df_produto = df_final[df_final['codigo_produto'] == produto]
                            # Remover coluna temporária
                            df_produto = df_produto[colunas_saida].copy()
                            
                            # Ordenar por cor e previsão
                            if 'Produto / Cor' in df_produto.columns:
                                df_produto['_previsao_ordem'] = df_produto['Previsão'].apply(ordenar_previsao)
                                df_produto = df_produto.sort_values(['Produto / Cor', '_previsao_ordem'])
                                df_produto = df_produto.drop('_previsao_ordem', axis=1)
                            
                            nome_aba = f"ART_{produto}"[:31]  # Excel limita a 31 caracteres
                            df_produto.to_excel(writer, sheet_name=nome_aba, index=False)
                            logger.info(f"  ✓ Aba para produto {produto} criada")
                        except Exception as e:
                            logger.warning(f"  ✗ Erro ao criar aba para {produto}: {e}")
                            continue
        
        logger.info(f"✅ Excel criado: {excel_filename}")
        
        # Estatísticas finais
        total_registros = len(df_saida)
        produtos_unicos = len(set(df_final['codigo_produto'])) if 'codigo_produto' in df_final.columns else 0
        
        resultado = {
            'arquivo_csv': csv_filename,
            'arquivo_excel': excel_filename,
            'total_registros': total_registros,
            'produtos_unicos': produtos_unicos,
            'arquivos_processados': len(arquivos_processados),
            'timestamp': timestamp
        }
        
        mensagem = f"✅ Consolidação concluída: {total_registros} registros de {len(arquivos_processados)} arquivos"
        logger.info(mensagem)
        
        return resultado, mensagem
        
    except Exception as e:
        logger.error(f"❌ Erro na consolidação: {e}")
        logger.error(traceback.format_exc())
        return None, str(e)

# Função para uso direto
if __name__ == "__main__":
    # Configurar logging básico
    logging.basicConfig(level=logging.INFO, 
                       format='%(asctime)s - %(levelname)s - %(message)s')
    
    resultado, mensagem = consolidar_dados_estruturados()
    if resultado:
        print(f"\n{mensagem}")
        print(f"📁 CSV: {resultado['arquivo_csv']}")
        print(f"📁 Excel: {resultado['arquivo_excel']}")
        print(f"📊 Registros: {resultado['total_registros']}")
        print(f"🔢 Produtos únicos: {resultado['produtos_unicos']}")
    else:
        print(f"❌ {mensagem}")