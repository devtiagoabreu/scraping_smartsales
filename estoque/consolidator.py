# consolidator.py - VERSÃO COMPLETAMENTE CORRIGIDA
import os
import re
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional, Tuple
import json

logger = logging.getLogger(__name__)

class DGBDataProcessor:
    """Processa dados do DGB no formato correto"""
    
    def __init__(self, csv_folder: str = "data/csv", output_folder: str = "data/consolidated"):
        self.csv_folder = csv_folder
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
    
    def processar_csv_estruturado(self, arquivo_path: str) -> List[Dict[str, Any]]:
        """Processa arquivo CSV no formato estruturado"""
        dados_processados = []
        
        try:
            logger.info(f"Processando arquivo: {os.path.basename(arquivo_path)}")
            
            # Ler arquivo CSV
            df = pd.read_csv(arquivo_path, delimiter=';', encoding='utf-8-sig')
            
            # Verificar colunas
            required_columns = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante',
                              'Previsão', 'Estoque', 'Pedidos', 'Disponível']
            
            for _, row in df.iterrows():
                try:
                    # Extrair informações
                    artigo = str(row['artigo']).strip()
                    datahora = row['datahora']
                    descricao_completa = str(row['Produto / Situação / Cor / Desenho / Variante']).strip()
                    previsao = str(row['Previsão']).strip()
                    
                    # Converter valores
                    estoque = self.converter_valor(row['Estoque'])
                    pedidos = self.converter_valor(row['Pedidos'])
                    disponivel = self.converter_valor(row['Disponível'])
                    
                    # Extrair informações detalhadas da descrição
                    info_detalhada = self.extrair_info_detalhada(descricao_completa, artigo)
                    
                    # Criar registro estruturado
                    registro = {
                        'ARTIGO': info_detalhada['artigo'],
                        'DESCRICAO': info_detalhada['descricao'],
                        'COR_CODIGO': info_detalhada['cor_codigo'],
                        'COR': info_detalhada['cor_nome'],
                        'DESENHO': info_detalhada['desenho'],
                        'VARIANTE': info_detalhada['variante'],
                        'SITUACAO': info_detalhada['situacao'],
                        'PREVISAO': previsao,
                        'ESTOQUE': self.formatar_valor(estoque),
                        'PEDIDOS': self.formatar_valor(pedidos),
                        'DISPONIVEL': self.formatar_valor(disponivel),
                        'DATAHORA': datahora
                    }
                    
                    dados_processados.append(registro)
                    
                except Exception as e:
                    logger.warning(f"Erro ao processar linha: {e}")
                    continue
            
            logger.info(f"Processados {len(dados_processados)} registros de {len(df)} linhas")
            
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {arquivo_path}: {e}")
        
        return dados_processados
    
    def extrair_info_detalhada(self, descricao: str, artigo_padrao: str) -> Dict[str, str]:
        """Extrai informações detalhadas da descrição do produto"""
        info = {
            'artigo': artigo_padrao.zfill(6),
            'descricao': 'PRODUTO ' + artigo_padrao,
            'cor_codigo': '00000',
            'cor_nome': 'NÃO IDENTIFICADA',
            'desenho': 'LISO',
            'variante': 'PADRÃO',
            'situacao': 'TINTO'
        }
        
        try:
            # Procurar código de 6 dígitos
            match_artigo = re.search(r'(\d{6})', descricao)
            if match_artigo:
                info['artigo'] = match_artigo.group(1)
            
            # Procurar nome do produto após o código
            match_desc = re.search(r'\d{6}\s+([A-Z][A-Z\s]+?)(?=\s+\d{3}|$)', descricao)
            if match_desc:
                info['descricao'] = match_desc.group(1).strip()
            
            # Procurar situação
            match_situacao = re.search(r'\d{3}\s+(TINTO|CRU|ESTAMPADO)', descricao, re.IGNORECASE)
            if match_situacao:
                info['situacao'] = match_situacao.group(1).upper()
            
            # Procurar cor
            match_cor = re.search(r'/\s*(\d{5})\s+(\d+)\s*-\s*([A-Z\s]+)', descricao)
            if match_cor:
                info['cor_codigo'] = match_cor.group(1)
                info['cor_nome'] = f"{match_cor.group(2)} - {match_cor.group(3).strip()}"
            
            # Procurar desenho
            match_desenho = re.search(r'(\d{5})\s+(LISO|ESTAMPADO)', descricao, re.IGNORECASE)
            if match_desenho:
                info['desenho'] = match_desenho.group(2).upper()
            
            # Procurar variante
            match_variante = re.search(r'(\d{5})\s+(Padrao|Padrão)', descricao, re.IGNORECASE)
            if match_variante:
                info['variante'] = 'PADRÃO'
                
        except Exception as e:
            logger.debug(f"Erro ao extrair info detalhada: {e}")
        
        return info
    
    def converter_valor(self, valor) -> float:
        """Converte valor string para float"""
        try:
            if pd.isna(valor):
                return 0.0
            
            valor_str = str(valor).strip()
            # Remover pontos de milhar e converter vírgula para ponto
            valor_str = valor_str.replace('.', '').replace(',', '.')
            return float(valor_str)
        except:
            return 0.0
    
    def formatar_valor(self, valor: float) -> str:
        """Formata valor float para string brasileira"""
        try:
            # Formatar com separador de milhar e vírgula decimal
            valor_str = f"{valor:,.2f}"
            valor_str = valor_str.replace(',', 'X').replace('.', ',').replace('X', '.')
            return valor_str
        except:
            return "0,00"
    
    def consolidar_todos_arquivos(self) -> Tuple[pd.DataFrame, str]:
        """Consolida todos os arquivos CSV"""
        todos_dados = []
        
        logger.info("=" * 60)
        logger.info("INICIANDO CONSOLIDAÇÃO DOS DADOS")
        logger.info("=" * 60)
        
        # Listar arquivos CSV
        csv_files = list(Path(self.csv_folder).glob("produto_*.csv"))
        
        if not csv_files:
            return pd.DataFrame(), "Nenhum arquivo CSV encontrado"
        
        logger.info(f"Encontrados {len(csv_files)} arquivos CSV")
        
        # Processar cada arquivo
        for csv_file in csv_files:
            logger.info(f"Processando: {csv_file.name}")
            dados = self.processar_csv_estruturado(str(csv_file))
            if dados:
                todos_dados.extend(dados)
                logger.info(f"  → {len(dados)} registros extraídos")
        
        if not todos_dados:
            return pd.DataFrame(), "Nenhum dado extraído dos arquivos"
        
        # Criar DataFrame
        df = pd.DataFrame(todos_dados)
        
        # Ordenar colunas
        colunas_ordem = ['ARTIGO', 'DESCRICAO', 'COR_CODIGO', 'COR', 'DESENHO', 
                        'VARIANTE', 'SITUACAO', 'PREVISAO', 'ESTOQUE', 
                        'PEDIDOS', 'DISPONIVEL', 'DATAHORA']
        
        # Manter apenas colunas existentes
        colunas_existentes = [col for col in colunas_ordem if col in df.columns]
        df = df[colunas_existentes]
        
        # Ordenar dados
        df = df.sort_values(['ARTIGO', 'COR', 'PREVISAO']).reset_index(drop=True)
        
        # Estatísticas
        total_registros = len(df)
        total_estoque = sum(self.converter_valor(v) for v in df['ESTOQUE'])
        total_pedidos = sum(self.converter_valor(v) for v in df['PEDIDOS'])
        total_disponivel = sum(self.converter_valor(v) for v in df['DISPONIVEL'])
        
        logger.info("=" * 60)
        logger.info("CONSOLIDAÇÃO CONCLUÍDA")
        logger.info(f"Total de registros: {total_registros}")
        logger.info(f"Total de estoque: {total_estoque:,.2f}")
        logger.info(f"Total de pedidos: {total_pedidos:,.2f}")
        logger.info(f"Total disponível: {total_disponivel:,.2f}")
        logger.info(f"Produtos únicos: {df['ARTIGO'].nunique()}")
        logger.info(f"Cores únicas: {df['COR'].nunique()}")
        logger.info("=" * 60)
        
        mensagem = f"Processados {len(csv_files)} arquivos, {total_registros} registros"
        return df, mensagem
    
    def gerar_csv_consolidado(self, df: pd.DataFrame) -> str:
        """Gera CSV consolidado"""
        if df.empty:
            return ""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"consolidado_final_{timestamp}.csv"
        filepath = os.path.join(self.output_folder, filename)
        
        # Salvar CSV
        df.to_csv(filepath, sep=';', index=False, encoding='utf-8-sig')
        
        logger.info(f"CSV consolidado gerado: {filename}")
        return filename
    
    def gerar_excel_completo(self, df: pd.DataFrame) -> str:
        """Gera Excel com múltiplas abas"""
        if df.empty:
            return ""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"consolidado_completo_{timestamp}.xlsx"
        filepath = os.path.join(self.output_folder, filename)
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # Aba 1: Todos os dados
            df.to_excel(writer, sheet_name='TODOS OS DADOS', index=False)
            
            # Aba 2: Resumo por produto
            if 'ARTIGO' in df.columns:
                resumo_produto = df.groupby('ARTIGO').agg({
                    'DESCRICAO': 'first',
                    'ESTOQUE': lambda x: self.somar_valores(x),
                    'PEDIDOS': lambda x: self.somar_valores(x),
                    'DISPONIVEL': lambda x: self.somar_valores(x)
                }).reset_index()
                resumo_produto.to_excel(writer, sheet_name='RESUMO POR PRODUTO', index=False)
            
            # Aba 3: Resumo por cor
            if 'COR' in df.columns and 'ARTIGO' in df.columns:
                resumo_cor = df.groupby(['ARTIGO', 'COR']).agg({
                    'DESCRICAO': 'first',
                    'ESTOQUE': lambda x: self.somar_valores(x),
                    'PEDIDOS': lambda x: self.somar_valores(x),
                    'DISPONIVEL': lambda x: self.somar_valores(x)
                }).reset_index()
                resumo_cor.to_excel(writer, sheet_name='RESUMO POR COR', index=False)
            
            # Aba 4: Pronta entrega
            if 'PREVISAO' in df.columns:
                pronta_entrega = df[df['PREVISAO'].str.contains('Pronta entrega', case=False, na=False)]
                if not pronta_entrega.empty:
                    pronta_entrega.to_excel(writer, sheet_name='PRONTA ENTREGA', index=False)
            
            # Aba 5: Datas futuras
            if 'PREVISAO' in df.columns:
                datas_futuras = df[~df['PREVISAO'].str.contains('Pronta entrega', case=False, na=False)]
                if not datas_futuras.empty:
                    datas_futuras.to_excel(writer, sheet_name='DATAS FUTURAS', index=False)
            
            # Aba 6: Tabela Pivot
            if 'ARTIGO' in df.columns and 'COR' in df.columns and 'DISPONIVEL' in df.columns:
                try:
                    # Converter DISPONIVEL para numérico
                    df_pivot = df.copy()
                    df_pivot['DISPONIVEL_NUM'] = df_pivot['DISPONIVEL'].apply(self.converter_valor)
                    
                    pivot = pd.pivot_table(df_pivot, 
                                         values='DISPONIVEL_NUM',
                                         index='ARTIGO',
                                         columns='COR',
                                         aggfunc='sum',
                                         fill_value=0)
                    
                    pivot.to_excel(writer, sheet_name='TABELA PIVOT')
                except Exception as e:
                    logger.warning(f"Não foi possível criar tabela pivot: {e}")
        
        logger.info(f"Excel completo gerado: {filename}")
        return filename
    
    def somar_valores(self, serie):
        """Soma valores de uma série"""
        total = 0.0
        for valor in serie:
            total += self.converter_valor(valor)
        return self.formatar_valor(total)
    
    def gerar_resumo_json(self, df: pd.DataFrame, csv_files: List[str]) -> Dict[str, Any]:
        """Gera resumo em formato JSON"""
        if df.empty:
            return {}
        
        # Calcular totais
        total_estoque = sum(self.converter_valor(v) for v in df['ESTOQUE'])
        total_pedidos = sum(self.converter_valor(v) for v in df['PEDIDOS'])
        total_disponivel = sum(self.converter_valor(v) for v in df['DISPONIVEL'])
        
        resumo = {
            'data_consolidacao': datetime.now().isoformat(),
            'total_registros': len(df),
            'total_estoque': total_estoque,
            'total_pedidos': total_pedidos,
            'total_disponivel': total_disponivel,
            'produtos_unicos': df['ARTIGO'].nunique(),
            'cores_unicas': df['COR'].nunique(),
            'arquivos_processados': len(csv_files),
            'estoque_por_produto': {},
            'disponivel_por_cor': {}
        }
        
        # Estoque por produto
        if 'ARTIGO' in df.columns and 'ESTOQUE' in df.columns:
            estoque_por_produto = df.groupby('ARTIGO')['ESTOQUE'].apply(
                lambda x: self.formatar_valor(sum(self.converter_valor(v) for v in x))
            ).to_dict()
            resumo['estoque_por_produto'] = estoque_por_produto
        
        # Disponível por cor
        if 'COR' in df.columns and 'DISPONIVEL' in df.columns:
            disponivel_por_cor = df.groupby('COR')['DISPONIVEL'].apply(
                lambda x: self.formatar_valor(sum(self.converter_valor(v) for v in x))
            ).to_dict()
            resumo['disponivel_por_cor'] = disponivel_por_cor
        
        return resumo

