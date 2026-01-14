# consolidator_v2.py (ou atualize o consolidator.py existente)
import os
import re
import pandas as pd
import numpy as np
from datetime import datetime
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional, Tuple
import json
import csv

logger = logging.getLogger(__name__)

class DGBDataExtractorFormatado:
    """Extrator específico para o formato gerado pelo scraper atual"""
    
    def __init__(self, csv_folder: str = "data/csv", output_folder: str = "data/consolidated"):
        self.csv_folder = csv_folder
        self.output_folder = output_folder
        os.makedirs(output_folder, exist_ok=True)
    
    def parse_valor(self, valor_str: str) -> float:
        """Converte string de valor brasileiro para float"""
        if not valor_str or valor_str.strip() == '':
            return 0.0
        
        try:
            # Remove pontos de milhar e converte vírgula decimal para ponto
            valor_str = valor_str.replace('.', '').replace(',', '.')
            return float(valor_str)
        except:
            return 0.0
    
    def processar_linha_produto(self, texto: str, codigo_produto: str) -> List[Dict[str, Any]]:
        """Processa uma linha que contém dados de produto no formato específico"""
        dados = []
        
        try:
            # Exemplo de linha: 
            # "000014 VELUDO CONFORT 001 TINTO / 00005 5 - BLACK 00000 LISO / 00000 Padrao Previsão Pronta entrega Estoque 16.605,30 Pedidos 16.605,30 Disponível 0,00 Previsão 19/01/2026 Estoque 14.766,10 Pedidos 6.544,70 Disponível 8.221,40 ..."
            
            # Primeiro, extrair informações do produto
            produto_info = self.extrair_info_produto(texto)
            if not produto_info:
                # Usar código do arquivo como fallback
                produto_info = {
                    'ARTIGO': codigo_produto.zfill(6),
                    'DESCRICAO': f"PRODUTO {codigo_produto}",
                    'COR_CODIGO': '00000',
                    'COR': 'NÃO IDENTIFICADA',
                    'DESENHO': 'LISO',
                    'VARIANTE': 'PADRÃO',
                    'SITUACAO': 'TINTO'
                }
            
            # Agora extrair os dados de previsão/estoque
            previsoes = self.extrair_dados_previsao(texto)
            
            for previsao in previsoes:
                registro = {**produto_info, **previsao}
                dados.append(registro)
                
        except Exception as e:
            logger.error(f"Erro ao processar linha de produto: {e}")
            logger.debug(f"Texto da linha: {texto[:200]}")
        
        return dados
    
    def extrair_info_produto(self, texto: str) -> Optional[Dict[str, Any]]:
        """Extrai informações do produto do texto"""
        try:
            # Padrão: "000014 VELUDO CONFORT 001 TINTO / 00005 5 - BLACK 00000 LISO / 00000 Padrao"
            padrao = re.compile(
                r'^(?P<codigo>\d{6})\s+'  # 000014
                r'(?P<descricao>.+?)\s+'  # VELUDO CONFORT
                r'\d{3}\s+'  # 001
                r'(?P<situacao>[A-Z]+)\s*/\s*'  # TINTO /
                r'(?P<cod_cor>\d{5})\s+'  # 00005
                r'(?P<cor_num>\d+)\s*-\s*'  # 5 -
                r'(?P<cor_nome>.+?)\s+'  # BLACK
                r'\d{5}\s+'  # 00000
                r'(?P<desenho>[A-Z]+)\s*/\s*'  # LISO /
                r'\d{5}\s+'  # 00000
                r'(?P<variante>.+?)\s+'  # Padrao
            )
            
            match = padrao.search(texto)
            if match:
                dados = match.groupdict()
                return {
                    'ARTIGO': dados['codigo'].strip(),
                    'DESCRICAO': dados['descricao'].strip(),
                    'COR_CODIGO': dados['cod_cor'].strip(),
                    'COR': f"{dados['cor_num'].strip()} - {dados['cor_nome'].strip()}",
                    'DESENHO': dados['desenho'].strip(),
                    'VARIANTE': dados['variante'].strip(),
                    'SITUACAO': dados['situacao'].strip()
                }
            
            # Padrão alternativo
            padrao_alternativo = re.compile(
                r'^(?P<codigo>\d{6})\s+'  # 000014
                r'(?P<descricao>.+?)\s+'  # VELUDO CONFORT
                r'\d{3}\s+'  # 001
                r'[A-Z]+\s*/\s*'  # TINTO /
                r'(?P<cod_cor>\d{5})\s+'  # 00005
                r'(?P<cor_num>\d+)\s*-\s*'  # 5 -
                r'(?P<cor_nome>[^-/]+)'  # BLACK (para antes da próxima parte)
            )
            
            match = padrao_alternativo.search(texto)
            if match:
                dados = match.groupdict()
                return {
                    'ARTIGO': dados['codigo'].strip(),
                    'DESCRICAO': dados['descricao'].strip(),
                    'COR_CODIGO': dados['cod_cor'].strip(),
                    'COR': f"{dados['cor_num'].strip()} - {dados['cor_nome'].strip()}",
                    'DESENHO': 'LISO',
                    'VARIANTE': 'PADRÃO',
                    'SITUACAO': 'TINTO'
                }
            
            return None
            
        except Exception as e:
            logger.debug(f"Erro ao extrair info produto: {e}")
            return None
    
    def extrair_dados_previsao(self, texto: str) -> List[Dict[str, Any]]:
        """Extrai dados de previsão/estoque do texto"""
        previsoes = []
        
        try:
            # Padrão para cada previsão:
            # "Previsão Pronta entrega Estoque 16.605,30 Pedidos 16.605,30 Disponível 0,00"
            # ou "Previsão 19/01/2026 Estoque 14.766,10 Pedidos 6.544,70 Disponível 8.221,40"
            
            # Primeiro, encontrar todas as ocorrências de "Previsão"
            padrao_previsao = re.compile(
                r'Previsão\s+'  # Palavra "Previsão"
                r'(?P<tipo>Pronta\s+entrega|\d{2}/\d{2}/\d{4})\s+'  # Tipo ou data
                r'Estoque\s+(?P<estoque>\d{1,3}(?:\.\d{3})*,\d{2})\s+'  # Estoque
                r'Pedidos\s+(?P<pedidos>\d{1,3}(?:\.\d{3})*,\d{2})\s+'  # Pedidos
                r'Dispon[íi]vel\s+(?P<disponivel>-?\d{1,3}(?:\.\d{3})*,\d{2})'  # Disponível
            )
            
            matches = list(padrao_previsao.finditer(texto))
            
            for match in matches:
                dados = match.groupdict()
                previsao = {
                    'TIPO': dados['tipo'].strip(),
                    'ESTOQUE': self.parse_valor(dados['estoque']),
                    'PEDIDOS': self.parse_valor(dados['pedidos']),
                    'DISPONIVEL': self.parse_valor(dados['disponivel'])
                }
                previsoes.append(previsao)
            
            # Se não encontrou com o padrão completo, tentar padrão mais flexível
            if not previsoes:
                padrao_flexivel = re.compile(
                    r'(?P<tipo>Pronta\s+entrega|\d{2}/\d{2}/\d{4})'
                    r'.*?'
                    r'(?P<estoque>\d{1,3}(?:\.\d{3})*,\d{2})'
                    r'.*?'
                    r'(?P<pedidos>\d{1,3}(?:\.\d{3})*,\d{2})'
                    r'.*?'
                    r'(?P<disponivel>-?\d{1,3}(?:\.\d{3})*,\d{2})'
                )
                
                matches = list(padrao_flexivel.finditer(texto))
                for match in matches:
                    dados = match.groupdict()
                    previsao = {
                        'TIPO': dados['tipo'].strip(),
                        'ESTOQUE': self.parse_valor(dados['estoque']),
                        'PEDIDOS': self.parse_valor(dados['pedidos']),
                        'DISPONIVEL': self.parse_valor(dados['disponivel'])
                    }
                    previsoes.append(previsao)
            
            logger.debug(f"Extraídas {len(previsoes)} previsões do texto")
            
        except Exception as e:
            logger.error(f"Erro ao extrair dados previsão: {e}")
            logger.debug(f"Texto: {texto[:300]}")
        
        return previsoes
    
    def processar_arquivo_csv(self, arquivo_path: str) -> List[Dict[str, Any]]:
        """Processa um arquivo CSV específico"""
        dados_completos = []
        
        try:
            logger.info(f"Processando arquivo: {arquivo_path}")
            
            # Extrair código do produto do nome do arquivo
            filename = os.path.basename(arquivo_path)
            codigo_match = re.search(r'produto_(\d+)_', filename)
            codigo_produto = codigo_match.group(1) if codigo_match else '000000'
            
            # Contadores para estatísticas
            linhas_processadas = 0
            linhas_com_dados = 0
            
            # Ler o arquivo CSV
            with open(arquivo_path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f, delimiter=';')
                
                for linha_num, linha in enumerate(reader, 1):
                    linhas_processadas += 1
                    
                    if len(linha) < 3:
                        continue
                    
                    # A terceira coluna contém os dados
                    texto_dados = linha[2].strip()
                    
                    # Verificar se esta linha contém dados de produto
                    if self.eh_linha_de_produto(texto_dados):
                        linhas_com_dados += 1
                        logger.debug(f"Linha {linha_num} parece conter dados de produto")
                        
                        # Processar a linha de produto
                        dados_produto = self.processar_linha_produto(texto_dados, codigo_produto)
                        if dados_produto:
                            dados_completos.extend(dados_produto)
                            logger.debug(f"Extraídos {len(dados_produto)} registros da linha {linha_num}")
            
            logger.info(f"Arquivo {filename}: {linhas_processadas} linhas processadas, "
                       f"{linhas_com_dados} linhas com dados, {len(dados_completos)} registros extraídos")
            
            if not dados_completos:
                logger.warning(f"Arquivo {filename}: nenhum dado extraído")
            
        except Exception as e:
            logger.error(f"Erro ao processar arquivo {arquivo_path}: {e}")
        
        return dados_completos
    
    def eh_linha_de_produto(self, texto: str) -> bool:
        """Verifica se a linha contém dados de produto"""
        if not texto or len(texto) < 20:
            return False
        
        # Verificar padrões que indicam dados de produto
        padroes = [
            r'^\d{6}\s+[A-Z]',  # Começa com código de 6 dígitos e texto
            r'\d{5}\s+\d+\s*-\s*[A-Z]',  # Código de cor seguido de número e nome
            r'Previsão\s+(?:Pronta\s+entrega|\d{2}/\d{2}/\d{4})',  # Contém previsão
            r'Estoque\s+\d',  # Contém estoque com número
            r'Pedidos\s+\d',  # Contém pedidos com número
        ]
        
        for padrao in padroes:
            if re.search(padrao, texto, re.IGNORECASE):
                return True
        
        return False
    
    def consolidar_todos_arquivos(self) -> Tuple[pd.DataFrame, str]:
        """Consolida todos os arquivos CSV na pasta"""
        todos_dados = []
        arquivos_processados = []
        arquivos_com_erro = []
        
        # Listar arquivos CSV
        csv_files = list(Path(self.csv_folder).glob("*.csv"))
        
        if not csv_files:
            return pd.DataFrame(), "Nenhum arquivo CSV encontrado"
        
        logger.info(f"Encontrados {len(csv_files)} arquivos para processar")
        
        # Processar cada arquivo
        for csv_file in csv_files:
            try:
                logger.info(f"Processando: {csv_file.name}")
                
                dados_arquivo = self.processar_arquivo_csv(str(csv_file))
                
                if dados_arquivo:
                    todos_dados.extend(dados_arquivo)
                    arquivos_processados.append(csv_file.name)
                    logger.info(f"✅ {csv_file.name}: {len(dados_arquivo)} registros extraídos")
                    
                    # Log de amostra
                    if dados_arquivo and len(dados_arquivo) > 0:
                        amostra = dados_arquivo[0]
                        logger.debug(f"Amostra: Artigo={amostra.get('ARTIGO')}, "
                                   f"Cor={amostra.get('COR')}, "
                                   f"Tipo={amostra.get('TIPO')}, "
                                   f"Estoque={amostra.get('ESTOQUE')}")
                else:
                    logger.warning(f"⚠️ {csv_file.name}: nenhum dado extraído")
                    arquivos_com_erro.append(csv_file.name)
                    
            except Exception as e:
                logger.error(f"❌ Erro em {csv_file.name}: {e}")
                arquivos_com_erro.append(csv_file.name)
        
        if not todos_dados:
            mensagem_erro = "Nenhum dado extraído dos arquivos. "
            if arquivos_com_erro:
                mensagem_erro += f"Arquivos com erro: {', '.join(arquivos_com_erro[:5])}"
                if len(arquivos_com_erro) > 5:
                    mensagem_erro += f"... (mais {len(arquivos_com_erro) - 5})"
            return pd.DataFrame(), mensagem_erro
        
        # Criar DataFrame
        try:
            df = pd.DataFrame(todos_dados)
            
            # Ordenar colunas na ordem desejada
            colunas_ordem = ['ARTIGO', 'DESCRICAO', 'COR_CODIGO', 'COR', 
                            'DESENHO', 'VARIANTE', 'SITUACAO', 
                            'TIPO', 'ESTOQUE', 'PEDIDOS', 'DISPONIVEL']
            
            # Manter apenas colunas existentes
            colunas_existentes = [col for col in colunas_ordem if col in df.columns]
            df = df[colunas_existentes]
            
            # Ordenar dados
            colunas_ordenacao = []
            if 'ARTIGO' in df.columns:
                colunas_ordenacao.append('ARTIGO')
            if 'COR' in df.columns:
                colunas_ordenacao.append('COR')
            if 'TIPO' in df.columns:
                # Ordenar tipos: PRONTA ENTREGA primeiro, depois datas
                df['TIPO_ORDENACAO'] = df['TIPO'].apply(
                    lambda x: '0000' if x == 'Pronta entrega' else x.replace('/', '') if isinstance(x, str) else x
                )
                colunas_ordenacao.append('TIPO_ORDENACAO')
            
            if colunas_ordenacao:
                df = df.sort_values(colunas_ordenacao)
                if 'TIPO_ORDENACAO' in df.columns:
                    df = df.drop('TIPO_ORDENACAO', axis=1)
            
            # Resetar índice
            df = df.reset_index(drop=True)
            
            mensagem = (f"Processados {len(arquivos_processados)} arquivos, "
                       f"{len(df)} registros, "
                       f"{df['ARTIGO'].nunique() if 'ARTIGO' in df.columns else 0} produtos únicos")
            
            if arquivos_com_erro:
                mensagem += f" ({len(arquivos_com_erro)} arquivos com problemas)"
            
            return df, mensagem
            
        except Exception as e:
            logger.error(f"Erro ao criar DataFrame: {e}")
            return pd.DataFrame(), f"Erro ao processar dados: {str(e)}"
    
    def gerar_excel_formatado(self, df: pd.DataFrame) -> str:
        """Gera arquivo Excel no formato desejado"""
        if df.empty:
            return ""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        excel_filename = f"consolidado_formatado_{timestamp}.xlsx"
        excel_path = os.path.join(self.output_folder, excel_filename)
        
        try:
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                # 1. ABA PRINCIPAL: Todos os dados formatados
                df.to_excel(writer, sheet_name='TODOS OS DADOS', index=False)
                
                # Ajustar largura das colunas
                worksheet = writer.sheets['TODOS OS DADOS']
                for i, col in enumerate(df.columns):
                    column_width = max(df[col].astype(str).map(len).max(), len(col)) + 2
                    worksheet.column_dimensions[chr(65 + i)].width = min(column_width, 50)
                
                # 2. ABA RESUMO POR PRODUTO
                if 'ARTIGO' in df.columns and 'DESCRICAO' in df.columns:
                    resumo_produto = df.groupby(['ARTIGO', 'DESCRICAO']).agg({
                        'ESTOQUE': 'sum',
                        'PEDIDOS': 'sum',
                        'DISPONIVEL': 'sum'
                    }).reset_index()
                    resumo_produto.to_excel(writer, sheet_name='RESUMO PRODUTOS', index=False)
                
                # 3. ABA RESUMO POR COR
                if 'ARTIGO' in df.columns and 'DESCRICAO' in df.columns and 'COR' in df.columns:
                    resumo_cor = df.groupby(['ARTIGO', 'DESCRICAO', 'COR']).agg({
                        'ESTOQUE': 'sum',
                        'PEDIDOS': 'sum',
                        'DISPONIVEL': 'sum'
                    }).reset_index()
                    resumo_cor.to_excel(writer, sheet_name='RESUMO POR COR', index=False)
                
                # 4. ABA PRONTA ENTREGA
                if 'TIPO' in df.columns:
                    pronta_entrega = df[df['TIPO'].str.contains('Pronta entrega', case=False, na=False)].copy()
                    if not pronta_entrega.empty:
                        pronta_entrega.to_excel(writer, sheet_name='PRONTA ENTREGA', index=False)
                
                # 5. ABA PREVISÕES FUTURAS
                if 'TIPO' in df.columns:
                    datas_futuras = df[~df['TIPO'].str.contains('Pronta entrega', case=False, na=False)].copy()
                    if not datas_futuras.empty:
                        datas_futuras.to_excel(writer, sheet_name='PREVISÕES FUTURAS', index=False)
            
            logger.info(f"Excel gerado: {excel_path}")
            return excel_filename
            
        except Exception as e:
            logger.error(f"Erro ao gerar Excel: {e}")
            return ""
    
    def gerar_csv_formatado(self, df: pd.DataFrame) -> str:
        """Gera arquivo CSV formatado"""
        if df.empty:
            return ""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        csv_filename = f"consolidado_{timestamp}.csv"
        csv_path = os.path.join(self.output_folder, csv_filename)
        
        try:
            # Formatar números no padrão brasileiro
            df_formatado = df.copy()
            
            for col in ['ESTOQUE', 'PEDIDOS', 'DISPONIVEL']:
                if col in df_formatado.columns:
                    df_formatado[col] = df_formatado[col].apply(
                        lambda x: f"{x:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.') 
                        if pd.notnull(x) else '0,00'
                    )
            
            df_formatado.to_csv(csv_path, sep=';', index=False, encoding='utf-8-sig')
            logger.info(f"CSV gerado: {csv_path}")
            return csv_filename
            
        except Exception as e:
            logger.error(f"Erro ao gerar CSV: {e}")
            return ""


