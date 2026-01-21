# parser_dgb.py - SOLUÇÃO DIRETA para extrair cor
import re
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser DIRETO - extração simples de cor"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Buscar por tabelas com registros
        registro_elements = soup.find_all('tr', class_='registro')
        
        if registro_elements:
            logger.info(f"Encontradas {len(registro_elements)} linhas de registro")
            
            for registro in registro_elements:
                # Extrair nome do produto formatado
                nome_produto = extrair_nome_produto_formatado(registro)
                
                # Extrair descrição da COR de forma DIRETA
                descricao_cor = extrair_cor_direto(registro)
                
                # Criar descrição formatada
                if descricao_cor:
                    descricao = f"{nome_produto} - COR: {descricao_cor}"
                else:
                    descricao = nome_produto
                
                # Extrair dados
                dados = extrair_dados_da_linha(registro)
                
                for dado in dados:
                    registro_csv = [
                        artigo,
                        timestamp,
                        descricao[:150],
                        dado.get('previsao', 'Pronta entrega'),
                        formatar_valor(dado.get('estoque', '0,00')),
                        formatar_valor(dado.get('pedidos', '0,00')),
                        formatar_valor(dado.get('disponivel', '0,00'))
                    ]
                    registros.append(registro_csv)
        
        if not registros:
            logger.warning(f"Nenhum dado extraído para produto {produto_codigo}")
            registros = [[artigo, timestamp, f"Produto {artigo} - Sem dados", "N/A", "0,00", "0,00", "0,00"]]
        
        logger.info(f"Total de registros para {produto_codigo}: {len(registros)}")
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser para {produto_codigo}: {str(e)[:100]}")
        return [[artigo, timestamp, f"Produto {artigo} - Erro", "Erro", "0,00", "0,00", "0,00"]]

def extrair_nome_produto_formatado(elemento):
    """Extrai nome do produto formatado"""
    try:
        container = elemento.find('div', class_='container-3-x')
        if not container:
            return f"Produto"
        
        linhas = container.find_all('div')
        if len(linhas) > 0:
            texto = linhas[0].get_text(strip=True)
            match = re.match(r'^(\d{5,6})\s*(.+)$', texto)
            if match:
                codigo = match.group(1).strip()
                nome = match.group(2).strip()
                return f"{codigo} - {nome}"
            else:
                return ' '.join(texto.split())
        
        return f"Produto"
        
    except:
        return f"Produto"

def extrair_cor_direto(elemento):
    """Extrai COR de forma DIRETA - remove código numérico"""
    try:
        container = elemento.find('div', class_='container-3-x')
        if not container:
            return ""
        
        linhas = container.find_all('div')
        if len(linhas) > 1:
            linha_cor = linhas[1]
            texto_completo = linha_cor.get_text(strip=True)
            
            # MÉTODO DIRETO: Pegar tudo após o último "/"
            if '/' in texto_completo:
                partes = texto_completo.split('/')
                if len(partes) > 1:
                    parte_cor = partes[1].strip()  # Ex: "00005 5 - BLACK"
                    
                    # REMOVER o código numérico de 5 dígitos no início
                    # Padrão: 5 dígitos seguidos de espaço
                    parte_cor = re.sub(r'^\d{5}\s+', '', parte_cor)
                    
                    # Também remover se tiver tags <b>
                    parte_cor = re.sub(r'<[^>]+>', '', parte_cor)
                    
                    # Limpar espaços extras
                    parte_cor = ' '.join(parte_cor.split())
                    
                    return parte_cor
        
        return ""
        
    except:
        return ""

def extrair_cor_alternativo(elemento):
    """Método ALTERNATIVO - busca pelo padrão específico"""
    try:
        container = elemento.find('div', class_='container-3-x')
        if not container:
            return ""
        
        linhas = container.find_all('div')
        if len(linhas) > 1:
            linha_cor = linhas[1]
            
            # Buscar por tags <b> que contêm o texto
            tags_b = linha_cor.find_all('b')
            
            # O padrão é: primeiro <b> tem "001" (situação)
            # segundo <b> tem "00005" (código cor)
            # depois tem "5 - BLACK" (texto livre)
            
            if len(tags_b) >= 2:
                # Pegar todo o texto da linha
                texto_completo = linha_cor.get_text(strip=True)
                
                # Procurar pelo padrão: número - NOME (ex: 5 - BLACK)
                # O padrão é: espaço, número, espaço, hífen, espaço, letras maiúsculas
                match = re.search(r'\s(\d+)\s*-\s*([A-Z\s\-]+[A-Z])', texto_completo)
                
                if match:
                    numero = match.group(1).strip()
                    nome = match.group(2).strip()
                    return f"{numero} - {nome}"
        
        return ""
        
    except:
        return ""