def consolidar_dados_estruturados():
    """Função principal para consolidação"""
    try:
        logger.info("Iniciando consolidação de dados...")
        
        processor = DGBDataProcessor()
        
        # Consolidar dados
        df, mensagem = processor.consolidar_todos_arquivos()
        
        if df.empty:
            return None, mensagem
        
        # Listar arquivos processados
        csv_files = list(Path(processor.csv_folder).glob("produto_*.csv"))
        
        # Gerar arquivos
        csv_filename = processor.gerar_csv_consolidado(df)
        excel_filename = processor.gerar_excel_completo(df)
        
        # Gerar resumo JSON
        resumo = processor.gerar_resumo_json(df, csv_files)
        
        # Salvar JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f"resumo_consolidacao_{timestamp}.json"
        json_path = os.path.join(processor.output_folder, json_filename)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(resumo, f, ensure_ascii=False, indent=2)
        
        # Preparar resultado
        resultado = {
            'data_consolidacao': datetime.now().isoformat(),
            'total_registros': len(df),
            'total_estoque': resumo.get('total_estoque', 0),
            'total_pedidos': resumo.get('total_pedidos', 0),
            'total_disponivel': resumo.get('total_disponivel', 0),
            'produtos_unicos': df['ARTIGO'].nunique(),
            'cores_unicas': df['COR'].nunique(),
            'arquivos_processados': len(csv_files),
            'arquivo_csv': csv_filename,
            'arquivo_excel': excel_filename,
            'arquivo_json': json_filename,
            'mensagem': mensagem
        }
        
        logger.info("Consolidação concluída com sucesso!")
        
        return resultado, mensagem
        
    except Exception as e:
        logger.error(f"Erro na consolidação: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None, str(e)

# Função principal para execução direta
if __name__ == "__main__":
    resultado, mensagem = consolidar_dados_estruturados()
    if resultado:
        print(f"✅ Consolidação concluída: {mensagem}")
        print(f"📊 Registros: {resultado['total_registros']}")
        print(f"📁 CSV: {resultado['arquivo_csv']}")
        print(f"📁 Excel: {resultado['arquivo_excel']}")
    else:
        print(f"❌ Erro: {mensagem}")