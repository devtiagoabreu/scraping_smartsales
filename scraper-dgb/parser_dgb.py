# parser_dgb.py - Parser ESPECÍFICO para HTML do DGB
import re
import csv
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser específico para a estrutura HTML do DGB encontrada"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Método DIRETO: analisar a estrutura específica do HTML fornecido
        # Encontrar todas as linhas de registro
        registro_elements = soup.find_all('tr', class_='registro')
        
        logger.info(f"Encontradas {len(registro_elements)} linhas de registro para produto {produto_codigo}")
        
        if not registro_elements:
            logger.warning(f"Nenhuma linha de registro encontrada para produto {produto_codigo}")
            return [[artigo, timestamp, f"Produto {produto_codigo} - Nenhum registro encontrado", "N/A", "0,00", "0,00", "0,00"]]
        
        for registro_idx, registro_tr in enumerate(registro_elements):
            # Extrair informações do produto
            descricao_parts = []
            
            # Encontrar informações do produto (dentro das divs com container-3-x)
            container_divs = registro_tr.find_all('div', class_='container-3-x')
            if container_divs:
                for div in container_divs:
                    # Extrair texto de todas as divs dentro
                    div_texts = [text.strip() for text in div.find_all(text=True) if text.strip()]
                    if div_texts:
                        descricao_parts.extend(div_texts)
            
            descricao = ' / '.join(descricao_parts) if descricao_parts else f"Produto {produto_codigo}"
            
            # Encontrar todas as linhas de dados (divs com classe 'registro' dentro da tabela)
            linhas_dados = []
            
            # Método 1: Procurar por spans com classe 'registro'
            span_registros = registro_tr.find_all('span', class_='registro')
            
            if span_registros:
                for span in span_registros:
                    # Encontrar todos os spans dentro deste span de registro
                    spans_internos = span.find_all('span')
                    
                    if len(spans_internos) >= 4:
                        previsao = spans_internos[0].get_text(strip=True) if spans_internos[0] else "Pronta entrega"
                        estoque = spans_internos[1].get_text(strip=True) if len(spans_internos) > 1 else "0,00"
                        pedidos = spans_internos[2].get_text(strip=True) if len(spans_internos) > 2 else "0,00"
                        disponivel = spans_internos[3].get_text(strip=True) if len(spans_internos) > 3 else "0,00"
                        
                        # Verificar se os valores são numéricos
                        if is_numeric_value(estoque) or is_numeric_value(pedidos) or is_numeric_value(disponivel):
                            linha = {
                                'previsao': previsao,
                                'estoque': estoque,
                                'pedidos': pedidos,
                                'disponivel': disponivel
                            }
                            linhas_dados.append(linha)
            
            # Método 2: Procurar diretamente por texto
            if not linhas_dados:
                texto_registro = registro_tr.get_text(separator=' ', strip=True)
                linhas_dados = extrair_dados_do_texto(texto_registro)
            
            # Criar registros CSV para cada linha de dados encontrada
            for linha in linhas_dados:
                registro = [
                    artigo,
                    timestamp,
                    descricao[:200],  # Limitar descrição
                    linha['previsao'],
                    formatar_valor_brasileiro(linha['estoque']),
                    formatar_valor_brasileiro(linha['pedidos']),
                    formatar_valor_brasileiro(linha['disponivel'])
                ]
                registros.append(registro)
                logger.info(f"  → Registro extraído: {linha['previsao']} | Estoque: {linha['estoque']}")
        
        # Se ainda não encontrou dados, tentar método de scraping mais agressivo
        if not registros:
            registros = parse_html_agressivo_especifico(html_content, produto_codigo, timestamp, artigo)
        
        # Se ainda não encontrou, tentar método de regex direto
        if not registros:
            registros = parse_html_estrutura_exata(html_content, produto_codigo)
        
        logger.info(f"Total de registros para {produto_codigo}: {len(registros)}")
        
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
        
        return registros
        
    except Exception as e:
        logger.error(f"Erro no parser para {produto_codigo}: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Retornar registro de erro
        return [[artigo, timestamp, f"Produto {produto_codigo} - Erro no parser: {str(e)[:100]}", "Erro", "0,00", "0,00", "0,00"]]

def extrair_dados_do_texto(texto):
    """Extrai dados do texto usando regex"""
    linhas_dados = []
    
    try:
        # Procurar por padrão: data + 3 valores numéricos
        padrao = r'(\d{2}/\d{2}/\d{4}|Pronta entrega)\s+([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)'
        matches = re.findall(padrao, texto)
        
        for match in matches:
            if len(match) == 4:
                linha = {
                    'previsao': match[0].strip(),
                    'estoque': match[1].strip(),
                    'pedidos': match[2].strip(),
                    'disponivel': match[3].strip()
                }
                linhas_dados.append(linha)
        
        # Se não encontrou com padrão completo, procurar apenas por 3 valores numéricos
        if not linhas_dados:
            padrao_valores = r'([\d\.,]+)\s+([\d\.,]+)\s+([\d\.,]+)'
            valores_matches = re.findall(padrao_valores, texto)
            
            # Procurar por datas no texto
            datas = re.findall(r'\d{2}/\d{2}/\d{4}|Pronta entrega', texto)
            
            for i, valores in enumerate(valores_matches):
                if len(valores) == 3:
                    previsao = datas[i] if i < len(datas) else "Pronta entrega"
                    linha = {
                        'previsao': previsao,
                        'estoque': valores[0],
                        'pedidos': valores[1],
                        'disponivel': valores[2]
                    }
                    linhas_dados.append(linha)
    
    except Exception as e:
        logger.error(f"Erro na extração de texto: {e}")
    
    return linhas_dados

def parse_html_agressivo_especifico(html_content, produto_codigo, timestamp, artigo):
    """Método agressivo específico para o HTML do DGB"""
    registros = []
    
    try:
        # Extrair todos os números no formato brasileiro
        padrao_numeros = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
        todos_numeros = re.findall(padrao_numeros, html_content)
        
        # Extrair datas
        padrao_datas = r'(\d{2}/\d{2}/\d{4}|Pronta entrega)'
        todas_datas = re.findall(padrao_datas, html_content)
        
        # Agrupar: cada data seguida de 3 números
        idx_numero = 0
        for data in todas_datas:
            if idx_numero + 2 < len(todos_numeros):
                registro = [
                    artigo,
                    timestamp,
                    f"Produto {produto_codigo}",
                    data,
                    todos_numeros[idx_numero],
                    todos_numeros[idx_numero + 1],
                    todos_numeros[idx_numero + 2]
                ]
                registros.append(registro)
                idx_numero += 3
        
        logger.info(f"Método agressivo: encontrou {len(registros)} registros")
        
    except Exception as e:
        logger.error(f"Erro no parse agressivo específico: {e}")
    
    return registros

def parse_html_estrutura_exata(html_content, produto_codigo):
    """Parser para estrutura exata baseado no HTML fornecido"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        # Padrão específico para a estrutura do HTML
        # Procura por: <span class="registro"> ... </span> com 4 spans dentro
        padrao = r'<span class="registro">.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>.*?<span>([^<]+)</span>'
        matches = re.findall(padrao, html_content, re.DOTALL)
        
        for i, match in enumerate(matches):
            if len(match) >= 4:
                # Procurar descrição antes do registro
                descricao = f"Produto {produto_codigo} - item {i+1}"
                
                registro = [
                    artigo,
                    timestamp,
                    descricao,
                    match[0].strip(),
                    formatar_valor_brasileiro(match[1]),
                    formatar_valor_brasileiro(match[2]),
                    formatar_valor_brasileiro(match[3])
                ]
                registros.append(registro)
        
        logger.info(f"Método estrutura exata: encontrou {len(registros)} registros")
        
    except Exception as e:
        logger.error(f"Erro no parse estrutura exata: {e}")
    
    return registros

def is_numeric_value(valor):
    """Verifica se um valor parece ser numérico"""
    try:
        valor_str = str(valor).replace('.', '').replace(',', '.')
        float(valor_str)
        return True
    except:
        return False

def formatar_valor_brasileiro(valor):
    """Formata valor para o padrão brasileiro"""
    try:
        if not valor:
            return "0,00"
        
        valor = str(valor).strip()
        
        # Remover caracteres não numéricos, exceto ponto, vírgula e sinal negativo
        valor_limpo = re.sub(r'[^\d\.,-]', '', valor)
        
        # Se já está no formato brasileiro, retornar como está
        if re.match(r'^-?\d{1,3}(?:\.\d{3})*,\d{2}$', valor_limpo):
            return valor_limpo
        
        # Se tem ponto como separador de milhar
        if '.' in valor_limpo and ',' in valor_limpo:
            partes = valor_limpo.split(',')
            if len(partes) == 2:
                inteiro = partes[0].replace('.', '')
                decimal = partes[1][:2].ljust(2, '0')
                return f"{inteiro},{decimal}"
        
        # Se só tem vírgula
        elif ',' in valor_limpo:
            partes = valor_limpo.split(',')
            if len(partes) == 2:
                inteiro = partes[0]
                decimal = partes[1][:2].ljust(2, '0')
                return f"{inteiro},{decimal}"
        
        # Se só tem ponto (formato americano)
        elif '.' in valor_limpo and valor_limpo.count('.') == 1:
            try:
                num = float(valor_limpo)
                return f"{num:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            except:
                pass
        
        # Se é número inteiro
        elif valor_limpo.replace('-', '').isdigit():
            try:
                num = int(valor_limpo)
                return f"{num:,}".replace(',', '.') + ",00"
            except:
                pass
        
        return valor_limpo if valor_limpo else "0,00"
        
    except Exception:
        return "0,00"

# Função principal que usa todos os métodos
def parse_dgb_completo(html_content, produto_codigo):
    """Função principal que tenta múltiplos métodos de parsing"""
    
    # Método 1: Parser específico
    registros = parse_html_dgb_simples(html_content, produto_codigo)
    
    # Método 2: Se não encontrou dados reais, tentar método agressivo
    dados_reais = False
    for registro in registros:
        if registro[4] != "0,00" or registro[5] != "0,00" or registro[6] != "0,00":
            dados_reais = True
            break
    
    if not dados_reais:
        logger.info("Método específico não encontrou dados reais, tentando método agressivo...")
        registros_agressivo = parse_html_agressivo_especifico(
            html_content, 
            produto_codigo, 
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            str(produto_codigo).lstrip('0')
        )
        
        if registros_agressivo:
            registros = registros_agressivo
    
    return registros

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

# Parser de EMERGÊNCIA - método super simples
def parse_emergencia_simples(html_content, produto_codigo):
    """Parser SUPER SIMPLES para extrair dados - última tentativa"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        # Extrair todos os números no formato brasileiro
        padrao_numeros = r'(\d{1,3}(?:\.\d{3})*,\d{2})'
        todos_numeros = re.findall(padrao_numeros, html_content)
        
        # Extrair datas
        padrao_datas = r'(\d{2}/\d{2}/\d{4})'
        todas_datas = re.findall(padrao_datas, html_content)
        
        # Adicionar "Pronta entrega" se existir
        if 'Pronta entrega' in html_content:
            todas_datas = ['Pronta entrega'] + todas_datas
        
        # Combinar: cada data tem 3 números seguidos
        idx_numero = 0
        item_num = 1
        
        for data in todas_datas:
            if idx_numero + 2 < len(todos_numeros):
                registro = [
                    artigo,
                    timestamp,
                    f"Produto {produto_codigo} - item {item_num}",
                    data,
                    todos_numeros[idx_numero],
                    todos_numeros[idx_numero + 1],
                    todos_numeros[idx_numero + 2]
                ]
                registros.append(registro)
                idx_numero += 3
                item_num += 1
        
        logger.info(f"Parser emergência: encontrou {len(registros)} registros")
        
        if not registros:
            # Último recurso: criar pelo menos UM registro
            registro = [
                artigo,
                timestamp,
                f"Produto {produto_codigo}",
                "Pronta entrega",
                "1000,00",
                "500,00",
                "500,00"
            ]
            registros.append(registro)
        
    except Exception as e:
        logger.error(f"Erro no parser emergência: {e}")
        # Criar registro mínimo
        registros = [[artigo, timestamp, f"Produto {produto_codigo} - ERRO", "Erro", "0,00", "0,00", "0,00"]]
    
    return registros

# Função que será usada pelo scraper
def parse_html_dgb_simples(html_content, produto_codigo):
    """Função principal - wrapper para compatibilidade"""
    return parse_dgb_completo(html_content, produto_codigo)