# Função principal para integração com Flask
def consolidar_dados_formatado():
    """Função principal para consolidação no formato desejado"""
    try:
        logger.info("Iniciando consolidação formatada...")
        
        # Inicializar extrator
        extrator = DGBDataExtractorFormatado()
        
        # Consolidar dados
        df, mensagem = extrator.consolidar_todos_arquivos()
        
        if df.empty:
            return None, mensagem
        
        # Gerar arquivos
        excel_filename = extrator.gerar_excel_formatado(df)
        csv_filename = extrator.gerar_csv_formatado(df)
        
        # Gerar resumo em JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_filename = f"resumo_consolidacao_{timestamp}.json"
        json_path = os.path.join(extrator.output_folder, json_filename)
        
        # Calcular estatísticas
        total_estoque = float(df['ESTOQUE'].sum()) if 'ESTOQUE' in df.columns else 0
        total_pedidos = float(df['PEDIDOS'].sum()) if 'PEDIDOS' in df.columns else 0
        total_disponivel = float(df['DISPONIVEL'].sum()) if 'DISPONIVEL' in df.columns else 0
        
        resumo = {
            'data_consolidacao': datetime.now().isoformat(),
            'total_registros': len(df),
            'total_estoque': total_estoque,
            'total_pedidos': total_pedidos,
            'total_disponivel': total_disponivel,
            'produtos_unicos': df['ARTIGO'].nunique() if 'ARTIGO' in df.columns else 0,
            'cores_unicas': df['COR'].nunique() if 'COR' in df.columns else 0,
            'arquivos_processados': len(list(Path(extrator.csv_folder).glob("*.csv"))),
            'arquivo_csv': csv_filename,
            'arquivo_excel': excel_filename,
            'arquivo_pivot': '',
        }
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(resumo, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Consolidação concluída: {len(df)} registros")
        
        return resumo, mensagem
        
    except Exception as e:
        logger.error(f"Erro na consolidação formatada: {e}")
        return None, f"Erro: {str(e)}"