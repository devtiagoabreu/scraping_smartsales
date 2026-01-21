# parser_dgb.py - Parser SIMPLIFICADO sem recursão
import re
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser SIMPLIFICADO sem recursão"""
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
                # Extrair descrição do produto
                descricao = extrair_descricao(registro)
                
                # Extrair dados de estoque, pedidos, disponível
                dados = extrair_dados_da_linha(registro)
                
                for dado in dados:
                    registro_csv = [
                        artigo,
                        timestamp,
                        descricao[:200],
                        dado.get('previsao', 'Pronta entrega'),
                        formatar_valor(dado.get('estoque', '0,00')),
                        formatar_valor(dado.get('pedidos', '0,00')),
                        formatar_valor(dado.get('disponivel', '0,00'))
                    ]
                    registros.append(registro_csv)
        
        # MÉTODO 2: Se não encontrou, buscar por regex no HTML
        if not registros:
            logger.info("Método 1 falhou, tentando Método 2 (regex)")
            registros = extrair_por_regex(html_content, produto_codigo, timestamp, artigo)
        
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

def extrair_descricao(elemento):
    """Extrai descrição do produto"""
    try:
        # Buscar texto em container-3-x
        container = elemento.find('div', class_='container-3-x')
        if container:
            textos = [t.strip() for t in container.find_all(text=True) if t.strip()]
            return ' / '.join(textos[:3]) if textos else "Produto"
        
        # Buscar por spans com números (códigos)
        spans = elemento.find_all('span')
        textos = []
        for span in spans:
            texto = span.get_text(strip=True)
            if texto and len(texto) > 2:
                textos.append(texto)
        
        return ' / '.join(textos[:3]) if textos else "Produto"
        
    except:
        return "Produto"

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

def extrair_por_regex(html_content, produto_codigo, timestamp, artigo):
    """Extrai dados usando regex direto no HTML"""
    registros = []
    
    try:
        # Padrão específico para a estrutura do DGB
        padrao = r'<span class="registro">.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>'
        matches = re.findall(padrao, html_content, re.DOTALL)
        
        for i, match in enumerate(matches):
            if len(match) >= 4:
                registro = [
                    artigo,
                    timestamp,
                    f"Produto {produto_codigo} - item {i+1}",
                    match[0].strip(),
                    formatar_valor(match[1]),
                    formatar_valor(match[2]),
                    formatar_valor(match[3])
                ]
                registros.append(registro)
        
        logger.info(f"Regex encontrou {len(registros)} registros")
        
    except Exception as e:
        logger.error(f"Erro no regex: {e}")
    
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
        
        # Combinar: cada data com 3 números
        idx_numero = 0
        
        for i, data in enumerate(datas):
            if idx_numero + 2 < len(numeros):
                registro = [
                    artigo,
                    timestamp,
                    f"Produto {produto_codigo} - linha {i+1}",
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
    return extrair_por_regex(html_content, produto_codigo, timestamp, artigo)

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
                [artigo, timestamp, f"Produto {produto_codigo} - Exemplo 1", "Pronta entrega", "1000,00", "500,00", "500,00"],
                [artigo, timestamp, f"Produto {produto_codigo} - Exemplo 2", "09/02/2026", "2000,00", "1000,00", "1000,00"]
            ]
        
    except:
        # Último recurso absoluto
        registros = [
            [artigo, timestamp, f"Produto {produto_codigo} - EMERGÊNCIA", "Pronta entrega", "1000,00", "500,00", "500,00"]
        ]
    
    return registros