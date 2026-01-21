# parser_dgb.py - Parser ATUALIZADO para HTML do DGB
import re
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser atualizado para HTML do DGB baseado na estrutura real"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remover scripts e styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        
        # Método 1: Procurar por tabelas de dados
        tabelas = soup.find_all('table')
        
        if not tabelas:
            logger.warning(f"Nenhuma tabela encontrada para produto {produto_codigo}")
            # Usar método alternativo de busca por texto
            return parse_texto_detalhado(html_content, produto_codigo, timestamp, artigo)
        
        logger.info(f"Encontradas {len(tabelas)} tabelas para produto {produto_codigo}")
        
        # Procurar por todas as ocorrências do produto no HTML
        texto_completo = soup.get_text(separator='\n')
        
        # Dividir em seções baseado em "Produto / Situação / Cor / Desenho / Variante"
        secoes = re.split(r'Produto\s*/\s*Situação\s*/\s*Cor\s*/\s*Desenho\s*/\s*Variante', texto_completo)
        
        # A primeira seção é o cabeçalho, descartar
        for secao_idx, secao in enumerate(secoes[1:], 1):
            linhas = secao.strip().split('\n')
            
            if not linhas:
                continue
                
            # A primeira linha da seção contém os dados do produto
            descricao_produto = linhas[0].strip() if linhas else ""
            
            # Procurar linhas com dados numéricos
            previsao_atual = "Pronta entrega"
            
            for i, linha in enumerate(linhas):
                linha = linha.strip()
                
                # Verificar se é uma data (previsão)
                match_data = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', linha)
                if match_data:
                    previsao_atual = match_data.group(1)
                    continue
                
                # Procurar por linha com 3 valores numéricos no formato brasileiro
                # Padrão: número com ponto de milhar e vírgula decimal
                padrao_valores = r'^([\d\.]+,\d{2})\s+([\d\.]+,\d{2})\s+([\d\.]+,\d{2})$'
                match_valores = re.match(padrao_valores, linha)
                
                if match_valores:
                    estoque = match_valores.group(1)
                    pedidos = match_valores.group(2)
                    disponivel = match_valores.group(3)
                    
                    # Criar registro
                    registro = [
                        artigo,
                        timestamp,
                        f"{descricao_produto}",
                        previsao_atual,
                        estoque,
                        pedidos,
                        disponivel
                    ]
                    registros.append(registro)
                    
                    logger.info(f"  → Registro {len(registros)}: {previsao_atual} | Estoque: {estoque} | Pedidos: {pedidos} | Disponível: {disponivel}")
        
        # Método alternativo: busca mais agressiva no HTML completo
        if not registros:
            registros = parse_html_agressivo(html_content, produto_codigo, timestamp, artigo)
        
        # Se ainda não encontrou nada, criar registro vazio
        if not registros:
            logger.warning(f"Nenhum dado extraído para produto {produto_codigo}")
            registro = [
                artigo,
                timestamp,
                f"Produto {produto_codigo} - Dados não encontrados",
                "N/A",
                "0,00",
                "0,00",
                "0,00"
            ]
            registros.append(registro)
        
        logger.info(f"Total de registros para {produto_codigo}: {len(registros)}")
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser para {produto_codigo}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Retornar registro de erro
        return [[artigo, timestamp, f"Produto {produto_codigo} - Erro no parser: {str(e)}", "Erro", "0,00", "0,00", "0,00"]]

def parse_texto_detalhado(html_content, produto_codigo, timestamp, artigo):
    """Método mais detalhado de parsing por texto"""
    registros = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        texto_completo = soup.get_text(separator=' ')
        
        # Padrões de busca
        padroes = [
            r'(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})',
            r'([\d\.]+,\d{2})\s+([\d\.]+,\d{2})\s+([\d\.]+,\d{2})',
            r'Estoque[\s:]*([\d\.,]+).*Pedidos[\s:]*([\d\.,]+).*Disponível[\s:]*([\d\.,]+)'
        ]
        
        # Dividir texto em linhas
        linhas = texto_completo.split('  ')  # Separar por múltiplos espaços
        
        previsao = "Pronta entrega"
        descricao = f"Produto {produto_codigo}"
        
        for linha in linhas:
            linha = linha.strip()
            
            # Verificar se contém o código do produto
            if str(produto_codigo) in linha:
                descricao = linha[:200]
            
            # Verificar se é uma data
            match_data = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', linha)
            if match_data:
                previsao = match_data.group(1)
                continue
            
            # Procurar por valores
            for padrao in padroes:
                matches = re.findall(padrao, linha)
                
                for match in matches:
                    if len(match) >= 3:
                        estoque = formatar_valor(match[0])
                        pedidos = formatar_valor(match[1])
                        disponivel = formatar_valor(match[2])
                        
                        # Verificar se são valores válidos (não todos zeros)
                        if estoque != "0,00" or pedidos != "0,00" or disponivel != "0,00":
                            registro = [
                                artigo,
                                timestamp,
                                descricao,
                                previsao,
                                estoque,
                                pedidos,
                                disponivel
                            ]
                            registros.append(registro)
                            
                            logger.info(f"Método detalhado: {previsao} | Estoque: {estoque}")
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parse detalhado: {e}")
        return []

