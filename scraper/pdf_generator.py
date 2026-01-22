# pdf_generator.py - Geração de PDFs e imagens - VERSÃO CORRIGIDA
import os
import pandas as pd
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import logging
import matplotlib.pyplot as plt
import numpy as np
from io import BytesIO
import csv
import glob
import re

logger = logging.getLogger(__name__)

def find_latest_consolidated_file():
    """Encontra o arquivo consolidado CSV mais recente na pasta CSV"""
    try:
        csv_folder = 'csv'  # Pasta onde estão os CSVs consolidados
        
        # Apenas procurar CSV, ignorar XLSX
        pattern_csv = os.path.join(csv_folder, "consolidado_organizado_*.csv")
        csv_files = glob.glob(pattern_csv)
        
        if not csv_files:
            logger.error("Nenhum arquivo CSV consolidado encontrado")
            
            # Listar arquivos disponíveis para debug
            all_files = glob.glob(os.path.join(csv_folder, "*"))
            if all_files:
                logger.info(f"Arquivos encontrados em {csv_folder}:")
                for f in all_files:
                    logger.info(f"  - {os.path.basename(f)}")
            
            return None
        
        # Ordenar por data de modificação (mais recente primeiro)
        csv_files.sort(key=os.path.getmtime, reverse=True)
        
        # Pegar o arquivo mais recente
        latest_file = csv_files[0]
        logger.info(f"✅ Arquivo CSV mais recente encontrado: {latest_file}")
        
        # Debug: listar todos os CSVs encontrados
        logger.info(f"Todos os CSVs encontrados ({len(csv_files)}):")
        for i, f in enumerate(csv_files[:5]):  # Mostrar apenas os 5 mais recentes
            mod_time = datetime.fromtimestamp(os.path.getmtime(f))
            logger.info(f"  {i+1}. {os.path.basename(f)} - Modificado: {mod_time}")
        
        return latest_file
        
    except Exception as e:
        logger.error(f"Erro ao buscar arquivo consolidado mais recente: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def extract_timestamp_from_filename(filename):
    """Extrai timestamp do nome do arquivo"""
    try:
        # Padrão: consolidado_organizado_YYYYMMDD_HHMMSS.csv
        pattern = r'consolidado_organizado_(\d{8}_\d{6})\.csv'
        match = re.search(pattern, os.path.basename(filename))
        
        if match:
            timestamp_str = match.group(1)
            # Converter para datetime
            timestamp_dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
            return timestamp_dt, timestamp_str
        else:
            # Se não encontrar no padrão, usar data de modificação
            mod_time = os.path.getmtime(filename)
            timestamp_dt = datetime.fromtimestamp(mod_time)
            timestamp_str = timestamp_dt.strftime('%Y%m%d_%H%M%S')
            logger.warning(f"Timestamp não encontrado no nome do arquivo, usando data de modificação: {timestamp_str}")
            return timestamp_dt, timestamp_str
            
    except Exception as e:
        logger.warning(f"Erro ao extrair timestamp do arquivo {filename}: {e}")
        # Usar data atual como fallback
        now = datetime.now()
        return now, now.strftime('%Y%m%d_%H%M%S')

def read_csv_file(csv_file_path):
    """Lê arquivo CSV com tratamento robusto"""
    try:
        logger.info(f"Lendo arquivo CSV: {csv_file_path}")
        
        # Verificar se o arquivo existe
        if not os.path.exists(csv_file_path):
            logger.error(f"Arquivo não existe: {csv_file_path}")
            return None
        
        # Verificar tamanho do arquivo
        file_size = os.path.getsize(csv_file_path)
        logger.info(f"Tamanho do arquivo: {file_size} bytes")
        
        if file_size == 0:
            logger.error("Arquivo CSV está vazio")
            return None
        
        # Ler o CSV com ponto-e-vírgula como delimitador
        try:
            df = pd.read_csv(
                csv_file_path,
                delimiter=';',
                encoding='utf-8',
                on_bad_lines='skip',
                engine='python'
            )
            
            if not df.empty:
                logger.info(f"✅ CSV lido com sucesso com delimitador ';'")
                logger.info(f"   Linhas: {len(df)}")
                logger.info(f"   Colunas ({len(df.columns)}): {list(df.columns)}")
                return df
        except Exception as e1:
            logger.warning(f"Tentativa 1 falhou: {e1}")
            
        # Tentar com outros delimitadores e encodings
        encodings_to_try = ['latin-1', 'cp1252', 'utf-8-sig', 'iso-8859-1']
        delimiters_to_try = [';', ',', '\t']
        
        for encoding in encodings_to_try:
            for delimiter in delimiters_to_try:
                try:
                    df = pd.read_csv(
                        csv_file_path,
                        delimiter=delimiter,
                        encoding=encoding,
                        on_bad_lines='skip',
                        engine='python'
                    )
                    
                    if not df.empty:
                        logger.info(f"✅ CSV lido com encoding={encoding}, delimiter='{delimiter}'")
                        logger.info(f"   Linhas: {len(df)}")
                        return df
                except Exception as e2:
                    continue
        
        logger.error("Não foi possível ler o arquivo CSV com nenhum método")
        return None
        
    except Exception as e:
        logger.error(f"Erro crítico na leitura do CSV: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None

def clean_and_prepare_data(df):
    """Limpa e prepara os dados do DataFrame - VERSÃO CORRIGIDA"""
    try:
        logger.info("Limpando e preparando dados...")
        
        if df is None or df.empty:
            logger.error("DataFrame vazio ou nulo")
            return pd.DataFrame()
        
        # Fazer uma cópia
        df_original = df.copy()
        
        logger.info(f"Dados brutos: {len(df)} linhas, {len(df.columns)} colunas")
        logger.info(f"Colunas brutas: {list(df.columns)}")
        
        # Converter todos os dados para string e limpar
        for col in df.columns:
            df[col] = df[col].astype(str).str.strip()
        
        # Remover linhas totalmente vazias
        df = df.replace('', pd.NA).dropna(how='all').fillna('')
        
        if df.empty:
            logger.error("Todos os dados foram removidos após limpeza")
            return pd.DataFrame()
        
        # Mapeamento inteligente de colunas
        expected_columns = ['Produto / Cor', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        
        # Dicionário de mapeamento de padrões
        column_patterns = {
            'Produto / Cor': ['produto', 'descrição', 'descricao', 'prod', 'item', 'artigo'],
            'Previsão': ['previsão', 'previsao', 'prev', 'forecast'],
            'Estoque': ['estoque', 'stock', 'stk', 'saldo'],
            'Pedidos': ['pedidos', 'orders', 'ord', 'vendas'],
            'Disponível': ['disponível', 'disponivel', 'disp', 'available', 'avl']
        }
        
        column_mapping = {}
        
        # Para cada coluna esperada, procurar correspondência
        for expected_col, patterns in column_patterns.items():
            found = False
            
            # Verificar cada coluna do DataFrame
            for actual_col in df.columns:
                actual_lower = str(actual_col).lower().strip()
                
                # Verificar correspondência exata
                if expected_col.lower() == actual_lower:
                    column_mapping[actual_col] = expected_col
                    found = True
                    break
                
                # Verificar correspondência por padrão
                for pattern in patterns:
                    if pattern in actual_lower:
                        column_mapping[actual_col] = expected_col
                        found = True
                        break
                
                if found:
                    break
            
            if not found:
                logger.warning(f"Coluna '{expected_col}' não encontrada nos dados")
        
        logger.info(f"Mapeamento de colunas: {column_mapping}")
        
        # Aplicar mapeamento
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Garantir que temos as colunas necessárias
        for col in expected_columns:
            if col not in df.columns:
                logger.warning(f"Coluna '{col}' não encontrada, criando vazia")
                df[col] = ''
        
        # Reordenar colunas
        df = df.reindex(columns=expected_columns)
        
        # Filtrar linhas vazias na coluna 'Produto / Cor'
        initial_count = len(df)
        df = df[df['Produto / Cor'].str.strip() != '']
        filtered_count = len(df)
        
        logger.info(f"Linhas removidas (Produto vazio): {initial_count - filtered_count}")
        
        if df.empty:
            logger.error("Nenhum dado válido após filtrar produtos vazios")
            return pd.DataFrame()
        
        # CORREÇÃO: NÃO REMOVER DUPLICATAS! Mantém todas as linhas
        # Cada linha representa uma previsão diferente para o mesmo produto/cor
        logger.info(f"Dados mantidos com múltiplas previsões: {len(df)} linhas")
        
        logger.info(f"Dados limpos: {len(df)} linhas")
        logger.info(f"Colunas finais: {list(df.columns)}")
        
        # Exibir amostra das primeiras linhas limpas
        logger.info("Amostra das primeiras 10 linhas limpas:")
        for i in range(min(10, len(df))):
            logger.info(f"  Linha {i}: {df.iloc[i].to_dict()}")
        
        return df
        
    except Exception as e:
        logger.error(f"Erro na limpeza de dados: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()

def generate_product_images(df, timestamp):
    """Gera imagens JPG para cada produto com gráficos"""
    images_created = []
    
    try:
        logger.info("Gerando imagens para produtos...")
        
        if df.empty or 'Produto / Cor' not in df.columns:
            logger.error("Dados vazios ou sem coluna 'Produto / Cor'")
            return images_created
        
        # Extrair produtos únicos
        df['codigo_produto'] = df['Produto / Cor'].apply(extrair_codigo_produto)
        produtos_unicos = [p for p in df['codigo_produto'].unique() 
                          if p and str(p).strip() and str(p).strip() != 'Desconhecido']
        
        logger.info(f"Produtos únicos encontrados: {len(produtos_unicos)}")
        
        if not produtos_unicos:
            logger.warning("Nenhum código de produto válido encontrado")
            return images_created
        
        for produto in produtos_unicos[:30]:  # Limitar a 30 produtos
            try:
                # Filtrar dados do produto
                df_produto = df[df['codigo_produto'] == produto].copy()
                
                if len(df_produto) == 0:
                    continue
                
                logger.info(f"Processando produto {produto} com {len(df_produto)} previsões")
                
                # Converter valores para numérico
                df_produto['Estoque_num'] = df_produto['Estoque'].apply(converter_valor_brasileiro)
                df_produto['Pedidos_num'] = df_produto['Pedidos'].apply(converter_valor_brasileiro)
                df_produto['Disponível_num'] = df_produto['Disponível'].apply(converter_valor_brasileiro)
                
                # Agrupar por produto/cor (somando todas as previsões)
                df_grouped = df_produto.groupby('Produto / Cor').agg({
                    'Estoque_num': 'sum',
                    'Pedidos_num': 'sum',
                    'Disponível_num': 'sum'
                }).reset_index()
                
                if len(df_grouped) == 0:
                    continue
                
                # Criar figura com subplots
                fig, axes = plt.subplots(1, 2, figsize=(12, 6))
                fig.suptitle(f'Produto {produto}', fontsize=16, fontweight='bold')
                
                # Gráfico 1: Barras para variantes principais (até 5)
                if len(df_grouped) > 0:
                    # Pegar até 5 primeiras variantes
                    df_display = df_grouped.head(5)
                    
                    # Preparar rótulos para o gráfico
                    variantes = []
                    for i, row in df_display.iterrows():
                        desc = str(row['Produto / Cor'])
                        # Extrair cor
                        if 'COR:' in desc:
                            try:
                                cor_part = desc.split('COR:')[-1].strip()
                                cor = cor_part.split('-')[0].strip() if '-' in cor_part else cor_part[:20]
                            except:
                                cor = f"Var{i+1}"
                        else:
                            cor = f"Var{i+1}"
                        variantes.append(cor[:20])
                    
                    estoque_vals = df_display['Estoque_num'].values
                    pedidos_vals = df_display['Pedidos_num'].values
                    disponivel_vals = df_display['Disponível_num'].values
                    
                    x = np.arange(len(variantes))
                    width = 0.25
                    
                    axes[0].bar(x - width, estoque_vals, width, label='Estoque', color='blue', alpha=0.7)
                    axes[0].bar(x, pedidos_vals, width, label='Pedidos', color='orange', alpha=0.7)
                    axes[0].bar(x + width, disponivel_vals, width, label='Disponível', color='green', alpha=0.7)
                    
                    axes[0].set_xlabel('Variantes')
                    axes[0].set_ylabel('Quantidade')
                    axes[0].set_title('Estoque vs Pedidos vs Disponível (Total)')
                    axes[0].set_xticks(x)
                    axes[0].set_xticklabels(variantes, rotation=45, ha='right')
                    axes[0].legend()
                    axes[0].grid(True, alpha=0.3)
                
                # Gráfico 2: Totais do produto
                try:
                    total_estoque = df_grouped['Estoque_num'].sum()
                    total_pedidos = df_grouped['Pedidos_num'].sum()
                    total_disponivel = df_grouped['Disponível_num'].sum()
                    
                    sizes = [total_estoque, total_pedidos, total_disponivel]
                    labels = ['Estoque Total', 'Pedidos Total', 'Disponível Total']
                    colors_pie = ['#ff9999', '#66b3ff', '#99ff99']
                    
                    # Remover zeros
                    valid_data = [(s, l, c) for s, l, c in zip(sizes, labels, colors_pie) if s > 0]
                    
                    if valid_data:
                        sizes_filt = [d[0] for d in valid_data]
                        labels_filt = [d[1] for d in valid_data]
                        colors_filt = [d[2] for d in valid_data]
                        
                        axes[1].pie(sizes_filt, labels=labels_filt, colors=colors_filt, 
                                  autopct='%1.1f%%', startangle=90)
                        axes[1].axis('equal')
                        axes[1].set_title('Distribuição Total do Produto')
                    else:
                        axes[1].text(0.5, 0.5, 'Sem dados', ha='center', va='center', fontsize=12)
                        axes[1].set_title('Distribuição Total')
                except Exception as pie_error:
                    logger.warning(f"Erro no gráfico de pizza para {produto}: {pie_error}")
                    axes[1].text(0.5, 0.5, 'Erro nos dados', ha='center', va='center', fontsize=12)
                    axes[1].set_title('Distribuição Total')
                
                # Ajustar layout
                plt.tight_layout()
                
                # Salvar imagem
                image_filename = f"produto_{produto}_{timestamp}.jpg"
                image_path = os.path.join('images', image_filename)
                plt.savefig(image_path, dpi=150, bbox_inches='tight')
                plt.close()
                
                images_created.append({
                    'produto': produto,
                    'filename': image_filename,
                    'path': image_path
                })
                
                logger.info(f"✅ Imagem gerada para produto {produto}: {image_filename}")
                
            except Exception as e:
                logger.error(f"Erro ao gerar imagem para produto {produto}: {e}")
                continue
        
        logger.info(f"Total de imagens geradas: {len(images_created)}")
        return images_created
        
    except Exception as e:
        logger.error(f"Erro na geração de imagens: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def extrair_codigo_produto(descricao):
    """Extrai código do produto da descrição"""
    try:
        if pd.isna(descricao) or descricao is None:
            return "Desconhecido"
        
        desc_str = str(descricao).strip()
        
        if not desc_str:
            return "Desconhecido"
        
        # Padrões comuns
        # 1. "000014 - VELUDO CONFORT - COR: 5 - BLACK"
        # 2. "14 - VELUDO CONFORT - COR: 5 - BLACK"
        # 3. "PRODUTO 14 - VELUDO CONFORT"
        
        # Tentar extrair código do início
        match = re.match(r'^(\d+)\s*[-–]', desc_str)
        if match:
            return match.group(1).zfill(6)  # Formatar com zeros à esquerda
        
        # Tentar encontrar números no início
        match = re.match(r'^(\d+)', desc_str)
        if match:
            return match.group(1).zfill(6)
        
        # Se não encontrar número, usar parte da descrição
        return desc_str[:30] if len(desc_str) > 30 else desc_str
        
    except Exception as e:
        logger.warning(f"Erro ao extrair código de '{descricao}': {e}")
        return "Desconhecido"

def formatar_data_hora():
    """Formata data e hora para o relatório"""
    now = datetime.now()
    return now.strftime('%d/%m/%Y %H:%M:%S')

def formatar_data_hora_arquivo(timestamp_str):
    """Formata timestamp do arquivo para exibição"""
    try:
        # Converter string YYYYMMDD_HHMMSS para formato legível
        dt = datetime.strptime(timestamp_str, '%Y%m%d_%H%M%S')
        return dt.strftime('%d/%m/%Y %H:%M:%S')
    except:
        return timestamp_str

def generate_all_products_pdf(df, output_path, total_registros, file_timestamp_str, 
                             generation_timestamp, source_filename, images_created):
    """Gera PDF com todos os produtos - VERSÃO CORRIGIDA"""
    try:
        logger.info(f"Gerando PDF completo: {output_path}")
        
        # Criar documento
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        # Elementos do documento
        story = []
        
        # Título
        story.append(Paragraph("RELATÓRIO COMPLETO DE ESTOQUE DGB", title_style))
        
        # Informações do relatório
        info_text = f"""
        <b>Data de Geração:</b> {formatar_data_hora()}<br/>
        <b>Data dos Dados:</b> {formatar_data_hora_arquivo(file_timestamp_str)}<br/>
        <b>Total de Registros:</b> {total_registros}<br/>
        <b>Total de Produtos:</b> {len(df['codigo_produto'].unique()) if 'codigo_produto' in df.columns else 'N/A'}<br/>
        <b>Arquivo Fonte:</b> {source_filename}
        """
        
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Adicionar imagem de resumo se disponível
        if images_created:
            try:
                # Usar a primeira imagem como exemplo
                first_image_path = images_created[0]['path']
                if os.path.exists(first_image_path):
                    img = Image(first_image_path, width=400, height=200)
                    story.append(img)
                    story.append(Spacer(1, 20))
                    story.append(Paragraph("<i>Gráficos disponíveis para cada produto</i>", styles['Italic']))
                    story.append(Spacer(1, 20))
            except Exception as e:
                logger.warning(f"Erro ao adicionar imagem ao PDF: {e}")
        
        # Preparar dados para tabela - CORREÇÃO: Mostrar todas as previsões
        df_table = df.copy()
        
        # Ordenar por produto e previsão
        if 'Previsão' in df_table.columns:
            # Criar ordenação personalizada
            def sort_key(x):
                previsao = str(x).lower().strip()
                if 'pronta entrega' in previsao:
                    return (0, '')  # "Pronta entrega" primeiro
                else:
                    # Tentar extrair data para ordenação
                    try:
                        # Formato DD/MM/YYYY
                        parts = previsao.split('/')
                        if len(parts) == 3:
                            return (1, f"{parts[2]}{parts[1]}{parts[0]}")  # Ordenar por data
                    except:
                        pass
                    return (2, previsao)  # Outros textos
            
            df_table['sort_key'] = df_table.apply(
                lambda row: (row['Produto / Cor'], sort_key(row['Previsão'])), 
                axis=1
            )
            df_table = df_table.sort_values('sort_key')
            df_table = df_table.drop('sort_key', axis=1)
        
        # Limitar o número de registros para não sobrecarregar o PDF
        show_limit = min(200, len(df_table))
        if len(df_table) > show_limit:
            story.append(Paragraph(f"<i>Mostrando {show_limit} de {total_registros} registros...</i>", styles['Italic']))
            story.append(Spacer(1, 10))
            df_table = df_table.head(show_limit)
        else:
            story.append(Paragraph(f"<i>Mostrando todos os {total_registros} registros</i>", styles['Italic']))
            story.append(Spacer(1, 10))
        
        # Converter DataFrame para lista para a tabela
        table_data = []
        
        # Cabeçalho
        headers = ['Produto', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        table_data.append(headers)
        
        # Dados - mostrar todas as previsões
        current_product = None
        for _, row in df_table.iterrows():
            # Truncar descrição se muito longa
            produto_desc = str(row['Produto / Cor'])
            if len(produto_desc) > 50:
                produto_desc = produto_desc[:47] + "..."
            
            previsao = str(row['Previsão'])
            
            table_data.append([
                produto_desc,
                previsao[:20],
                str(row['Estoque']),
                str(row['Pedidos']),
                str(row['Disponível'])
            ])
        
        # Criar tabela
        col_widths = [250, 80, 60, 60, 60]
        table = Table(table_data, colWidths=col_widths)
        
        # Estilo da tabela
        table.setStyle(TableStyle([
            # Cabeçalho
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            
            # Linhas alternadas
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
            
            # Destacar "Pronta entrega"
            ('TEXTCOLOR', (1, 1), (1, -1), colors.black),
        ]))
        
        # Destacar linhas com "Pronta entrega"
        for i, row in enumerate(table_data[1:], 1):  # Começar da linha 1 (após cabeçalho)
            if 'pronta entrega' in str(row[1]).lower():
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FFF2CC')),
                ]))
        
        story.append(table)
        
        # Estatísticas rápidas
        story.append(Spacer(1, 30))
        story.append(Paragraph("<b>ESTATÍSTICAS RÁPIDAS:</b>", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        try:
            # Calcular estatísticas
            total_estoque = 0
            total_pedidos = 0
            total_disponivel = 0
            
            for _, row in df.iterrows():
                total_estoque += converter_valor_brasileiro(row['Estoque'])
                total_pedidos += converter_valor_brasileiro(row['Pedidos'])
                total_disponivel += converter_valor_brasileiro(row['Disponível'])
            
            # Contar previsões únicas
            if 'Previsão' in df.columns:
                previsoes_unicas = df['Previsão'].unique()
            else:
                previsoes_unicas = []
            
            stats_text = f"""
            <b>Estoque Total:</b> {formatar_valor_brasileiro(total_estoque)}<br/>
            <b>Pedidos Total:</b> {formatar_valor_brasileiro(total_pedidos)}<br/>
            <b>Disponível Total:</b> {formatar_valor_brasileiro(total_disponivel)}<br/>
            <b>Previsões Únicas:</b> {len(previsoes_unicas)}<br/>
            """
            
            story.append(Paragraph(stats_text, styles['Normal']))
            
            # Distribuição de previsões
            if 'Previsão' in df.columns and len(previsoes_unicas) > 0:
                story.append(Spacer(1, 10))
                story.append(Paragraph("<b>DISTRIBUIÇÃO DE PREVISÕES:</b>", styles['Heading3']))
                
                # Contar ocorrências de cada previsão
                previsao_counts = df['Previsão'].value_counts().head(10)  # Top 10
                
                previsao_table_data = [['Previsão', 'Quantidade']]
                for previsao, count in previsao_counts.items():
                    previsao_display = str(previsao)[:25] + ("..." if len(str(previsao)) > 25 else "")
                    previsao_table_data.append([previsao_display, str(count)])
                
                previsao_table = Table(previsao_table_data, colWidths=[150, 80])
                previsao_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ]))
                
                story.append(previsao_table)
                
        except Exception as e:
            logger.warning(f"Erro ao calcular estatísticas: {e}")
            story.append(Paragraph("Erro ao calcular estatísticas", styles['Normal']))
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer_text = f"Relatório gerado automaticamente pelo Sistema DGB Scraper - {formatar_data_hora()}"
        story.append(Paragraph(footer_text, styles['Italic']))
        
        # Construir PDF
        doc.build(story)
        
        logger.info(f"✅ PDF completo gerado: {os.path.basename(output_path)}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF completo: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def generate_single_product_pdf(df_produto, output_path, produto_codigo, 
                               file_timestamp_str, generation_timestamp, images_created):
    """Gera PDF para um produto específico"""
    try:
        logger.info(f"Gerando PDF para produto {produto_codigo}: {output_path}")
        
        # Criar documento
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Elementos do documento
        story = []
        
        # Título
        title = f"RELATÓRIO DE ESTOQUE - PRODUTO {produto_codigo}"
        story.append(Paragraph(title, styles['Heading1']))
        
        # Informações
        info_text = f"""
        <b>Data de Geração:</b> {formatar_data_hora()}<br/>
        <b>Data dos Dados:</b> {formatar_data_hora_arquivo(file_timestamp_str)}<br/>
        <b>Código do Produto:</b> {produto_codigo}<br/>
        <b>Total de Previsões:</b> {len(df_produto)}<br/>
        """
        
        story.append(Paragraph(info_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Adicionar imagem do produto se disponível
        try:
            for image_info in images_created:
                if image_info['produto'] == produto_codigo:
                    image_path = image_info['path']
                    if os.path.exists(image_path):
                        img = Image(image_path, width=400, height=200)
                        story.append(img)
                        story.append(Spacer(1, 20))
                        break
        except Exception as e:
            logger.warning(f"Erro ao adicionar imagem do produto: {e}")
        
        # Resumo estatístico
        try:
            # Calcular totais
            total_estoque = 0
            total_pedidos = 0
            total_disponivel = 0
            
            for _, row in df_produto.iterrows():
                total_estoque += converter_valor_brasileiro(row['Estoque'])
                total_pedidos += converter_valor_brasileiro(row['Pedidos'])
                total_disponivel += converter_valor_brasileiro(row['Disponível'])
            
            summary_text = f"""
            <b>RESUMO ESTATÍSTICO:</b><br/>
            <b>Estoque Total:</b> {formatar_valor_brasileiro(total_estoque)}<br/>
            <b>Pedidos Total:</b> {formatar_valor_brasileiro(total_pedidos)}<br/>
            <b>Disponível Total:</b> {formatar_valor_brasileiro(total_disponivel)}<br/>
            """
            
            story.append(Paragraph(summary_text, styles['Normal']))
            story.append(Spacer(1, 20))
            
        except Exception as e:
            logger.warning(f"Erro ao calcular estatísticas para produto {produto_codigo}: {e}")
        
        # Tabela de dados - ordenar por previsão
        if len(df_produto) > 0:
            # Ordenar: "Pronta entrega" primeiro, depois datas
            df_produto_sorted = df_produto.copy()
            
            def previsao_sort_key(x):
                previsao = str(x).lower()
                if 'pronta entrega' in previsao:
                    return (0, '')
                else:
                    # Tentar extrair data
                    try:
                        parts = previsao.split('/')
                        if len(parts) == 3:
                            return (1, f"{parts[2]}{parts[1]}{parts[0]}")
                    except:
                        pass
                    return (2, previsao)
            
            df_produto_sorted['sort_key'] = df_produto_sorted['Previsão'].apply(previsao_sort_key)
            df_produto_sorted = df_produto_sorted.sort_values('sort_key')
            df_produto_sorted = df_produto_sorted.drop('sort_key', axis=1)
            
            table_data = []
            
            # Cabeçalho
            headers = ['Produto / Cor', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
            table_data.append(headers)
            
            # Dados
            for _, row in df_produto_sorted.iterrows():
                produto_desc = str(row['Produto / Cor'])
                if len(produto_desc) > 80:
                    produto_desc = produto_desc[:77] + "..."
                
                previsao = str(row['Previsão'])
                
                table_data.append([
                    produto_desc,
                    previsao[:20],
                    str(row['Estoque']),
                    str(row['Pedidos']),
                    str(row['Disponível'])
                ])
            
            # Criar tabela
            table = Table(table_data, colWidths=[200, 80, 60, 60, 60])
            
            # Estilo da tabela
            table.setStyle(TableStyle([
                # Cabeçalho
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                
                # Linhas alternadas
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
                ('ALIGN', (0, 1), (0, -1), 'LEFT'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F2F2F2')]),
            ]))
            
            # Destacar "Pronta entrega"
            for i, row in enumerate(table_data[1:], 1):
                if 'pronta entrega' in str(row[1]).lower():
                    table.setStyle(TableStyle([
                        ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#FFF2CC')),
                    ]))
            
            story.append(table)
        
        # Informações de cores/variantes
        story.append(Spacer(1, 20))
        
        # Listar previsões disponíveis
        if 'Previsão' in df_produto.columns and len(df_produto) > 0:
            previsoes_unicas = df_produto['Previsão'].unique()
            previsoes_text = f"<b>Previsões disponíveis:</b> {len(previsoes_unicas)} tipos"
            story.append(Paragraph(previsoes_text, styles['Normal']))
            
            # Listar primeiras 5 previsões
            if len(previsoes_unicas) > 0:
                previsoes_lista = ", ".join([str(p)[:20] for p in previsoes_unicas[:5]])
                if len(previsoes_unicas) > 5:
                    previsoes_lista += f" e mais {len(previsoes_unicas) - 5}"
                story.append(Paragraph(f"<i>{previsoes_lista}</i>", styles['Italic']))
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer_text = f"Relatório gerado automaticamente pelo Sistema DGB Scraper - {formatar_data_hora()}"
        story.append(Paragraph(footer_text, styles['Italic']))
        
        # Construir PDF
        doc.build(story)
        
        logger.info(f"✅ PDF para produto {produto_codigo} gerado: {os.path.basename(output_path)}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF para produto {produto_codigo}: {e}")
        return False

def generate_summary_pdf(df, output_path, file_timestamp_str, generation_timestamp, images_created):
    """Gera PDF de resumo estatístico"""
    try:
        logger.info(f"Gerando PDF de resumo: {output_path}")
        
        # Criar documento
        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )
        
        # Estilos
        styles = getSampleStyleSheet()
        
        # Elementos do documento
        story = []
        
        # Título
        story.append(Paragraph("RELATÓRIO RESUMIDO - ESTATÍSTICAS DGB", styles['Heading1']))
        
        # Data
        story.append(Paragraph(f"<b>Data de Geração:</b> {formatar_data_hora()}", styles['Normal']))
        story.append(Paragraph(f"<b>Data dos Dados:</b> {formatar_data_hora_arquivo(file_timestamp_str)}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Estatísticas gerais
        total_registros = len(df)
        
        # Extrair produtos únicos
        df['codigo_produto'] = df['Produto / Cor'].apply(extrair_codigo_produto)
        produtos_unicos = [p for p in df['codigo_produto'].unique() 
                          if p and str(p).strip() and str(p).strip() != 'Desconhecido']
        
        # Calcular totais
        try:
            total_estoque = 0
            total_pedidos = 0
            total_disponivel = 0
            
            for _, row in df.iterrows():
                total_estoque += converter_valor_brasileiro(row['Estoque'])
                total_pedidos += converter_valor_brasileiro(row['Pedidos'])
                total_disponivel += converter_valor_brasileiro(row['Disponível'])
            
        except:
            total_estoque = total_pedidos = total_disponivel = 0
        
        # Contar previsões
        if 'Previsão' in df.columns:
            previsoes_counts = df['Previsão'].value_counts()
        else:
            previsoes_counts = pd.Series()
        
        # Seção de estatísticas
        stats_text = f"""
        <b>ESTATÍSTICAS GERAIS:</b><br/><br/>
        <b>Total de Registros:</b> {total_registros}<br/>
        <b>Produtos Únicos:</b> {len(produtos_unicos)}<br/>
        <b>Previsões Únicas:</b> {len(previsoes_counts)}<br/><br/>
        
        <b>TOTAIS:</b><br/>
        <b>Estoque Total:</b> {formatar_valor_brasileiro(total_estoque)}<br/>
        <b>Pedidos Total:</b> {formatar_valor_brasileiro(total_pedidos)}<br/>
        <b>Disponível Total:</b> {formatar_valor_brasileiro(total_disponivel)}<br/><br/>
        """
        
        story.append(Paragraph(stats_text, styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Distribuição por produto (top 10)
        if len(produtos_unicos) > 0:
            story.append(Paragraph("<b>TOP 10 PRODUTOS POR ESTOQUE:</b>", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            # Calcular estoque por produto
            produtos_estoque = []
            for produto in produtos_unicos:
                df_produto = df[df['codigo_produto'] == produto]
                estoque_produto = 0
                for _, row in df_produto.iterrows():
                    estoque_produto += converter_valor_brasileiro(row['Estoque'])
                produtos_estoque.append((produto, estoque_produto))
            
            # Ordenar por estoque
            produtos_estoque.sort(key=lambda x: x[1], reverse=True)
            
            # Tabela de top produtos
            table_data = [['Produto', 'Estoque Total']]
            for produto, estoque in produtos_estoque[:10]:
                table_data.append([produto, formatar_valor_brasileiro(estoque)])
            
            table = Table(table_data, colWidths=[100, 100])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            
            story.append(table)
            story.append(Spacer(1, 20))
        
        # Distribuição por previsão
        if not previsoes_counts.empty:
            story.append(Paragraph("<b>DISTRIBUIÇÃO POR PREVISÃO:</b>", styles['Heading2']))
            story.append(Spacer(1, 10))
            
            table_data = [['Previsão', 'Quantidade']]
            for previsao, count in previsoes_counts.head(10).items():
                previsao_display = str(previsao)[:25] + ("..." if len(str(previsao)) > 25 else "")
                table_data.append([previsao_display, str(count)])
            
            table = Table(table_data, colWidths=[150, 80])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ]))
            
            story.append(table)
        
        # Rodapé
        story.append(Spacer(1, 30))
        footer_text = f"Relatório gerado automaticamente pelo Sistema DGB Scraper - {formatar_data_hora()}"
        story.append(Paragraph(footer_text, styles['Italic']))
        
        # Construir PDF
        doc.build(story)
        
        logger.info(f"✅ PDF de resumo gerado: {os.path.basename(output_path)}")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF de resumo: {e}")
        return False

def converter_valor_brasileiro(val):
    """Converte valores no formato brasileiro para numérico"""
    try:
        if pd.isna(val):
            return 0.0
        
        # Converter string
        val_str = str(val).strip()
        
        # Se estiver vazio, retornar 0
        if not val_str:
            return 0.0
        
        # Remover caracteres não numéricos exceto pontos e vírgulas
        val_str = ''.join(c for c in val_str if c.isdigit() or c in ',.')
        
        # Se ainda estiver vazio, retornar 0
        if not val_str:
            return 0.0
        
        # Remover pontos de milhar e substituir vírgula decimal por ponto
        if ',' in val_str and '.' in val_str:
            # Formato brasileiro: 1.234,56
            # Contar quantos pontos há antes da vírgula
            if val_str.rfind('.') < val_str.rfind(','):
                # Ponto é separador de milhar, vírgula é decimal
                val_str = val_str.replace('.', '').replace(',', '.')
            else:
                # Vírgula é separador de milhar, ponto é decimal
                val_str = val_str.replace(',', '')
        elif ',' in val_str:
            # Formato com apenas vírgula como decimal
            val_str = val_str.replace(',', '.')
        
        # Remover múltiplos pontos
        if val_str.count('.') > 1:
            # Manter apenas o último ponto como decimal
            parts = val_str.split('.')
            val_str = ''.join(parts[:-1]) + '.' + parts[-1]
        
        # Tentar converter para float
        return float(val_str)
    except Exception as e:
        logger.warning(f"Erro ao converter valor '{val}': {e}")
        return 0.0

def formatar_valor_brasileiro(val):
    """Formata valor numérico para formato brasileiro"""
    try:
        if pd.isna(val) or val == 0:
            return "0,00"
        
        # Arredondar para 2 casas decimais
        val = round(float(val), 2)
        
        # Se for inteiro
        if val.is_integer():
            val_int = int(val)
            # Formatar com separador de milhar
            val_str = f"{val_int:,}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{val_str},00"
        else:
            # Formatar com duas casas decimais
            val_str = f"{val:,.2f}"
            # Substituir . por , para decimais e , por . para milhares
            parts = val_str.split('.')
            inteira = parts[0].replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{inteira},{parts[1]}"
    except Exception as e:
        logger.warning(f"Erro ao formatar valor {val}: {e}")
        return "0,00"

def generate_pdf_report(csv_file_path=None):
    """Gera relatórios em PDF a partir do arquivo CSV consolidado - FUNÇÃO PRINCIPAL"""
    try:
        logger.info("=" * 60)
        logger.info("INICIANDO GERAÇÃO DE PDFs (VERSÃO CORRIGIDA)")
        logger.info("=" * 60)
        
        # Se não for fornecido um caminho específico, buscar o arquivo mais recente
        if csv_file_path is None or not os.path.exists(csv_file_path):
            logger.info("Buscando arquivo consolidado CSV mais recente...")
            csv_file_path = find_latest_consolidated_file()
            
            if csv_file_path is None:
                logger.error("❌ Nenhum arquivo CSV consolidado encontrado!")
                return {'success': False, 'error': 'Nenhum arquivo CSV consolidado encontrado'}
        
        # Verificar se é realmente um arquivo CSV
        if not csv_file_path.lower().endswith('.csv'):
            logger.error(f"❌ O arquivo não é CSV: {csv_file_path}")
            logger.info("Por favor, execute a consolidação para gerar um arquivo CSV")
            return {'success': False, 'error': 'Arquivo não é CSV. Execute a consolidação primeiro.'}
        
        # Extrair timestamp do arquivo
        file_timestamp_dt, file_timestamp_str = extract_timestamp_from_filename(csv_file_path)
        logger.info(f"📄 Arquivo fonte: {csv_file_path}")
        logger.info(f"📅 Timestamp do arquivo: {file_timestamp_str}")
        
        # Ler o CSV consolidado
        if not os.path.exists(csv_file_path):
            logger.error(f"❌ Arquivo não encontrado: {csv_file_path}")
            return {'success': False, 'error': f'Arquivo CSV não encontrado: {csv_file_path}'}
        
        # Ler CSV
        df = read_csv_file(csv_file_path)
        
        if df is None or df.empty:
            logger.error("❌ Não foi possível ler o CSV ou está vazio")
            return {'success': False, 'error': 'Não foi possível ler o CSV ou está vazio'}
        
        # Limpar e preparar dados (VERSÃO CORRIGIDA - não remove duplicatas)
        df = clean_and_prepare_data(df)
        
        if df.empty:
            logger.error("❌ Dados limpos estão vazios")
            return {'success': False, 'error': 'Dados limpos estão vazios'}
        
        # Extrair informações básicas
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')  # Para os arquivos de saída
        total_registros = len(df)
        
        logger.info(f"📊 Total de registros (com múltiplas previsões): {total_registros}")
        
        # Extrair códigos de produtos únicos
        df['codigo_produto'] = df['Produto / Cor'].apply(extrair_codigo_produto)
        produtos_unicos = [p for p in df['codigo_produto'].unique() 
                          if p and str(p).strip() and str(p).strip() != 'Desconhecido']
        
        logger.info(f"📦 Produtos únicos encontrados: {len(produtos_unicos)}")
        
        # Criar pasta para saída se não existir
        os.makedirs('pdfs', exist_ok=True)
        
        # Criar lista de PDFs gerados
        pdf_files_created = []
        
        # Criar pasta para imagens
        os.makedirs('images', exist_ok=True)
        
        # 1. Gerar imagens JPG para cada produto
        logger.info("🎨 Gerando imagens JPG...")
        images_created = generate_product_images(df, timestamp)
        
        # 2. Gerar PDF com TODOS os produtos (mostrando múltiplas previsões)
        all_pdf_filename = f"relatorio_todos_produtos_{timestamp}.pdf"
        all_pdf_path = os.path.join('pdfs', all_pdf_filename)
        
        success = generate_all_products_pdf(df, all_pdf_path, total_registros, 
                                           file_timestamp_str, timestamp, 
                                           os.path.basename(csv_file_path), images_created)
        
        if success:
            pdf_files_created.append({
                'type': 'all',
                'name': all_pdf_filename,
                'desc': 'Relatório Completo'
            })
        
        # 3. Gerar PDF para cada produto (limitar a 30 produtos)
        if produtos_unicos:
            logger.info(f"📄 Gerando PDFs individuais para {min(30, len(produtos_unicos))} produtos...")
            for i, produto in enumerate(produtos_unicos[:30]):
                try:
                    # Filtrar dados do produto
                    df_produto = df[df['codigo_produto'] == produto].copy()
                    
                    if len(df_produto) == 0:
                        continue
                    
                    # Gerar PDF para o produto
                    produto_pdf_filename = f"relatorio_produto_{produto}_{timestamp}.pdf"
                    produto_pdf_path = os.path.join('pdfs', produto_pdf_filename)
                    
                    success = generate_single_product_pdf(df_produto, produto_pdf_path, 
                                                         produto, file_timestamp_str, 
                                                         timestamp, images_created)
                    
                    if success:
                        pdf_files_created.append({
                            'type': 'product',
                            'name': produto_pdf_filename,
                            'desc': f'Produto {produto}'
                        })
                        
                except Exception as e:
                    logger.error(f"❌ Erro ao gerar PDF para produto {produto}: {e}")
                    continue
        
        # 4. Gerar PDF de resumo estatístico
        logger.info("📊 Gerando PDF de resumo...")
        summary_pdf_filename = f"resumo_estatistico_{timestamp}.pdf"
        summary_pdf_path = os.path.join('pdfs', summary_pdf_filename)
        
        success = generate_summary_pdf(df, summary_pdf_path, file_timestamp_str, 
                                      timestamp, images_created)
        
        if success:
            pdf_files_created.append({
                'type': 'summary',
                'name': summary_pdf_filename,
                'desc': 'Resumo Estatístico'
            })
        
        logger.info("=" * 60)
        logger.info("✅ GERAÇÃO DE PDFs CONCLUÍDA")
        logger.info(f"📄 PDFs gerados: {len(pdf_files_created)}")
        logger.info(f"🖼️ Imagens geradas: {len(images_created)}")
        logger.info(f"📊 Total de registros processados: {total_registros}")
        logger.info(f"📦 Produtos únicos: {len(produtos_unicos)}")
        logger.info("=" * 60)
        
        return {
            'success': True,
            'message': f'Gerados {len(pdf_files_created)} arquivos PDF e {len(images_created)} imagens JPG',
            'pdf_files': pdf_files_created,
            'image_files': images_created,
            'total_registros': total_registros,
            'produtos_unicos': len(produtos_unicos),
            'source_file': os.path.basename(csv_file_path),
            'source_timestamp': file_timestamp_str
        }
        
    except Exception as e:
        logger.error(f"❌ Erro na geração de PDFs: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}