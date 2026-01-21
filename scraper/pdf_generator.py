# pdf_generator.py - Geração de PDFs e imagens
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

logger = logging.getLogger(__name__)

def generate_pdf_report(csv_file_path):
    """Gera relatórios em PDF a partir do arquivo CSV consolidado"""
    try:
        # Ler o CSV consolidado com encoding correto
        if not os.path.exists(csv_file_path):
            return {'success': False, 'error': 'Arquivo CSV não encontrado'}
        
        # Tentar diferentes encodings
        encodings = ['utf-8-sig', 'latin-1', 'cp1252', 'iso-8859-1']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(csv_file_path, delimiter=';', encoding=encoding)
                logger.info(f"CSV lido com encoding: {encoding}")
                break
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.warning(f"Erro com encoding {encoding}: {e}")
                continue
        
        if df is None or df.empty:
            return {'success': False, 'error': 'Não foi possível ler o CSV ou está vazio'}
        
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
                
                # Converter valores para numérico
                df_produto['Estoque_num'] = df_produto['Estoque'].apply(converter_valor_brasileiro)
                df_produto['Pedidos_num'] = df_produto['Pedidos'].apply(converter_valor_brasileiro)
                df_produto['Disponível_num'] = df_produto['Disponível'].apply(converter_valor_brasileiro)
                
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
                            cor = desc.split('COR:')[-1].split('-')[0].strip()[:20]
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
            return partes[0] if len(partes) > 0 else descricao
        else:
            return str(descricao)
    except:
        return str(descricao)

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
        <b>Total de Produtos:</b> {len(df['codigo_produto'].unique())}<br/>
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
            produto_desc = str(row['Produto / Cor'])
            if len(produto_desc) > 50:
                produto_desc = produto_desc[:47] + "..."
            
            table_data.append([
                produto_desc,
                str(row['Previsão']),
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
            df['Estoque_num'] = df['Estoque'].apply(converter_valor_brasileiro)
            df['Pedidos_num'] = df['Pedidos'].apply(converter_valor_brasileiro)
            df['Disponível_num'] = df['Disponível'].apply(converter_valor_brasileiro)
            
            total_estoque = df['Estoque_num'].sum()
            total_pedidos = df['Pedidos_num'].sum()
            total_disponivel = df['Disponível_num'].sum()
            
            stats_text = f"""
            <b>Estoque Total:</b> {formatar_valor_brasileiro(total_estoque)}<br/>
            <b>Pedidos Total:</b> {formatar_valor_brasileiro(total_pedidos)}<br/>
            <b>Disponível Total:</b> {formatar_valor_brasileiro(total_disponivel)}<br/>
            """
            
            story.append(Paragraph(stats_text, styles['Normal']))
        except:
            pass
        
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
            # Converter valores para numérico para cálculos
            df_produto['Estoque_num'] = df_produto['Estoque'].apply(converter_valor_brasileiro)
            df_produto['Pedidos_num'] = df_produto['Pedidos'].apply(converter_valor_brasileiro)
            df_produto['Disponível_num'] = df_produto['Disponível'].apply(converter_valor_brasileiro)
            
            total_estoque = df_produto['Estoque_num'].sum()
            total_pedidos = df_produto['Pedidos_num'].sum()
            total_disponivel = df_produto['Disponível_num'].sum()
            
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
        table_data = []
        
        # Cabeçalho
        headers = ['Produto / Cor', 'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        table_data.append(headers)
        
        # Dados
        for _, row in df_produto.iterrows():
            table_data.append([
                str(row['Produto / Cor']),
                str(row['Previsão']),
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
        
        if 'Produto / Cor' in df_produto.columns:
            colors_info = []
            for desc in df_produto['Produto / Cor']:
                # Extrair informação de cor
                if 'COR:' in str(desc):
                    color_part = str(desc).split('COR:')[-1].strip()
                    colors_info.append(color_part)
            
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
        previsoes_counts = df['Previsão'].value_counts()
        
        # Calcular totais
        try:
            df['Estoque_num'] = df['Estoque'].apply(converter_valor_brasileiro)
            df['Pedidos_num'] = df['Pedidos'].apply(converter_valor_brasileiro)
            df['Disponível_num'] = df['Disponível'].apply(converter_valor_brasileiro)
            
            total_estoque = df['Estoque_num'].sum()
            total_pedidos = df['Pedidos_num'].sum()
            total_disponivel = df['Disponível_num'].sum()
            
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
                estoque_produto = df_produto['Estoque_num'].sum() if 'Estoque_num' in df_produto.columns else 0
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
                table_data.append([previsao, str(count)])
            
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
        return "0,00"