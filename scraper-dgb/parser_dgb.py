# parser_dgb.py - Parser otimizado para HTML do DGB
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser direto e eficiente para HTML do DGB"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Encontrar tabelas
        tabelas = soup.find_all('table')
        
        for tabela in tabelas:
            # Procurar por linhas que contenham o produto
            linhas = tabela.find_all('tr')
            
            for linha in linhas:
                texto_linha = linha.get_text().strip()
                
                # Verificar se contém o produto
                if produto_codigo in texto_linha or artigo in texto_linha:
                    logger.info(f"Encontrado produto {produto_codigo}: {texto_linha[:100]}...")
                    
                    # Extrair células da linha
                    celulas = linha.find_all(['td', 'th'])
                    textos_celulas = [cell.get_text().strip() for cell in celulas]
                    
                    # Tentar identificar padrões de dados
                    for i, texto in enumerate(textos_celulas):
                        # Verificar se é linha de dados (contém valores numéricos)
                        valores = re.findall(r'[\d.,]+', texto)
                        
                        if len(valores) >= 3:
                            # Extrair previsão (pode estar na célula anterior)
                            previsao = "Pronta entrega"
                            if i > 0:
                                texto_anterior = textos_celulas[i-1]
                                match_data = re.search(r'\d{2}/\d{2}/\d{4}', texto_anterior)
                                if match_data:
                                    previsao = match_data.group(0)
                            
                            # Criar registro
                            registro = [
                                artigo,
                                timestamp,
                                texto_linha,  # Descrição completa
                                previsao,
                                formatar_valor_csv(valores[0]),
                                formatar_valor_csv(valores[1]),
                                formatar_valor_csv(valores[2])
                            ]
                            registros.append(registro)
        
        # Se não encontrou nas tabelas, usar método alternativo
        if not registros:
            registros = parse_html_alternativo(html_content, produto_codigo, timestamp, artigo)
        
        logger.info(f"Extraídos {len(registros)} registros para produto {produto_codigo}")
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser: {e}")
        return []

def parse_html_alternativo(html_content, produto_codigo, timestamp, artigo):
    """Método alternativo de parsing"""
    registros = []
    
    try:
        # Extrair todo o texto
        soup = BeautifulSoup(html_content, 'html.parser')
        texto_completo = soup.get_text()
        
        # Procurar blocos com o produto
        linhas = texto_completo.split('\n')
        
        for i, linha in enumerate(linhas):
            linha = linha.strip()
            
            if produto_codigo in linha or artigo in linha:
                # Procurar por dados nas próximas linhas
                for j in range(i, min(i + 10, len(linhas))):
                    linha_dados = linhas[j].strip()
                    
                    # Verificar se tem valores numéricos
                    valores = re.findall(r'[\d.,]+', linha_dados)
                    
                    if len(valores) >= 3:
                        # Extrair previsão
                        previsao = "Pronta entrega"
                        for k in range(max(0, j-2), j):
                            match_data = re.search(r'\d{2}/\d{2}/\d{4}', linhas[k])
                            if match_data:
                                previsao = match_data.group(0)
                                break
                        
                        registro = [
                            artigo,
                            timestamp,
                            linha,  # Descrição
                            previsao,
                            formatar_valor_csv(valores[0]),
                            formatar_valor_csv(valores[1]),
                            formatar_valor_csv(valores[2])
                        ]
                        registros.append(registro)
                        break
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser alternativo: {e}")
        return []

def formatar_valor_csv(valor_str):
    """Formata valor para CSV no padrão brasileiro"""
    try:
        valor_str = str(valor_str).strip().replace(' ', '')
        
        if not valor_str:
            return "0,00"
        
        if ',' in valor_str:
            partes = valor_str.split(',')
            inteiro = partes[0].replace('.', '')
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            decimal = decimal.ljust(2, '0')
            return f"{inteiro},{decimal}"
        else:
            valor_str = valor_str.replace('.', '')
            return f"{valor_str},00"
            
    except:
        return "0,00"