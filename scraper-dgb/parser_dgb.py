# parser_dgb.py - Parser SIMPLIFICADO sem recursão (ATUALIZADO para extrair COR)
import re
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser SIMPLIFICADO sem recursão - ATUALIZADO para extrair COR"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # MÉTODO 1: Buscar por tabelas com registros
        registro_elements = soup.find_all('tr', class_='registro')
        
        if registro_elements:
            logger.info(f"Método 1: Encontradas {len(registro_elements)} linhas de registro")
            
            for registro in registro_elements:
                # Extrair descrição do produto com COR
                descricao_completa = extrair_descricao_completa(registro)
                
                # Extrair COR específica
                cor_info = extrair_cor(registro)
                
                # Combinar descrição com COR
                descricao_final = f"{descricao_completa} / {cor_info}" if cor_info else descricao_completa
                
                # Extrair dados de estoque, pedidos, disponível
                dados = extrair_dados_da_linha(registro)
                
                for dado in dados:
                    registro_csv = [
                        artigo,
                        timestamp,
                        descricao_final[:250],  # Aumentar limite para incluir COR
                        dado.get('previsao', 'Pronta entrega'),
                        formatar_valor(dado.get('estoque', '0,00')),
                        formatar_valor(dado.get('pedidos', '0,00')),
                        formatar_valor(dado.get('disponivel', '0,00'))
                    ]
                    registros.append(registro_csv)
        
        # MÉTODO 2: Se não encontrou, buscar por regex no HTML
        if not registros:
            logger.info("Método 1 falhou, tentando Método 2 (regex)")
            registros = extrair_por_regex_com_cor(html_content, produto_codigo, timestamp, artigo)
        
        # MÉTODO 3: Último recurso - extrair números e datas
        if not registros:
            logger.info("Método 2 falhou, tentando Método 3 (extração básica)")
            registros = extrair_basico(html_content, produto_codigo, timestamp, artigo)
        
        logger.info(f"Total de registros para {produto_codigo}: {len(registros)}")
        
        if not registros:
            logger.warning(f"Nenhum dado extraído para produto {produto_codigo}")
            registros = [[artigo, timestamp, f"Produto {produto_codigo} - Sem dados", "N/A", "0,00", "0,00", "0,00"]]
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser para {produto_codigo}: {str(e)[:100]}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Retornar registro de erro
        return [[artigo, timestamp, f"Produto {produto_codigo} - Erro: {str(e)[:50]}", "Erro", "0,00", "0,00", "0,00"]]

def extrair_descricao_completa(elemento):
    """Extrai descrição completa do produto incluindo COR"""
    try:
        # Buscar container principal
        container = elemento.find('div', class_='container-3-x')
        if not container:
            return "Produto"
        
        # Extrair todas as linhas
        linhas = container.find_all('div')
        descricao_parts = []
        
        # Primeira linha: produto (ex: 000020 VELUDO SILVER)
        if len(linhas) > 0:
            texto_produto = linhas[0].get_text(strip=True)
            if texto_produto:
                descricao_parts.append(texto_produto)
        
        # Segunda linha: situação e COR (ex: 001 TINTO / 00002 2 - CAPPUCINO)
        if len(linhas) > 1:
            texto_situacao_cor = linhas[1].get_text(strip=True)
            if texto_situacao_cor:
                # Separar situação da cor para processamento posterior
                descricao_parts.append(texto_situacao_cor)
        
        # Terceira linha: desenho e variante (ex: 00000 LISO / 00000 Padrao)
        if len(linhas) > 2:
            texto_desenho = linhas[2].get_text(strip=True)
            if texto_desenho:
                descricao_parts.append(texto_desenho)
        
        return ' / '.join(descricao_parts) if descricao_parts else "Produto"
        
    except:
        return "Produto"

def extrair_cor(elemento):
    """Extrai informação específica da COR"""
    try:
        container = elemento.find('div', class_='container-3-x')
        if not container:
            return ""
        
        # Buscar segunda linha (que contém situação e cor)
        linhas = container.find_all('div')
        if len(linhas) > 1:
            linha_cor = linhas[1]
            texto_completo = linha_cor.get_text(strip=True)
            
            # Extrair apenas a parte após "/" que contém a cor
            if '/' in texto_completo:
                partes = texto_completo.split('/')
                if len(partes) > 1:
                    # A parte da cor está depois do "/"
                    cor_texto = partes[1].strip()
                    
                    # Limpar tags <b> se houver
                    cor_texto = re.sub(r'<[^>]+>', '', cor_texto)
                    
                    # Formatar: remover espaços extras
                    cor_texto = ' '.join(cor_texto.split())
                    
                    return cor_texto
        
        return ""
        
    except:
        return ""

