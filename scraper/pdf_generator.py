# pdf_generator.py - Geração de PDFs e imagens - CORRIGIDO
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

logger = logging.getLogger(__name__)

def generate_pdf_report(csv_file_path):
    """Gera relatórios em PDF a partir do arquivo CSV consolidado"""
    try:
        # Ler o CSV consolidado com encoding correto
        if not os.path.exists(csv_file_path):
            return {'success': False, 'error': 'Arquivo CSV não encontrado'}
        
        # Ler CSV com tratamento de erros
        df = read_csv_with_error_handling(csv_file_path)
        
        if df is None or df.empty:
            return {'success': False, 'error': 'Não foi possível ler o CSV ou está vazio'}
        
        # Limpar e preparar dados
        df = clean_and_prepare_data(df)
        
        # Extrair informações básicas
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        total_registros = len(df)
        
        # Extrair códigos de produtos únicos
        df['codigo_produto'] = df['Produto / Cor'].apply(extrair_codigo_produto)
        produtos_unicos = df['codigo_produto'].unique()
        
        # Criar lista de PDFs gerados
        pdf_files_created = []
        
        # Criar pasta para imagens
        os.makedirs('images', exist_ok=True)
        
        # 1. Gerar imagens JPG para cada produto
        images_created = generate_product_images(df, timestamp)
        
        # 2. Gerar PDF com TODOS os produtos
        all_pdf_filename = f"relatorio_todos_produtos_{timestamp}.pdf"
        all_pdf_path = os.path.join('pdfs', all_pdf_filename)
        
        success = generate_all_products_pdf(df, all_pdf_path, total_registros, timestamp, images_created)
        
        if success:
            pdf_files_created.append({
                'type': 'all',
                'name': all_pdf_filename,
                'desc': 'Relatório Completo'
            })
        
        # 3. Gerar PDF para cada produto (limitar a 50 produtos)
        for i, produto in enumerate(produtos_unicos[:50]):
            try:
                # Filtrar dados do produto
                df_produto = df[df['codigo_produto'] == produto].copy()
                
                if len(df_produto) == 0:
                    continue
                
                # Gerar PDF para o produto
                produto_pdf_filename = f"relatorio_produto_{produto}_{timestamp}.pdf"
                produto_pdf_path = os.path.join('pdfs', produto_pdf_filename)
                
                success = generate_single_product_pdf(df_produto, produto_pdf_path, produto, timestamp, images_created)
                
                if success:
                    pdf_files_created.append({
                        'type': 'product',
                        'name': produto_pdf_filename,
                        'desc': f'Produto {produto}'
                    })
                    
            except Exception as e:
                logger.error(f"Erro ao gerar PDF para produto {produto}: {e}")
                continue
        
        # 4. Gerar PDF de resumo estatístico
        summary_pdf_filename = f"resumo_estatistico_{timestamp}.pdf"
        summary_pdf_path = os.path.join('pdfs', summary_pdf_filename)
        
        success = generate_summary_pdf(df, summary_pdf_path, timestamp, images_created)
        
        if success:
            pdf_files_created.append({
                'type': 'summary',
                'name': summary_pdf_filename,
                'desc': 'Resumo Estatístico'
            })
        
        return {
            'success': True,
            'message': f'Gerados {len(pdf_files_created)} arquivos PDF e {len(images_created)} imagens JPG',
            'pdf_files': pdf_files_created,
            'image_files': images_created,
            'total_registros': total_registros,
            'produtos_unicos': len(produtos_unicos)
        }
        
    except Exception as e:
        logger.error(f"Erro na geração de PDFs: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'success': False, 'error': str(e)}

def read_csv_with_error_handling(csv_file_path):
    """Lê CSV com tratamento robusto de erros"""
    try:
        # Tentar diferentes encodings
        encodings = ['utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1', 'utf-8']
        
        for encoding in encodings:
            try:
                logger.info(f"Tentando ler CSV com encoding: {encoding}")
                
                # Tentar ler normalmente primeiro
                try:
                    df = pd.read_csv(csv_file_path, delimiter=';', encoding=encoding, on_bad_lines='warn')
                    if not df.empty:
                        logger.info(f"CSV lido com sucesso usando encoding: {encoding}")
                        return df
                except Exception as e:
                    logger.warning(f"Falha ao ler com pandas: {e}")
                
                # Se falhar, tentar leitura manual
                try:
                    data = []
                    with open(csv_file_path, 'r', encoding=encoding) as f:
                        # Ler o arquivo linha por linha
                        lines = f.readlines()
                        
                        if not lines:
                            continue
                        
                        # Tentar detectar o delimitador
                        first_line = lines[0]
                        delimiter = ';' if ';' in first_line else ','
                        
                        # Ler todas as linhas
                        for i, line in enumerate(lines):
                            try:
                                # Limpar a linha
                                line = line.strip()
                                if not line:
                                    continue
                                    
                                # Dividir pelo delimitador
                                parts = line.split(delimiter)
                                
                                # Se for a primeira linha (cabeçalho)
                                if i == 0:
                                    headers = parts
                                else:
                                    # Garantir que temos o mesmo número de colunas que o cabeçalho
                                    if len(parts) != len(headers):
                                        # Tentar correção se houver citação
                                        if '"' in line:
                                            # Usar csv.reader para lidar com campos citados
                                            f.seek(0)
                                            csv_reader = csv.reader(f, delimiter=delimiter)
                                            headers = next(csv_reader)
                                            data = []
                                            for row in csv_reader:
                                                if len(row) == len(headers):
                                                    data.append(row)
                                            df = pd.DataFrame(data, columns=headers)
                                            return df
                                        else:
                                            # Preencher ou truncar para corresponder ao cabeçalho
                                            if len(parts) > len(headers):
                                                parts = parts[:len(headers)]
                                            else:
                                                while len(parts) < len(headers):
                                                    parts.append('')
                                    data.append(parts)
                                    
                            except Exception as line_error:
                                logger.warning(f"Erro na linha {i+1}: {line_error}")
                                continue
                    
                    if headers and data:
                        df = pd.DataFrame(data, columns=headers)
                        logger.info(f"CSV lido manualmente com {len(df)} registros")
                        return df
                        
                except Exception as manual_error:
                    logger.warning(f"Falha na leitura manual: {manual_error}")
                    continue
                    
            except Exception as encoding_error:
                logger.warning(f"Erro com encoding {encoding}: {encoding_error}")
                continue
        
        # Última tentativa: usar engine python com sep=None (detecção automática)
        try:
            df = pd.read_csv(csv_file_path, sep=None, engine='python', encoding='latin-1')
            if not df.empty:
                logger.info("CSV lido com detecção automática de separador")
                return df
        except Exception as e:
            logger.error(f"Falha na detecção automática: {e}")
        
        return None
        
    except Exception as e:
        logger.error(f"Erro crítico na leitura do CSV: {e}")
        return None

def clean_and_prepare_data(df):
    """Limpa e prepara os dados do DataFrame"""
    try:
        # Remover linhas totalmente vazias
        df = df.dropna(how='all')
        
        # Remover colunas totalmente vazias
        df = df.dropna(axis=1, how='all')
        
        # Renomear colunas para nomes padrão se necessário
        expected_columns = ['Produto / Cor', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        
        # Tentar encontrar colunas correspondentes
        column_mapping = {}
        for expected in expected_columns:
            for actual in df.columns:
                if expected.lower() in actual.lower():
                    column_mapping[actual] = expected
                    break
        
        # Renomear colunas se encontradas
        if column_mapping:
            df = df.rename(columns=column_mapping)
        
        # Garantir que temos as colunas necessárias
        missing_columns = [col for col in expected_columns if col not in df.columns]
        if missing_columns:
            for col in missing_columns:
                df[col] = ''
        
        # Preencher valores NaN
        df = df.fillna('')
        
        # Converter tipos de dados
        for col in ['Estoque', 'Pedidos', 'Disponível']:
            if col in df.columns:
                # Tentar converter para string primeiro
                df[col] = df[col].astype(str)
        
        return df
        
    except Exception as e:
        logger.error(f"Erro na limpeza de dados: {e}")
        return df

def generate_product_images(df, timestamp):
    """Gera imagens JPG para cada produto com gráficos"""
    images_created = []
    
    try:
        # Extrair produtos únicos
        df['codigo_produto'] = df['Produto / Cor'].apply(extrair_codigo_produto)
        produtos_unicos = df['codigo_produto'].unique()
        
        for produto in produtos_unicos[:50]:  # Limitar a 50 produtos
            try:
                # Filtrar dados do produto
                df_produto = df[df['codigo_produto'] == produto].copy()
                
                if len(df_produto) == 0:
                    continue
                
                # Converter valores para numérico
                try:
                    df_produto['Estoque_num'] = df_produto['Estoque'].apply(converter_valor_brasileiro)
                    df_produto['Pedidos_num'] = df_produto['Pedidos'].apply(converter_valor_brasileiro)
                    df_produto['Disponível_num'] = df_produto['Disponível'].apply(converter_valor_brasileiro)
                except:
                    # Se não conseguir converter, usar zeros
                    df_produto['Estoque_num'] = 0
                    df_produto['Pedidos_num'] = 0
                    df_produto['Disponível_num'] = 0
                
                # Verificar se temos dados válidos
                if df_produto['Estoque_num'].sum() == 0 and df_produto['Pedidos_num'].sum() == 0:
                    continue
                
                # Criar figura com subplots
                fig, axes = plt.subplots(1, 2, figsize=(12, 6))
                fig.suptitle(f'Produto {produto}', fontsize=16, fontweight='bold')
                
                # Gráfico 1: Barras empilhadas
                if len(df_produto) > 0:
                    # Pegar até 5 primeiras variantes
                    df_display = df_produto.head(5)
                    
                    # Preparar dados para gráfico
                    variantes = []
                    for i, row in df_display.iterrows():
                        # Extrair cor da descrição
                        desc = str(row['Produto / Cor'])
                        if 'COR:' in desc:
                            try:
                                cor = desc.split('COR:')[-1].split('-')[0].strip()[:20]
                            except:
                                cor = f"Var{i+1}"
                        else:
                            cor = f"Var{i+1}"
                        variantes.append(cor)
                    
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
                    axes[0].set_title('Estoque vs Pedidos vs Disponível')
                    axes[0].set_xticks(x)
                    axes[0].set_xticklabels(variantes, rotation=45, ha='right')
                    axes[0].legend()
                    axes[0].grid(True, alpha=0.3)
                
                # Gráfico 2: Pizza de distribuição
                if len(df_produto) > 0:
                    try:
                        total_estoque = df_produto['Estoque_num'].sum()
                        total_pedidos = df_produto['Pedidos_num'].sum()
                        total_disponivel = df_produto['Disponível_num'].sum()
                        
                        sizes = [total_estoque, total_pedidos, total_disponivel]
                        labels = ['Estoque', 'Pedidos', 'Disponível']
                        colors_pie = ['#ff9999', '#66b3ff', '#99ff99']
                        
                        # Remover zeros
                        valid_data = [(s, l, c) for s, l, c in zip(sizes, labels, colors_pie) if s > 0]
                        
                        if valid_data:
                            sizes_filt = [d[0] for d in valid_data]
                            labels_filt = [d[1] for d in valid_data]
                            colors_filt = [d[2] for d in valid_data]
                            
                            axes[1].pie(sizes_filt, labels=labels_filt, colors=colors_filt, autopct='%1.1f%%', startangle=90)
                            axes[1].axis('equal')
                            axes[1].set_title('Distribuição Total')
                        else:
                            axes[1].text(0.5, 0.5, 'Sem dados', ha='center', va='center', fontsize=12)
                            axes[1].set_title('Distribuição Total')
                    except:
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
        
        return images_created
        
    except Exception as e:
        logger.error(f"Erro na geração de imagens: {e}")
        return []

def extrair_codigo_produto(descricao):
    """Extrai código do produto da descrição"""
    try:
        if isinstance(descricao, str):
            # Exemplo: "000014 - VELUDO CONFORT - COR: 5 - BLACK"
            partes = descricao.split(' - ')
            if len(partes) > 0:
                return partes[0].strip()
            else:
                return descricao.strip()
        else:
            return str(descricao).strip()
    except:
        try:
            return str(descricao).strip()
        except:
            return "Desconhecido"

def formatar_data_hora():
    """Formata data e hora para o relatório"""
    now = datetime.now()
    return now.strftime('%d/%m/%Y %H:%M:%S')

def generate_all_products_pdf(df, output_path, total_registros, timestamp, images_created):
    """Gera PDF com todos os produtos"""
    try:
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
        <b>Total de Registros:</b> {total_registros}<br/>
        <b>Total de Produtos:</b> {len(df['codigo_produto'].unique()) if 'codigo_produto' in df.columns else 'N/A'}<br/>
        <b>Arquivo Fonte:</b> consolidado_organizado_{timestamp}.csv
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
        
        # Preparar dados para tabela
        df_table = df.copy()
        
        # Limitar o número de registros para não sobrecarregar o PDF
        if len(df_table) > 100:
            df_table = df_table.head(100)
            story.append(Paragraph(f"<i>Mostrando 100 de {total_registros} registros...</i>", styles['Italic']))
            story.append(Spacer(1, 10))
        
        # Converter DataFrame para lista para a tabela
        table_data = []
        
        # Cabeçalho
        headers = ['Produto', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        table_data.append(headers)
        
        # Dados
        for _, row in df_table.iterrows():
            # Truncar descrição se muito longa
            produto_desc = str(row['Produto / Cor'])[:50]
            
            table_data.append([
                produto_desc,
                str(row['Previsão'])[:20],
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
        ]))
        
        story.append(table)
        
        # Estatísticas rápidas
        story.append(Spacer(1, 30))
        story.append(Paragraph("<b>ESTATÍSTICAS RÁPIDAS:</b>", styles['Heading2']))
        story.append(Spacer(1, 10))
        
        try:
            # Tentar calcular estatísticas
            total_estoque = 0
            total_pedidos = 0
            total_disponivel = 0
            
            for _, row in df.iterrows():
                total_estoque += converter_valor_brasileiro(row['Estoque'])
                total_pedidos += converter_valor_brasileiro(row['Pedidos'])
                total_disponivel += converter_valor_brasileiro(row['Disponível'])
            
            stats_text = f"""
            <b>Estoque Total:</b> {formatar_valor_brasileiro(total_estoque)}<br/>
            <b>Pedidos Total:</b> {formatar_valor_brasileiro(total_pedidos)}<br/>
            <b>Disponível Total:</b> {formatar_valor_brasileiro(total_disponivel)}<br/>
            """
            
            story.append(Paragraph(stats_text, styles['Normal']))
        except Exception as e:
            logger.warning(f"Erro ao calcular estatísticas: {e}")
        
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

def generate_single_product_pdf(df_produto, output_path, produto_codigo, timestamp, images_created):
    """Gera PDF para um produto específico"""
    try:
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
        <b>Código do Produto:</b> {produto_codigo}<br/>
        <b>Total de Variantes:</b> {len(df_produto)}<br/>
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
            # Tentar calcular totais
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
        
        # Tabela de dados
        if len(df_produto) > 0:
            table_data = []
            
            # Cabeçalho
            headers = ['Produto / Cor', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
            table_data.append(headers)
            
            # Dados
            for _, row in df_produto.iterrows():
                table_data.append([
                    str(row['Produto / Cor'])[:100],
                    str(row['Previsão'])[:20],
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
            
            story.append(table)
        
        # Informações de cores/variantes
        story.append(Spacer(1, 30))
        
        if 'Produto / Cor' in df_produto.columns and len(df_produto) > 0:
            colors_info = []
            for desc in df_produto['Produto / Cor']:
                # Extrair informação de cor
                desc_str = str(desc)
                if 'COR:' in desc_str:
                    try:
                        color_part = desc_str.split('COR:')[-1].strip()
                        colors_info.append(color_part[:50])
                    except:
                        pass
            
            if colors_info:
                colors_text = f"<b>Cores/Variantes Disponíveis:</b> {', '.join(colors_info[:5])}"
                story.append(Paragraph(colors_text, styles['Normal']))
        
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

def generate_summary_pdf(df, output_path, timestamp, images_created):
    """Gera PDF de resumo estatístico"""
    try:
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
        story.append(Paragraph(f"<b>Data:</b> {formatar_data_hora()}", styles['Normal']))
        story.append(Spacer(1, 20))
        
        # Adicionar imagem de exemplo se disponível
        if images_created:
            try:
                first_image_path = images_created[0]['path']
                if os.path.exists(first_image_path):
                    img = Image(first_image_path, width=300, height=150)
                    story.append(img)
                    story.append(Spacer(1, 20))
            except Exception as e:
                logger.warning(f"Erro ao adicionar imagem ao resumo: {e}")
        
        # Estatísticas gerais
        total_registros = len(df)
        
        # Extrair produtos únicos
        df['codigo_produto'] = df['Produto / Cor'].apply(extrair_codigo_produto)
        produtos_unicos = df['codigo_produto'].unique()
        
        # Contar previsões
        try:
            previsoes_counts = df['Previsão'].value_counts()
        except:
            previsoes_counts = pd.Series()
        
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
        
        # Seção de estatísticas
        stats_text = f"""
        <b>ESTATÍSTICAS GERAIS:</b><br/><br/>
        <b>Total de Registros:</b> {total_registros}<br/>
        <b>Produtos Únicos:</b> {len(produtos_unicos)}<br/><br/>
        
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
            for produto in produtos_unicos[:10]:
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
                table_data.append([str(previsao)[:30], str(count)])
            
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