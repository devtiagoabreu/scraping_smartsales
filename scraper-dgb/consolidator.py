# consolidator.py - Consolida CSVs
import os
import pandas as pd
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def consolidar_dados_estruturados():
    """Consolida todos os CSVs"""
    try:
        csv_files = [f for f in os.listdir('csv') if f.endswith('.csv')]
        
        if not csv_files:
            return None, "Nenhum arquivo CSV encontrado"
        
        logger.info(f"Processando {len(csv_files)} arquivos CSV")
        
        # Ler e consolidar todos os CSVs
        dfs = []
        for csv_file in csv_files:
            try:
                df = pd.read_csv(f'csv/{csv_file}', delimiter=';', encoding='utf-8-sig')
                dfs.append(df)
                logger.info(f"  → {csv_file}: {len(df)} registros")
            except Exception as e:
                logger.warning(f"  → Erro em {csv_file}: {e}")
        
        if not dfs:
            return None, "Nenhum dado válido encontrado"
        
        # Concatenar todos
        df_final = pd.concat(dfs, ignore_index=True)
        
        # Remover duplicatas
        df_final = df_final.drop_duplicates()
        
        # Salvar CSV consolidado
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"consolidado_{timestamp}.csv"
        excel_filename = f"consolidado_{timestamp}.xlsx"
        
        df_final.to_csv(f'csv/{csv_filename}', sep=';', index=False, encoding='utf-8-sig')
        
        # Criar Excel com abas por produto
        with pd.ExcelWriter(f'csv/{excel_filename}', engine='openpyxl') as writer:
            # Aba com todos os dados
            df_final.to_excel(writer, sheet_name='TODOS OS DADOS', index=False)
            
            # Abas por produto
            produtos = df_final['artigo'].unique()
            for produto in produtos[:50]:  # Limitar a 50 abas
                df_produto = df_final[df_final['artigo'] == produto]
                nome_aba = f"ART_{produto}"[:31]  # Excel limita a 31 caracteres
                df_produto.to_excel(writer, sheet_name=nome_aba, index=False)
        
        resultado = {
            'arquivo_csv': csv_filename,
            'arquivo_excel': excel_filename,
            'total_registros': len(df_final),
            'produtos_unicos': len(produtos)
        }
        
        return resultado, f"Consolidado: {len(df_final)} registros de {len(csv_files)} arquivos"
        
    except Exception as e:
        logger.error(f"Erro na consolidação: {e}")
        return None, str(e)