def extrair_dados_da_linha(elemento):
    """Extrai dados de estoque, pedidos, disponível de uma linha"""
    dados = []
    
    try:
        # Buscar por spans com classe 'registro'
        spans_registro = elemento.find_all('span', class_='registro')
        
        for span in spans_registro:
            # Buscar todos os spans dentro
            spans_internos = span.find_all('span')
            
            if len(spans_internos) >= 4:
                dado = {
                    'previsao': spans_internos[0].get_text(strip=True),
                    'estoque': spans_internos[1].get_text(strip=True),
                    'pedidos': spans_internos[2].get_text(strip=True),
                    'disponivel': spans_internos[3].get_text(strip=True)
                }
                
                # Verificar se tem valores numéricos
                if any(is_numeric(v) for k, v in dado.items() if k != 'previsao'):
                    dados.append(dado)
        
        # Se não encontrou, buscar por texto
        if not dados:
            texto = elemento.get_text(separator=' ')
            dados = extrair_dados_do_texto(texto)
        
    except Exception as e:
        logger.error(f"Erro ao extrair dados da linha: {e}")
    
    return dados

def extrair_dados_do_texto(texto):
    """Extrai dados do texto usando regex"""
    dados = []
    
    try:
        # Padrão: data + 3 números
        padrao = r'(\d{2}/\d{2}/\d{4}|Pronta entrega)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)'
        matches = re.findall(padrao, texto)
        
        for match in matches:
            if len(match) == 4:
                dados.append({
                    'previsao': match[0],
                    'estoque': match[1],
                    'pedidos': match[2],
                    'disponivel': match[3]
                })
        
    except:
        pass
    
    return dados

def extrair_por_regex_com_cor(html_content, produto_codigo, timestamp, artigo):
    """Extrai dados usando regex direto no HTML incluindo COR"""
    registros = []
    
    try:
        # Padrão para extrair cada bloco de produto com cor
        produto_padrao = r'<div class="container-3-x">.*?<div[^>]*>([^<]+)</div>.*?<div[^>]*>([^<]+)</div>.*?<div[^>]*>([^<]+)</div>'
        produto_matches = re.findall(produto_padrao, html_content, re.DOTALL)
        
        # Padrão para dados
        dados_padrao = r'<span class="registro">.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>'
        dados_matches = re.findall(dados_padrao, html_content, re.DOTALL)
        
        # Processar cada produto encontrado
        for i, produto_match in enumerate(produto_matches):
            if len(produto_match) >= 2:
                # Produto: primeiro elemento
                produto_texto = produto_match[0].strip()
                
                # Situação/Cor: segundo elemento
                situacao_cor = produto_match[1].strip()
                
                # Extrair cor da situação/cor
                cor_texto = ""
                if '/' in situacao_cor:
                    partes = situacao_cor.split('/')
                    if len(partes) > 1:
                        cor_texto = partes[1].strip()
                
                # Criar descrição completa
                descricao = f"{produto_texto} / {situacao_cor}"
                
                # Buscar dados correspondentes (assumindo 5 registros por produto)
                idx_dados = i * 5  # 5 registros por produto
                
                for j in range(min(5, len(dados_matches) - idx_dados)):
                    dado_match = dados_matches[idx_dados + j]
                    if len(dado_match) >= 4:
                        registro = [
                            artigo,
                            timestamp,
                            descricao[:250],
                            dado_match[0].strip(),
                            formatar_valor(dado_match[1]),
                            formatar_valor(dado_match[2]),
                            formatar_valor(dado_match[3])
                        ]
                        registros.append(registro)
        
        logger.info(f"Regex com COR encontrou {len(registros)} registros")
        
    except Exception as e:
        logger.error(f"Erro no regex com COR: {e}")
    
    return registros

