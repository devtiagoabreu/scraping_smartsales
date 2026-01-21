# consolidator.py - Consolida CSVs de forma robusta
import os
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def consolidar_dados_estruturados():
    """Consolida todos os CSVs"""
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
                    # Adicionar coluna com nome do arquivo de origem
                    df['arquivo_origem'] = csv_file
                    dfs.append(df)
                    arquivos_processados.append(csv_file)
                    
                    logger.info(f"    ✓ {len(df)} registros")
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
        
        # Ordenar por artigo e previsão
        if 'artigo' in df_final.columns and 'Previsão' in df_final.columns:
            df_final = df_final.sort_values(['artigo', 'Previsão'])
        
        # Gerar timestamp para nome dos arquivos
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Salvar CSV consolidado
        csv_filename = f"consolidado_{timestamp}.csv"
        csv_path = os.path.join('csv', csv_filename)
        df_final.to_csv(csv_path, sep=';', index=False, encoding='utf-8-sig')
        logger.info(f"✅ CSV consolidado salvo: {csv_filename}")
        
        # Criar Excel com abas por produto
        excel_filename = f"consolidado_{timestamp}.xlsx"
        excel_path = os.path.join('csv', excel_filename)
        
        logger.info("Criando arquivo Excel...")
        
        with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
            # Aba com todos os dados
            df_final.to_excel(writer, sheet_name='TODOS OS DADOS', index=False)
            logger.info("  ✓ Aba 'TODOS OS DADOS' criada")
            
            # Criar abas por produto (limitar a 50 produtos para não exceder limite do Excel)
            produtos = df_final['artigo'].unique() if 'artigo' in df_final.columns else []
            
            if len(produtos) > 0:
                produtos = produtos[:50]  # Limitar a 50 abas
                
                for produto in produtos:
                    try:
                        df_produto = df_final[df_final['artigo'] == produto]
                        nome_aba = f"ART_{produto}"[:31]  # Excel limita a 31 caracteres
                        df_produto.to_excel(writer, sheet_name=nome_aba, index=False)
                        logger.info(f"  ✓ Aba para produto {produto} criada")
                    except Exception as e:
                        logger.warning(f"  ✗ Erro ao criar aba para {produto}: {e}")
                        continue
            
            # Aba de resumo
            try:
                if 'artigo' in df_final.columns and 'Estoque' in df_final.columns:
                    # Converter valores para numérico
                    def converter_valor(val):
                        try:
                            if pd.isna(val):
                                return 0.0
                            val_str = str(val).replace('.', '').replace(',', '.')
                            return float(val_str)
                        except:
                            return 0.0
                    
                    df_final['estoque_numerico'] = df_final['Estoque'].apply(converter_valor)
                    
                    resumo = df_final.groupby('artigo').agg({
                        'estoque_numerico': 'sum'
                    }).reset_index()
                    
                    # Converter de volta para formato brasileiro
                    def formatar_brasileiro(val):
                        try:
                            val_str = f"{val:,.2f}"
                            return val_str.replace(',', 'X').replace('.', ',').replace('X', '.')
                        except:
                            return "0,00"
                    
                    resumo['Estoque Total'] = resumo['estoque_numerico'].apply(formatar_brasileiro)
                    resumo = resumo[['artigo', 'Estoque Total']]
                    
                    resumo.to_excel(writer, sheet_name='RESUMO', index=False)
                    logger.info("  ✓ Aba 'RESUMO' criada")
            except Exception as e:
                logger.warning(f"  ✗ Erro ao criar aba RESUMO: {e}")
        
        logger.info(f"✅ Excel criado: {excel_filename}")
        
        # Estatísticas finais
        total_registros = len(df_final)
        produtos_unicos = len(produtos) if 'artigo' in df_final.columns else 0
        
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
        import traceback
        logger.error(traceback.format_exc())
        return None, str(e)

# Função para uso direto
if __name__ == "__main__":
    resultado, mensagem = consolidar_dados_estruturados()
    if resultado:
        print(f"\n{mensagem}")
        print(f"📁 CSV: {resultado['arquivo_csv']}")
        print(f"📁 Excel: {resultado['arquivo_excel']}")
        print(f"📊 Registros: {resultado['total_registros']}")
        print(f"🔢 Produtos únicos: {resultado['produtos_unicos']}")
    else:
        print(f"❌ {mensagem}")