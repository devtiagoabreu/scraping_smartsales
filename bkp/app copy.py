# app.py - SCRAPER COM DEBUG E CSV DIRETO DO HTML
import os
import csv
import json
import time
import threading
import logging
import re
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import pandas as pd
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import sys

# Configurar stdout para UTF-8
sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

sys.path.append('.')

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurações do sistema
UPLOAD_FOLDER = 'data'
CSV_FOLDER = 'data/csv'
PDF_FOLDER = 'data/pdf'
LOG_FOLDER = 'data/logs'
SCREENSHOT_FOLDER = 'data/screenshots'
CONSOLIDATED_FOLDER = 'data/consolidated'
DEBUG_FOLDER = 'data/debug'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(CONSOLIDATED_FOLDER, exist_ok=True)
os.makedirs(DEBUG_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dgb-comex-scraper-secret-2024')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_FOLDER, 'scraper.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DGBScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.driver = None
        self.wait = None
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.usuario = os.getenv('DGB_USUARIO')
        self.senha = os.getenv('DGB_SENHA')
        self.url_login = os.getenv('DGB_URL_LOGIN')
        self.url_estoque = os.getenv('DGB_URL_ESTOQUE')
        self.setup_driver()
        
    def setup_driver(self):
        """Configura o driver do Chrome"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 30)
        
    def take_screenshot(self, name):
        """Tira screenshot para debugging"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.session_id}_{name}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_FOLDER, filename)
            self.driver.save_screenshot(filepath)
            logger.info(f"Screenshot salvo: {filename}")
            return filepath
        except Exception as e:
            logger.error(f"Erro ao tirar screenshot: {str(e)}")
            return None
    
    def login(self):
        """Efetua login no sistema DGB"""
        try:
            logger.info(f"Acessando página de login: {self.url_login}")
            
            self.driver.get(self.url_login)
            time.sleep(3)
            
            self.take_screenshot("login_page")
            
            # Localizar e preencher campos de login
            try:
                login_field = self.driver.find_element(By.ID, "login")
            except NoSuchElementException:
                login_field = self.driver.find_element(By.NAME, "login")
            
            login_field.clear()
            login_field.send_keys(self.usuario)
            
            try:
                senha_field = self.driver.find_element(By.ID, "senha")
            except NoSuchElementException:
                senha_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            
            senha_field.clear()
            senha_field.send_keys(self.senha)
            
            # Clicar no botão de login
            try:
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except NoSuchElementException:
                login_button = self.driver.find_element(By.ID, "botaoEntrar")
            
            login_button.click()
            
            time.sleep(5)
            
            # Navegar para a página de estoque
            return self.navigate_to_stock_page()
                
        except Exception as e:
            logger.error(f"Erro durante login: {str(e)}")
            self.take_screenshot("erro_login")
            return False
    
    def navigate_to_stock_page(self):
        """Navega para a página de estoque"""
        try:
            # Ir diretamente para a URL de estoque
            self.driver.get(self.url_estoque)
            time.sleep(5)
            
            # Verificar se carregou corretamente
            current_url = self.driver.current_url
            if "estoquePrevisaoConsulta" in current_url:
                logger.info("Página de estoque carregada com sucesso!")
                return True
            else:
                # Tentar encontrar campo de produto
                try:
                    self.driver.find_element(By.ID, "produto")
                    logger.info("Campo 'produto' encontrado - página carregada")
                    return True
                except:
                    logger.error("Não conseguiu carregar página de estoque")
                    return False
                    
        except Exception as e:
            logger.error(f"Erro ao navegar para página de estoque: {str(e)}")
            return False
    
    def search_product(self, produto_codigo, situacao="TINTO"):
        """Realiza pesquisa de um produto específico COM SITUAÇÃO"""
        try:
            logger.info(f"Pesquisando produto {produto_codigo}, situação {situacao}...")
            
            # Verificar se estamos na página correta
            if "estoquePrevisaoConsulta" not in self.driver.current_url:
                if not self.navigate_to_stock_page():
                    return {
                        'success': False,
                        'codigo': produto_codigo,
                        'error': 'Não conseguiu acessar página de estoque'
                    }
            
            # Limpar campos
            self.clear_fields()
            
            # Encontrar e preencher campo de produto
            try:
                produto_field = self.driver.find_element(By.ID, "produto")
                produto_field.clear()
                produto_field.send_keys(str(produto_codigo))
                logger.info(f"Produto {produto_codigo} preenchido")
            except Exception as e:
                logger.error(f"Campo de produto não encontrado: {e}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': 'Campo de produto não encontrado'
                }
            
            # Encontrar e preencher campo de situação (TINTO)
            try:
                situacao_field = self.driver.find_element(By.ID, "situacao")
                situacao_field.clear()
                situacao_field.send_keys(situacao)
                logger.info(f"Situação '{situacao}' preenchida")
            except Exception as e:
                logger.warning(f"Campo de situação não encontrado: {e}")
            
            self.take_screenshot(f"antes_pesquisa_{produto_codigo}")
            
            # Encontrar e clicar no botão Pesquisar
            try:
                pesquisar_button = self.driver.find_element(By.ID, "j_idt67")
                pesquisar_button.click()
                logger.info("Botão Pesquisar clicado")
            except Exception as e:
                logger.error(f"Erro ao clicar no botão Pesquisar: {e}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Erro ao clicar em Pesquisar: {e}'
                }
            
            # Aguardar resultados
            time.sleep(8)
            
            # Verificar se há resultados
            try:
                self.take_screenshot(f"resultados_{produto_codigo}")
                
                # Extrair dados da página usando método MELHORADO
                dados = self.extract_stock_data_melhorado(produto_codigo)
                
                if dados:
                    return {
                        'success': True,
                        'codigo': produto_codigo,
                        'situacao': situacao,
                        'dados': dados,
                        'timestamp': datetime.now().isoformat(),
                        'total_registros': len(dados)
                    }
                else:
                    return {
                        'success': False,
                        'codigo': produto_codigo,
                        'error': 'Nenhum dado extraído da página'
                    }
                    
            except Exception as e:
                logger.error(f"Erro ao aguardar resultados: {e}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Timeout ao aguardar resultados: {e}'
                }
                
        except Exception as e:
            logger.error(f"Erro ao pesquisar produto {produto_codigo}: {e}")
            self.take_screenshot(f"erro_pesquisa_{produto_codigo}")
            return {
                'success': False,
                'codigo': produto_codigo,
                'error': str(e)
            }
    
    def extract_stock_data_melhorado(self, produto_codigo):
        """Extrai dados da página de forma MELHORADA analisando HTML diretamente"""
        dados_estruturados = []
        
        try:
            logger.info(f"Extraindo dados MELHORADOS para produto {produto_codigo}...")
            
            # Obter o HTML da página
            html_content = self.driver.page_source
            
            # Salvar HTML para debug
            debug_file = os.path.join(DEBUG_FOLDER, f"debug_html_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"HTML salvo para debug: {debug_file}")
            
            # Usar BeautifulSoup para parsear
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Método 1: Analisar estrutura HTML diretamente
            dados_html = self.analisar_estrutura_html(soup, produto_codigo)
            if dados_html:
                dados_estruturados.extend(dados_html)
                logger.info(f"Extraídos {len(dados_html)} registros do HTML")
            
            # Método 2: Se não encontrar, tentar extrair por texto
            if not dados_estruturados:
                dados_texto = self.extrair_por_texto_completo(produto_codigo)
                if dados_texto:
                    dados_estruturados.extend(dados_texto)
                    logger.info(f"Extraídos {len(dados_texto)} registros do texto")
            
            logger.info(f"Total de registros extraídos: {len(dados_estruturados)}")
            
            # Salvar dados brutos para análise
            if dados_estruturados:
                self.salvar_dados_brutos(dados_estruturados, produto_codigo)
            
        except Exception as e:
            logger.error(f"Erro na extração melhorada: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        return dados_estruturados
    
    def analisar_estrutura_html(self, soup, produto_codigo):
        """Analisa a estrutura HTML para extrair dados"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Procurar por divs que contenham dados de estoque
            # Baseado na estrutura que vimos: divs com informações de produto
            
            # Primeiro, encontrar todas as divs
            all_divs = soup.find_all('div')
            
            current_product = None
            current_description = ""
            
            for div in all_divs:
                div_text = div.get_text(strip=True)
                
                # Verificar se é um produto (contém código de 6 dígitos)
                if re.search(r'\b\d{6}\b', div_text) and len(div_text) > 10:
                    # Pode ser um produto
                    current_product = div_text
                    current_description = div_text
                    
                    # Verificar elementos filhos para mais informações
                    child_elements = div.find_all(['div', 'span', 'b', 'strong'])
                    for child in child_elements:
                        child_text = child.get_text(strip=True)
                        if child_text and child_text != current_product:
                            current_description += " " + child_text
                
                # Se temos um produto, procurar por dados numéricos
                elif current_product and produto_codigo in current_product:
                    # Procurar por padrões de data e valores
                    if re.match(r'^\d{2}/\d{2}/\d{4}$', div_text) or div_text.lower() == 'pronta entrega':
                        previsao = div_text
                        
                        # Procurar valores nos próximos elementos
                        next_siblings = div.find_next_siblings(['div', 'span'])
                        for sibling in next_siblings[:3]:  # Verificar próximos 3 elementos
                            sibling_text = sibling.get_text(strip=True)
                            valores = re.findall(r'[\d.,]+', sibling_text)
                            
                            if len(valores) >= 3:
                                estoque = self.formatar_valor(valores[0])
                                pedidos = self.formatar_valor(valores[1])
                                disponivel = self.formatar_valor(valores[2])
                                
                                registro = [
                                    str(produto_codigo).lstrip('0'),
                                    timestamp,
                                    current_description,
                                    previsao,
                                    estoque,
                                    pedidos,
                                    disponivel
                                ]
                                
                                dados.append(registro)
                                logger.info(f"Registro HTML: {produto_codigo} - {previsao}")
                                break
            
            # Método alternativo: procurar por tabelas ou listas
            if not dados:
                # Procurar por elementos que contenham múltiplos valores
                elements_with_numbers = soup.find_all(string=re.compile(r'[\d.,]+\s+[\d.,]+\s+[\d.,]+'))
                
                for element in elements_with_numbers:
                    parent = element.parent
                    # Verificar se o contexto contém o produto
                    context = parent.get_text()
                    if str(produto_codigo) in context:
                        # Extrair valores
                        valores = re.findall(r'[\d.,]+', element)
                        if len(valores) >= 3:
                            # Tentar encontrar data ou "Pronta entrega"
                            previsao = "Pronta entrega"
                            date_match = re.search(r'\d{2}/\d{2}/\d{4}', context)
                            if date_match:
                                previsao = date_match.group(0)
                            
                            # Extrair descrição
                            descricao = f"Produto {produto_codigo}"
                            prod_match = re.search(r'\d{6}\s+[A-Za-z\s]+', context)
                            if prod_match:
                                descricao = prod_match.group(0)
                            
                            registro = [
                                str(produto_codigo).lstrip('0'),
                                timestamp,
                                descricao,
                                previsao,
                                self.formatar_valor(valores[0]),
                                self.formatar_valor(valores[1]),
                                self.formatar_valor(valores[2])
                            ]
                            
                            dados.append(registro)
        
        except Exception as e:
            logger.error(f"Erro na análise HTML: {e}")
        
        return dados
    
    def extrair_por_texto_completo(self, produto_codigo):
        """Extrai dados do texto completo da página"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Obter todo o texto da página
            texto_completo = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Salvar texto para análise
            debug_text_file = os.path.join(DEBUG_FOLDER, f"debug_texto_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(debug_text_file, 'w', encoding='utf-8') as f:
                f.write(texto_completo)
            logger.info(f"Texto completo salvo: {debug_text_file}")
            
            # Dividir em linhas
            linhas = texto_completo.split('\n')
            
            # Padrão para encontrar blocos de produto
            i = 0
            while i < len(linhas):
                linha = linhas[i].strip()
                
                # Verificar se a linha contém o código do produto
                if str(produto_codigo).zfill(6) in linha or f"{produto_codigo} " in linha:
                    logger.info(f"Encontrado produto na linha {i}: {linha[:100]}")
                    
                    # Coletar informações do bloco
                    bloco = []
                    for j in range(i, min(i + 10, len(linhas))):
                        bloco.append(linhas[j].strip())
                    
                    # Processar o bloco
                    dados_bloco = self.processar_bloco_texto(bloco, produto_codigo, timestamp)
                    if dados_bloco:
                        dados.extend(dados_bloco)
                        logger.info(f"Extraídos {len(dados_bloco)} registros do bloco")
                    
                    i += 10  # Pular para próximo bloco
                else:
                    i += 1
        
        except Exception as e:
            logger.error(f"Erro na extração por texto: {e}")
        
        return dados
    
    def processar_bloco_texto(self, bloco, produto_codigo, timestamp):
        """Processa um bloco de texto para extrair dados"""
        dados = []
        
        try:
            # Construir descrição (primeiras linhas não numéricas)
            descricao_parts = []
            for linha in bloco[:3]:
                if linha and not re.search(r'[\d.,]+\s+[\d.,]+\s+[\d.,]+', linha):
                    descricao_parts.append(linha)
            
            descricao = ' '.join(descricao_parts) if descricao_parts else f"Produto {produto_codigo}"
            
            # Procurar por datas e valores
            for i in range(len(bloco)):
                linha = bloco[i]
                
                # Verificar se é data ou "Pronta entrega"
                if re.match(r'^\d{2}/\d{2}/\d{4}$', linha) or linha.lower() == 'pronta entrega':
                    previsao = linha
                    
                    # Procurar valores nas próximas linhas
                    for j in range(i + 1, min(i + 4, len(bloco))):
                        linha_valores = bloco[j]
                        valores = re.findall(r'[\d.,]+', linha_valores)
                        
                        if len(valores) >= 3:
                            estoque = self.formatar_valor(valores[0])
                            pedidos = self.formatar_valor(valores[1])
                            disponivel = self.formatar_valor(valores[2])
                            
                            registro = [
                                str(produto_codigo).lstrip('0'),
                                timestamp,
                                descricao,
                                previsao,
                                estoque,
                                pedidos,
                                disponivel
                            ]
                            
                            dados.append(registro)
                            break
        
        except Exception as e:
            logger.error(f"Erro no processamento do bloco: {e}")
        
        return dados
    
    def salvar_dados_brutos(self, dados, produto_codigo):
        """Salva dados brutos para análise"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"dados_brutos_{produto_codigo}_{timestamp}.json"
            filepath = os.path.join(DEBUG_FOLDER, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(dados, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Dados brutos salvos: {filepath}")
        except Exception as e:
            logger.error(f"Erro ao salvar dados brutos: {e}")
    
    def formatar_valor(self, valor_str):
        """Formata valor numérico para o padrão brasileiro"""
        try:
            # Remover espaços
            valor_str = str(valor_str).strip().replace(' ', '')
            
            if not valor_str:
                return "0,00"
            
            # Se já tem vírgula decimal
            if ',' in valor_str:
                partes = valor_str.split(',')
                inteiro = partes[0].replace('.', '')  # Remover pontos de milhar
                decimal = partes[1] if len(partes) > 1 else '00'
                
                # Garantir 2 casas decimais
                if len(decimal) == 1:
                    decimal = decimal + '0'
                elif len(decimal) == 0:
                    decimal = '00'
                elif len(decimal) > 2:
                    decimal = decimal[:2]
                
                return f"{inteiro},{decimal}"
            else:
                # Não tem vírgula, tratar como inteiro
                valor_str = valor_str.replace('.', '')  # Remover pontos
                return f"{valor_str},00"
                
        except Exception as e:
            logger.error(f"Erro ao formatar valor {valor_str}: {e}")
            return "0,00"
    
    def clear_fields(self):
        """Limpa os campos de pesquisa"""
        try:
            # Limpar campo produto
            produto_field = self.driver.find_element(By.ID, "produto")
            produto_field.clear()
        except:
            pass
        
        try:
            # Limpar campo situação
            situacao_field = self.driver.find_element(By.ID, "situacao")
            situacao_field.clear()
        except:
            pass
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver fechado")
            except:
                pass

# Funções auxiliares
def salvar_csv_estruturado(dados, produto_codigo, situacao):
    """Salva os dados em um arquivo CSV com formatação correta"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Ajustar o código do produto
        artigo_codigo = str(produto_codigo).lstrip('0')
        if not artigo_codigo:
            artigo_codigo = str(produto_codigo)
        
        filename = f"produto_{artigo_codigo}_{situacao}_{timestamp}.csv"
        filepath = os.path.join(CSV_FOLDER, filename)
        
        # Cabeçalho
        cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                    'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Escrever cabeçalho
            writer.writerow(cabecalho)
            
            # Escrever dados
            registros_validos = 0
            for linha in dados:
                if len(linha) == 7:
                    # Formatar valores
                    linha_formatada = []
                    for idx, valor in enumerate(linha):
                        if idx >= 4:  # Colunas numéricas
                            # Garantir formatação correta
                            valor_str = str(valor).strip()
                            if ',' not in valor_str:
                                if '.' in valor_str:
                                    partes = valor_str.split('.')
                                    if len(partes) == 2 and len(partes[1]) == 2:
                                        valor_str = partes[0] + ',' + partes[1]
                                    else:
                                        valor_str = valor_str.replace('.', '') + ',00'
                                else:
                                    valor_str = valor_str + ',00'
                            linha_formatada.append(valor_str)
                        else:
                            linha_formatada.append(valor)
                    
                    writer.writerow(linha_formatada)
                    registros_validos += 1
        
        logger.info(f"✅ CSV salvo: {filepath} ({registros_validos} registros)")
        
        # Salvar amostra no log
        if dados and registros_validos > 0:
            logger.info(f"📄 Amostra do CSV {filename}:")
            logger.info(f"Cabeçalho: {cabecalho}")
            for i, linha in enumerate(dados[:3]):
                logger.info(f"Linha {i}: {linha}")
        
        return filename
        
    except Exception as e:
        logger.error(f"❌ Erro ao salvar CSV: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def criar_csv_direto_html(html_content, produto_codigo, situacao):
    """Cria CSV diretamente do HTML sem usar Selenium"""
    try:
        logger.info(f"Criando CSV direto do HTML para produto {produto_codigo}")
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"produto_{produto_codigo}_{situacao}_{timestamp}_direto.csv"
        filepath = os.path.join(CSV_FOLDER, filename)
        
        # Parsear HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extrair dados
        dados = extrair_dados_direto_html(soup, produto_codigo)
        
        if not dados:
            logger.warning(f"Nenhum dado extraído do HTML para produto {produto_codigo}")
            return None
        
        # Salvar CSV
        cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                    'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(cabecalho)
            
            for linha in dados:
                if len(linha) == 7:
                    writer.writerow(linha)
        
        logger.info(f"✅ CSV direto salvo: {filepath} ({len(dados)} registros)")
        return filename
        
    except Exception as e:
        logger.error(f"Erro ao criar CSV direto: {e}")
        return None

def extrair_dados_direto_html(soup, produto_codigo):
    """Extrai dados diretamente do HTML"""
    dados = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        # Encontrar todo o texto
        texto_completo = soup.get_text(separator='\n')
        linhas = texto_completo.split('\n')
        
        # Procurar por blocos que contenham o produto
        for i in range(len(linhas)):
            linha = linhas[i].strip()
            
            # Verificar se contém o produto
            if str(produto_codigo).zfill(6) in linha or f" {produto_codigo} " in linha:
                # Coletar bloco
                bloco = []
                for j in range(max(0, i-2), min(len(linhas), i+8)):
                    if linhas[j].strip():
                        bloco.append(linhas[j].strip())
                
                # Processar bloco
                dados_bloco = processar_bloco_html(bloco, produto_codigo, timestamp)
                dados.extend(dados_bloco)
    
    except Exception as e:
        logger.error(f"Erro na extração direta HTML: {e}")
    
    return dados

def processar_bloco_html(bloco, produto_codigo, timestamp):
    """Processa um bloco de HTML para extrair dados"""
    dados = []
    
    try:
        # Construir descrição
        descricao_parts = []
        for linha in bloco:
            if linha and not re.search(r'[\d.,]+\s+[\d.,]+\s+[\d.,]+', linha) and not re.match(r'^\d{2}/\d{2}/\d{4}$', linha):
                descricao_parts.append(linha)
                if len(descricao_parts) >= 3:
                    break
        
        descricao = ' '.join(descricao_parts)
        
        # Procurar datas e valores
        for i in range(len(bloco)):
            linha = bloco[i]
            
            # Verificar se é data ou "Pronta entrega"
            if re.match(r'^\d{2}/\d{2}/\d{4}$', linha) or linha.lower() == 'pronta entrega':
                previsao = linha
                
                # Procurar valores
                for j in range(i + 1, min(i + 4, len(bloco))):
                    linha_valores = bloco[j]
                    valores = re.findall(r'[\d.,]+', linha_valores)
                    
                    if len(valores) >= 3:
                        # Formatar valores
                        estoque = formatar_valor_csv(valores[0])
                        pedidos = formatar_valor_csv(valores[1])
                        disponivel = formatar_valor_csv(valores[2])
                        
                        registro = [
                            str(produto_codigo).lstrip('0'),
                            timestamp,
                            descricao,
                            previsao,
                            estoque,
                            pedidos,
                            disponivel
                        ]
                        
                        dados.append(registro)
                        break
    
    except Exception as e:
        logger.error(f"Erro no processamento do bloco HTML: {e}")
    
    return dados

def formatar_valor_csv(valor_str):
    """Formata valor para CSV"""
    try:
        valor_str = str(valor_str).strip().replace(' ', '')
        
        if not valor_str:
            return "0,00"
        
        if ',' in valor_str:
            partes = valor_str.split(',')
            inteiro = partes[0].replace('.', '')
            decimal = partes[1] if len(partes) > 1 else '00'
            
            if len(decimal) == 1:
                decimal = decimal + '0'
            elif len(decimal) == 0:
                decimal = '00'
            
            return f"{inteiro},{decimal}"
        else:
            valor_str = valor_str.replace('.', '')
            return f"{valor_str},00"
            
    except Exception as e:
        return "0,00"

# Variáveis globais
scraper_thread = None
scraping_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'current': '',
    'message': '',
    'results': [],
    'start_time': None,
    'end_time': None
}

def run_scraping():
    """Função executada na thread para realizar o scraping"""
    global scraping_status
    
    scraper = None
    try:
        scraping_status['start_time'] = datetime.now().isoformat()
        
        # Ler lista de produtos
        produtos_file = 'produtos.txt'
        if not os.path.exists(produtos_file):
            with open(produtos_file, 'w') as f:
                f.write('14,15,19,20,23,24,27,28,29,30')
        
        with open(produtos_file, 'r') as f:
            conteudo = f.read().strip()
            produtos = [p.strip() for p in conteudo.split(',') if p.strip()]
        
        scraping_status['total'] = len(produtos)
        scraping_status['message'] = f'Encontrados {len(produtos)} produtos para processar'
        scraping_status['results'] = []
        
        # Inicializar scraper
        scraper = DGBScraper(headless=False)
        
        # Realizar login
        scraping_status['message'] = 'Realizando login...'
        logger.info("Tentando login...")
        if not scraper.login():
            scraping_status['message'] = 'Falha no login.'
            scraping_status['running'] = False
            logger.error("Login falhou")
            return
        
        scraping_status['message'] = 'Login realizado! Iniciando consultas...'
        logger.info("Login realizado com sucesso")
        
        # Processar cada produto
        for i, produto in enumerate(produtos, 1):
            if not scraping_status['running']:
                break
                
            scraping_status['current'] = produto
            scraping_status['progress'] = int((i / len(produtos)) * 100)
            scraping_status['message'] = f'Processando produto {produto} ({i}/{len(produtos)})'
            logger.info(f"Processando produto {produto} ({i}/{len(produtos)})")
            
            # Pesquisar produto
            resultado = scraper.search_product(produto, "TINTO")
            
            if resultado['success']:
                if resultado.get('dados'):
                    dados = resultado['dados']
                    
                    if dados:
                        # Salvar CSV
                        filename = salvar_csv_estruturado(dados, produto, "TINTO")
                        resultado['arquivo'] = filename
                        resultado['situacao'] = "TINTO"
                        resultado['dados_validos'] = len(dados)
                        scraping_status['message'] = f'✅ Produto {produto} processado: {len(dados)} registros'
                        logger.info(f"Produto {produto} processado: {len(dados)} registros")
                    else:
                        scraping_status['message'] = f'⚠️ Produto {produto}: nenhum registro encontrado'
                        resultado['situacao'] = "TINTO"
                        logger.warning(f"Produto {produto}: nenhum registro encontrado")
                else:
                    scraping_status['message'] = f'⚠️ Produto {produto}: nenhum dado encontrado'
                    resultado['situacao'] = "TINTO"
                    logger.warning(f"Produto {produto}: nenhum dado encontrado")
                
                scraping_status['results'].append(resultado)
            else:
                scraping_status['message'] = f'❌ Erro no produto {produto}: {resultado.get("error", "Erro desconhecido")}'
                logger.error(f"Erro no produto {produto}: {resultado.get('error', 'Erro desconhecido')}")
            
            # Pausa entre requisições
            time.sleep(3)
        
        scraping_status['end_time'] = datetime.now().isoformat()
        scraping_status['message'] = '✅ Scraping concluído com sucesso!'
        logger.info("Scraping concluído com sucesso!")
        
    except Exception as e:
        logger.error(f"❌ Erro na thread de scraping: {str(e)}")
        scraping_status['message'] = f"❌ Erro durante scraping: {str(e)}"
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
    finally:
        if scraper:
            scraper.close()
            logger.info("Driver fechado")
        scraping_status['running'] = False
        scraping_status['end_time'] = scraping_status['end_time'] or datetime.now().isoformat()

# Rotas Flask
@app.route('/')
def index():
    """Página inicial"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Retorna o status atual do scraping"""
    return jsonify(scraping_status)

@app.route('/api/start', methods=['POST'])
def start_scraping():
    """Inicia o processo de scraping"""
    global scraper_thread, scraping_status
    
    if scraping_status['running']:
        return jsonify({'error': 'Scraping já está em execução'}), 400
    
    # Reiniciar status
    scraping_status = {
        'running': True,
        'progress': 0,
        'total': 0,
        'current': '',
        'message': 'Iniciando...',
        'results': [],
        'start_time': None,
        'end_time': None
    }
    
    # Iniciar thread
    scraper_thread = threading.Thread(target=run_scraping)
    scraper_thread.daemon = True
    scraper_thread.start()
    
    return jsonify({'success': True, 'message': 'Scraping iniciado'})

@app.route('/api/stop', methods=['POST'])
def stop_scraping():
    """Para o scraping em execução"""
    global scraping_status
    scraping_status['running'] = False
    return jsonify({'success': True, 'message': 'Scraping sendo interrompido'})

@app.route('/api/debug/analyze/<produto_codigo>', methods=['GET'])
def debug_analyze(produto_codigo):
    """Analisa o HTML de um produto específico"""
    try:
        scraper = DGBScraper(headless=False)
        
        # Login
        if not scraper.login():
            scraper.close()
            return jsonify({'success': False, 'error': 'Falha no login'})
        
        # Pesquisar produto
        scraper.clear_fields()
        
        produto_field = scraper.driver.find_element(By.ID, "produto")
        produto_field.clear()
        produto_field.send_keys(str(produto_codigo))
        
        situacao_field = scraper.driver.find_element(By.ID, "situacao")
        situacao_field.clear()
        situacao_field.send_keys("TINTO")
        
        pesquisar_button = scraper.driver.find_element(By.ID, "j_idt67")
        pesquisar_button.click()
        
        time.sleep(8)
        
        # Obter HTML
        html_content = scraper.driver.page_source
        
        # Salvar HTML
        debug_file = os.path.join(DEBUG_FOLDER, f"debug_analyze_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        # Analisar HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Encontrar div de resultados
        lista_div = soup.find('div', id='estoquePrevisaoList')
        
        # Extrair informações
        analysis = {
            'produto': produto_codigo,
            'html_file': debug_file,
            'tem_lista_div': lista_div is not None,
            'texto_lista_div': lista_div.get_text(separator='\n', strip=True)[:500] + '...' if lista_div else None,
            'elementos_encontrados': []
        }
        
        # Procurar por padrões
        texto_completo = soup.get_text(separator='\n')
        linhas = texto_completo.split('\n')
        
        for i, linha in enumerate(linhas[:50]):  # Analisar primeiras 50 linhas
            if str(produto_codigo) in linha:
                analysis['elementos_encontrados'].append({
                    'linha': i,
                    'conteudo': linha[:100] + '...' if len(linha) > 100 else linha
                })
        
        scraper.close()
        
        return jsonify({
            'success': True,
            'analysis': analysis,
            'html_preview': html_content[:2000] + '...' if len(html_content) > 2000 else html_content
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/debug/create_csv_direct', methods=['POST'])
def debug_create_csv_direct():
    """Cria CSV diretamente do HTML"""
    try:
        data = request.json
        produto_codigo = data.get('produto_codigo')
        html_content = data.get('html_content')
        
        if not produto_codigo or not html_content:
            return jsonify({'success': False, 'error': 'Produto e HTML são obrigatórios'})
        
        filename = criar_csv_direto_html(html_content, produto_codigo, "TINTO")
        
        if filename:
            return jsonify({
                'success': True,
                'filename': filename,
                'message': f'CSV criado com sucesso: {filename}'
            })
        else:
            return jsonify({'success': False, 'error': 'Não foi possível criar o CSV'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get-products')
def get_products():
    """Retorna a lista de produtos atual"""
    try:
        with open('produtos.txt', 'r') as f:
            produtos = f.read().strip()
        return jsonify({'produtos': produtos})
    except Exception as e:
        return jsonify({'produtos': '14,15,19,20,23,24,27,28,29,30'})

@app.route('/api/update-products', methods=['POST'])
def update_products():
    """Atualiza a lista de produtos"""
    try:
        data = request.json
        produtos = data.get('produtos', '')
        
        with open('produtos.txt', 'w') as f:
            f.write(produtos)
        
        return jsonify({'success': True, 'message': 'Lista de produtos atualizada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/files/csv')
def list_csv_files():
    """Lista arquivos CSV"""
    try:
        files = []
        for file in os.listdir(CSV_FOLDER):
            if file.endswith('.csv'):
                filepath = os.path.join(CSV_FOLDER, file)
                files.append({
                    'name': file,
                    'size': os.path.getsize(filepath),
                    'path': f'/download/csv/{file}'
                })
        return jsonify({'files': sorted(files, key=lambda x: x['name'], reverse=True)})
    except Exception as e:
        return jsonify({'files': []})

@app.route('/api/files/debug')
def list_debug_files():
    """Lista arquivos de debug"""
    try:
        files = []
        for file in os.listdir(DEBUG_FOLDER):
            if file.endswith(('.html', '.txt', '.json')):
                filepath = os.path.join(DEBUG_FOLDER, file)
                files.append({
                    'name': file,
                    'size': os.path.getsize(filepath),
                    'path': f'/download/debug/{file}'
                })
        return jsonify({'files': sorted(files, key=lambda x: x['name'], reverse=True)})
    except Exception as e:
        return jsonify({'files': []})

@app.route('/download/csv/<filename>')
def download_csv(filename):
    """Download de arquivo CSV"""
    try:
        return send_from_directory(CSV_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return f"Erro ao baixar arquivo: {str(e)}", 404

@app.route('/download/debug/<filename>')
def download_debug(filename):
    """Download de arquivo de debug"""
    try:
        return send_from_directory(DEBUG_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return f"Erro ao baixar arquivo: {str(e)}", 404

@app.route('/api/test-login', methods=['POST'])
def test_login():
    """Testa as credenciais de login"""
    try:
        scraper = DGBScraper(headless=False)
        success = scraper.login()
        scraper.close()
        
        if success:
            return jsonify({'success': True, 'message': 'Login testado com sucesso!'})
        else:
            return jsonify({'success': False, 'error': 'Falha no login. Verifique as credenciais no arquivo .env'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # Verificar se o arquivo .env existe
    if not os.path.exists('.env'):
        logger.error("❌ Arquivo .env não encontrado!")
        logger.info("📝 Por favor, crie um arquivo .env com as seguintes variáveis:")
        logger.info("   DGB_USUARIO=seu_usuario")
        logger.info("   DGB_SENHA=sua_senha")
        logger.info("   DGB_URL_LOGIN=http://sistemadgb.4pu.com:90/dgb/login.jsf")
        logger.info("   DGB_URL_ESTOQUE=http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf")
        exit(1)
    
    # Carregar variáveis de ambiente
    load_dotenv()
    
    # Verificar se todas as variáveis necessárias estão definidas
    required_vars = ['DGB_USUARIO', 'DGB_SENHA', 'DGB_URL_LOGIN', 'DGB_URL_ESTOQUE']
    missing_vars = []
    
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"❌ Variáveis de ambiente faltando: {', '.join(missing_vars)}")
        logger.info("📝 Configure essas variáveis no arquivo .env")
        exit(1)
    
    # Criar pastas necessárias
    os.makedirs('templates', exist_ok=True)
    
    logger.info("✅ Configurações carregadas. Sistema pronto.")
    logger.info(f"👤 Usuário: {os.getenv('DGB_USUARIO')}")
    logger.info(f"🔗 URL Login: {os.getenv('DGB_URL_LOGIN')}")
    
    # Verificar se existe arquivo de produtos
    if not os.path.exists('produtos.txt'):
        with open('produtos.txt', 'w') as f:
            f.write('14,15,19,20,23,24,27,28,29,30')
        logger.info("📝 Arquivo produtos.txt criado com valores padrão")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)