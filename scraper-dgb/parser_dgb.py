# parser_dgb.py - Parser melhorado para HTML do DGB
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
        
        # Remover scripts e styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        
        # Encontrar todas as tabelas
        tabelas = soup.find_all('table')
        
        for tabela_idx, tabela in enumerate(tabelas):
            linhas = tabela.find_all('tr')
            
            for linha_idx, linha in enumerate(linhas):
                # Obter texto da linha
                texto_linha = linha.get_text(separator=' ', strip=True)
                
                # Verificar se esta linha contém o produto
                if (produto_codigo in texto_linha or 
                    artigo in texto_linha or 
                    f" {produto_codigo} " in texto_linha):
                    
                    logger.info(f"Produto {produto_codigo} encontrado na tabela {tabela_idx+1}, linha {linha_idx+1}")
                    
                    # Procurar por dados nas próximas linhas (máximo 5 linhas)
                    for j in range(linha_idx, min(linha_idx + 5, len(linhas))):
                        linha_dados = linhas[j]
                        texto_dados = linha_dados.get_text(separator=' ', strip=True)
                        
                        # Procurar por padrão de dados: 3 valores numéricos
                        padrao = r'(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})\s+(\d{1,3}(?:\.\d{3})*,\d{2})'
                        match = re.search(padrao, texto_dados)
                        
                        if match:
                            # Encontrar previsão
                            previsao = "Pronta entrega"
                            
                            # Verificar se há data na linha anterior
                            for k in range(max(0, j-2), j):
                                linha_anterior = linhas[k].get_text(separator=' ', strip=True)
                                match_data = re.search(r'\b\d{2}/\d{2}/\d{4}\b', linha_anterior)
                                if match_data:
                                    previsao = match_data.group(0)
                                    break
                            
                            # Criar registro
                            registro = [
                                artigo,
                                timestamp,
                                texto_linha[:200],  # Limitar descrição
                                previsao,
                                match.group(1),  # Estoque
                                match.group(2),  # Pedidos
                                match.group(3)   # Disponível
                            ]
                            registros.append(registro)
                            logger.info(f"  → Registro extraído: {previsao} | {match.group(1)}, {match.group(2)}, {match.group(3)}")
        
        # Se ainda não encontrou, usar método de busca por texto
        if not registros:
            registros = parse_por_texto_completo(html_content, produto_codigo, timestamp, artigo)
        
        logger.info(f"Total de registros para {produto_codigo}: {len(registros)}")
        
        # Se ainda não encontrou, criar um registro vazio para manter o produto na lista
        if not registros:
            logger.warning(f"Nenhum dado extraído para produto {produto_codigo}")
            # Criar um registro vazio para manter consistência
            registro = [
                artigo,
                timestamp,
                f"Produto {produto_codigo} - Nenhum dado extraído",
                "N/A",
                "0,00",
                "0,00",
                "0,00"
            ]
            registros.append(registro)
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser para {produto_codigo}: {e}")
        # Retornar registro vazio em caso de erro
        return [[artigo, timestamp, f"Produto {produto_codigo} - Erro no parser", "Erro", "0,00", "0,00", "0,00"]]

def parse_por_texto_completo(html_content, produto_codigo, timestamp, artigo):
    """Método alternativo: busca por texto completo"""
    registros = []
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        texto_completo = soup.get_text(separator='\n')
        linhas = texto_completo.split('\n')
        
        for i, linha in enumerate(linhas):
            linha = linha.strip()
            
            # Verificar se linha contém o produto
            if (produto_codigo in linha or 
                f" {produto_codigo} " in linha or
                (len(produto_codigo) >= 2 and produto_codigo in linha.replace(' ', ''))):
                
                # Procurar por dados nas próximas 10 linhas
                for j in range(i, min(i + 10, len(linhas))):
                    linha_atual = linhas[j].strip()
                    
                    # Procurar por padrão de 3 números com vírgula
                    padrao = r'(\d[\d\.,]+\d)\s+(\d[\d\.,]+\d)\s+(\d[\d\.,]+\d)'
                    match = re.search(padrao, linha_atual)
                    
                    if match:
                        # Extrair previsão
                        previsao = "Pronta entrega"
                        
                        # Verificar linhas anteriores para data
                        for k in range(max(0, j-3), j):
                            if re.search(r'\d{2}/\d{2}/\d{4}', linhas[k]):
                                previsao = re.search(r'\d{2}/\d{2}/\d{4}', linhas[k]).group(0)
                                break
                        
                        # Formatar valores
                        estoque = formatar_valor_csv(match.group(1))
                        pedidos = formatar_valor_csv(match.group(2))
                        disponivel = formatar_valor_csv(match.group(3))
                        
                        registro = [
                            artigo,
                            timestamp,
                            linha[:200],  # Descrição limitada
                            previsao,
                            estoque,
                            pedidos,
                            disponivel
                        ]
                        registros.append(registro)
                        
                        # Parar de procurar mais dados para este produto
                        break
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parse por texto: {e}")
        return []

def formatar_valor_csv(valor_str):
    """Formata valor para CSV no padrão brasileiro"""
    try:
        # Remover espaços
        valor_str = str(valor_str).strip().replace(' ', '')
        
        if not valor_str:
            return "0,00"
        
        # Verificar se já está no formato correto
        if re.match(r'^\d{1,3}(?:\.\d{3})*,\d{2}$', valor_str):
            return valor_str
        
        # Se tem ponto como separador de milhar e vírgula como decimal
        if '.' in valor_str and ',' in valor_str:
            partes = valor_str.split(',')
            inteiro = partes[0].replace('.', '')
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            decimal = decimal.ljust(2, '0')
            return f"{inteiro},{decimal}"
        
        # Se só tem vírgula
        elif ',' in valor_str:
            partes = valor_str.split(',')
            inteiro = partes[0]
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            decimal = decimal.ljust(2, '0')
            return f"{inteiro},{decimal}"
        
        # Se só tem ponto (provavelmente decimal americano)
        elif '.' in valor_str and valor_str.count('.') == 1:
            partes = valor_str.split('.')
            inteiro = partes[0]
            decimal = partes[1][:2] if len(partes) > 1 else '00'
            decimal = decimal.ljust(2, '0')
            return f"{inteiro},{decimal}"
        
        # Número inteiro
        else:
            return f"{valor_str},00"
            
    except:
        return "0,00"

def criar_csv_direto(produto_codigo, registros):
    """Cria CSV diretamente dos registros"""
    try:
        if not registros:
            return None
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"produto_{produto_codigo}_{timestamp}.csv"
        
        import os
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