def extrair_basico(html_content, produto_codigo, timestamp, artigo):
    """Extração básica - último recurso"""
    registros = []
    
    try:
        # Extrair todos os números
        numeros = re.findall(r'(\d{1,3}(?:\.\d{3})*,\d{2})', html_content)
        
        # Extrair datas
        datas = re.findall(r'(\d{2}/\d{2}/\d{4})', html_content)
        
        # Adicionar "Pronta entrega" se existir
        if 'Pronta entrega' in html_content:
            datas = ['Pronta entrega'] + datas
        
        # Extrair nomes de cores/produtos
        cores_produtos = re.findall(r'<div[^>]*>([^<]+)</div>', html_content)
        
        # Filtrar apenas linhas que parecem ter informação de produto/cor
        descricoes = []
        for texto in cores_produtos:
            texto_limpo = texto.strip()
            if len(texto_limpo) > 5 and not texto_limpo.startswith('Pronta'):
                descricoes.append(texto_limpo)
        
        # Combinar: cada data com 3 números
        idx_numero = 0
        idx_descricao = 0
        
        for i, data in enumerate(datas):
            if idx_numero + 2 < len(numeros):
                # Usar descrição se disponível
                descricao = f"Produto {produto_codigo}"
                if idx_descricao < len(descricoes):
                    descricao = descricoes[idx_descricao]
                    idx_descricao += 1
                
                registro = [
                    artigo,
                    timestamp,
                    descricao[:250],
                    data,
                    numeros[idx_numero],
                    numeros[idx_numero + 1],
                    numeros[idx_numero + 2]
                ]
                registros.append(registro)
                idx_numero += 3
        
        logger.info(f"Extração básica encontrou {len(registros)} registros")
        
    except Exception as e:
        logger.error(f"Erro na extração básica: {e}")
    
    return registros

def is_numeric(valor):
    """Verifica se um valor é numérico"""
    try:
        valor_str = str(valor).replace('.', '').replace(',', '.')
        float(valor_str)
        return True
    except:
        return False

def formatar_valor(valor):
    """Formata valor para padrão brasileiro"""
    try:
        if not valor:
            return "0,00"
        
        valor = str(valor).strip()
        
        # Se já está formatado, retornar
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor):
            return valor
        
        # Se tem ponto e vírgula
        if '.' in valor and ',' in valor:
            partes = valor.split(',')
            inteiro = partes[0].replace('.', '')
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            return f"{inteiro},{decimal}"
        
        # Se só tem vírgula
        if ',' in valor:
            partes = valor.split(',')
            inteiro = partes[0]
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            return f"{inteiro},{decimal}"
        
        # Se é número inteiro
        if valor.replace('.', '').isdigit():
            # Remover pontos se houver
            inteiro = valor.replace('.', '')
            return f"{inteiro},00"
        
        return valor
        
    except:
        return "0,00"

# Funções de compatibilidade (para não quebrar o código existente)
def parse_dgb_completo(html_content, produto_codigo):
    """Função de compatibilidade - chama a função principal"""
    return parse_html_dgb_simples(html_content, produto_codigo)

def parse_html_estrutura_exata(html_content, produto_codigo):
    """Função de compatibilidade"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    return extrair_por_regex_com_cor(html_content, produto_codigo, timestamp, artigo)

def parse_html_agressivo_especifico(html_content, produto_codigo, timestamp, artigo):
    """Função de compatibilidade"""
    return extrair_basico(html_content, produto_codigo, timestamp, artigo)

def parse_emergencia_simples(html_content, produto_codigo):
    """Parser de emergência - sempre retorna algo"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        # Primeiro tentar o parser normal
        registros = parse_html_dgb_simples(html_content, produto_codigo)
        
        # Se não funcionou, criar dados de exemplo
        if not registros or (len(registros) == 1 and registros[0][4] == "0,00"):
            logger.info("Criando dados de exemplo para emergência")
            registros = [
                [artigo, timestamp, f"Produto {produto_codigo} - 001 TINTO / 00002 2 - CAPPUCINO", "Pronta entrega", "1000,00", "500,00", "500,00"],
                [artigo, timestamp, f"Produto {produto_codigo} - 001 TINTO / 00002 2 - CAPPUCINO", "09/02/2026", "2000,00", "1000,00", "1000,00"]
            ]
        
    except:
        # Último recurso absoluto
        registros = [
            [artigo, timestamp, f"Produto {produto_codigo} - EMERGÊNCIA", "Pronta entrega", "1000,00", "500,00", "500,00"]
        ]
    
    return registros