def parse_html_agressivo(html_content, produto_codigo, timestamp, artigo):
    """Método agressivo: busca por todos os dados numéricos no HTML"""
    registros = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Encontrar todas as tags <tr> (linhas de tabela)
        trs = soup.find_all('tr')
        
        for tr in trs:
            texto_linha = tr.get_text(separator=' ', strip=True)
            
            # Procurar por padrão de 3 valores
            padrao = r'(\d[\d\.,]+\d)\s+(\d[\d\.,]+\d)\s+(\d[\d\.,]+\d)'
            match = re.search(padrao, texto_linha)
            
            if match:
                # Tentar encontrar data na linha anterior
                previsao = "Pronta entrega"
                
                # Verificar a linha atual primeiro
                match_data = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', texto_linha)
                if match_data:
                    previsao = match_data.group(1)
                
                # Verificar linha anterior
                if tr.previous_sibling and hasattr(tr.previous_sibling, 'get_text'):
                    texto_anterior = tr.previous_sibling.get_text(separator=' ', strip=True)
                    match_data = re.search(r'\b(\d{2}/\d{2}/\d{4})\b', texto_anterior)
                    if match_data:
                        previsao = match_data.group(1)
                
                estoque = formatar_valor(match.group(1))
                pedidos = formatar_valor(match.group(2))
                disponivel = formatar_valor(match.group(3))
                
                registro = [
                    artigo,
                    timestamp,
                    f"Produto {produto_codigo} - linha encontrada",
                    previsao,
                    estoque,
                    pedidos,
                    disponivel
                ]
                registros.append(registro)
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parse agressivo: {e}")
        return []

def formatar_valor(valor_str):
    """Formata valor para o padrão brasileiro"""
    try:
        if not valor_str:
            return "0,00"
        
        # Remover espaços
        valor_str = str(valor_str).strip().replace(' ', '')
        
        # Verificar se já está formatado
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor_str):
            return valor_str
        
        # Se tem apenas números
        if valor_str.replace('.', '').replace(',', '').isdigit():
            # Adicionar vírgula para centavos se não tiver
            if ',' not in valor_str:
                valor_str = valor_str + ',00'
            
            # Adicionar pontos de milhar
            partes = valor_str.split(',')
            inteiro = partes[0]
            decimal = partes[1] if len(partes) > 1 else '00'
            
            # Formatar com pontos de milhar
            try:
                inteiro_int = int(inteiro.replace('.', ''))
                inteiro_formatado = f"{inteiro_int:,}".replace(',', '.')
            except:
                inteiro_formatado = inteiro
            
            return f"{inteiro_formatado},{decimal[:2].ljust(2, '0')}"
        
        return valor_str
        
    except:
        return "0,00"

def salvar_html_para_debug(html_content, produto_codigo):
    """Salva HTML para análise de debug"""
    try:
        os.makedirs('debug', exist_ok=True)
        filename = f"debug_produto_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        filepath = os.path.join('debug', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"HTML salvo para debug: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Erro ao salvar HTML debug: {e}")
        return None

def criar_csv_direto(produto_codigo, registros):
    """Cria CSV diretamente dos registros"""
    try:
        if not registros:
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"produto_{produto_codigo}_{timestamp}.csv"
        
        os.makedirs('csv', exist_ok=True)
        
        with open(f'csv/{filename}', 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante',
                           'Previsão', 'Estoque', 'Pedidos', 'Disponível'])
            writer.writerows(registros)
        
        logger.info(f"CSV criado: {filename}")
        return filename
        
    except Exception as e:
        logger.error(f"Erro ao criar CSV: {e}")
        return None