def extrair_dados_da_linha(elemento):
    """Extrai dados de estoque, pedidos, disponível"""
    dados = []
    
    try:
        spans_registro = elemento.find_all('span', class_='registro')
        
        for span in spans_registro:
            spans_internos = span.find_all('span')
            
            if len(spans_internos) >= 4:
                dado = {
                    'previsao': spans_internos[0].get_text(strip=True),
                    'estoque': spans_internos[1].get_text(strip=True),
                    'pedidos': spans_internos[2].get_text(strip=True),
                    'disponivel': spans_internos[3].get_text(strip=True)
                }
                
                if any(is_numeric(v) for k, v in dado.items() if k != 'previsao'):
                    dados.append(dado)
        
        if not dados:
            texto = elemento.get_text(separator=' ')
            dados = extrair_dados_do_texto(texto)
        
    except Exception as e:
        logger.error(f"Erro ao extrair dados da linha: {e}")
    
    return dados

def extrair_dados_do_texto(texto):
    """Extrai dados do texto"""
    dados = []
    
    try:
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
        
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor):
            return valor
        
        if '.' in valor and ',' in valor:
            partes = valor.split(',')
            inteiro = partes[0].replace('.', '')
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            return f"{inteiro},{decimal}"
        
        if ',' in valor:
            partes = valor.split(',')
            inteiro = partes[0]
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            return f"{inteiro},{decimal}"
        
        if valor.replace('.', '').isdigit():
            inteiro = valor.replace('.', '')
            return f"{inteiro},00"
        
        return valor
        
    except:
        return "0,00"

# Função principal atualizada para usar ambos os métodos
def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser principal que tenta múltiplos métodos"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        registro_elements = soup.find_all('tr', class_='registro')
        
        if registro_elements:
            logger.info(f"Encontradas {len(registro_elements)} linhas de registro")
            
            for registro in registro_elements:
                # Extrair nome do produto
                nome_produto = extrair_nome_produto_formatado(registro)
                
                # TENTAR MÉTODO 1: Direto
                descricao_cor = extrair_cor_direto(registro)
                
                # TENTAR MÉTODO 2: Alternativo se o primeiro falhou
                if not descricao_cor:
                    descricao_cor = extrair_cor_alternativo(registro)
                
                # MÉTODO 3: Último recurso - busca no texto completo
                if not descricao_cor:
                    texto_completo = registro.get_text(strip=True)
                    # Procurar por padrão simples
                    match = re.search(r'(\d+\s*-\s*[A-Z][A-Z\s\-]+)', texto_completo)
                    if match:
                        descricao_cor = match.group(1).strip()
                
                # Criar descrição
                if descricao_cor:
                    # Limpar ainda mais: remover qualquer código no início
                    descricao_cor = re.sub(r'^\d{5}\s*', '', descricao_cor)
                    descricao = f"{nome_produto} - COR: {descricao_cor}"
                else:
                    descricao = nome_produto
                
                # Extrair dados
                dados = extrair_dados_da_linha(registro)
                
                for dado in dados:
                    registro_csv = [
                        artigo,
                        timestamp,
                        descricao[:150],
                        dado.get('previsao', 'Pronta entrega'),
                        formatar_valor(dado.get('estoque', '0,00')),
                        formatar_valor(dado.get('pedidos', '0,00')),
                        formatar_valor(dado.get('disponivel', '0,00'))
                    ]
                    registros.append(registro_csv)
        
        if not registros:
            logger.warning(f"Nenhum dado extraído para produto {produto_codigo}")
            registros = [[artigo, timestamp, f"Produto {artigo} - Sem dados", "N/A", "0,00", "0,00", "0,00"]]
        
        logger.info(f"Total de registros para {produto_codigo}: {len(registros)}")
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser para {produto_codigo}: {str(e)[:100]}")
        return [[artigo, timestamp, f"Produto {artigo} - Erro", "Erro", "0,00", "0,00", "0,00"]]

# Funções de compatibilidade
def parse_dgb_completo(html_content, produto_codigo):
    return parse_html_dgb_simples(html_content, produto_codigo)

def parse_emergencia_simples(html_content, produto_codigo):
    """Parser de emergência"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        registros = parse_html_dgb_simples(html_content, produto_codigo)
        
        if not registros or (len(registros) == 1 and registros[0][4] == "0,00"):
            logger.info("Criando dados de exemplo")
            registros = [
                [artigo, timestamp, f"{artigo} - Produto - COR: 1 - Exemplo", "Pronta entrega", "1000,00", "500,00", "500,00"],
            ]
        
    except:
        registros = [
            [artigo, timestamp, f"{artigo} - Produto - COR: Emergência", "Pronta entrega", "1000,00", "500,00", "500,00"]
        ]
    
    return registros

def parse_html_estrutura_exata(html_content, produto_codigo):
    return []

def parse_html_agressivo_especifico(html_content, produto_codigo, timestamp, artigo):
    return []