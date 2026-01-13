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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd
from reportlab.lib.pagesizes import letter, A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, cm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
import base64
from io import BytesIO, StringIO
from bs4 import BeautifulSoup
from dotenv import load_dotenv

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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(CONSOLIDATED_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dgb-comex-scraper-secret-2024')

# Configurações do sistema DGB (agora do .env)
DGB_USUARIO = os.getenv('DGB_USUARIO', 'tiago')
DGB_SENHA = os.getenv('DGB_SENHA', 'Esmeralda852456#&')
DGB_URL_LOGIN = os.getenv('DGB_URL_LOGIN', 'http://sistemadgb.4pu.com:90/dgb/login.jsf')
DGB_URL_ESTOQUE = os.getenv('DGB_URL_ESTOQUE', 'http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf')

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_FOLDER, 'scraper.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DGBScraper:
    def __init__(self, headless=False):  # False para debugging
        self.headless = headless
        self.driver = None
        self.wait = None
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.usuario = DGB_USUARIO
        self.senha = DGB_SENHA
        self.url_login = DGB_URL_LOGIN
        self.url_estoque = DGB_URL_ESTOQUE
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
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--allow-running-insecure-content')
        
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
        """Efetua login no sistema DGB usando credenciais do .env"""
        try:
            logger.info(f"Acessando página de login: {self.url_login}")
            logger.info(f"Usando usuário: {self.usuario}")
            
            self.driver.get(self.url_login)
            time.sleep(3)
            
            self.take_screenshot("login_page")
            
            # Aguardar carregamento completo da página
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Localizar campos de login
            try:
                # Tentar pelo ID primeiro
                login_field = self.driver.find_element(By.ID, "login")
            except NoSuchElementException:
                # Tentar pelo name
                login_field = self.driver.find_element(By.NAME, "login")
            
            # Preencher usuário
            login_field.clear()
            login_field.send_keys(self.usuario)
            
            # Localizar campo de senha
            try:
                senha_field = self.driver.find_element(By.ID, "senha")
            except NoSuchElementException:
                # Tentar pelo name com valor do campo
                senha_field = self.driver.find_element(By.CSS_SELECTOR, "input[type='password']")
            
            # Preencher senha
            senha_field.clear()
            senha_field.send_keys(self.senha)
            
            self.take_screenshot("credenciais_preenchidas")
            
            # Clicar no botão de login
            try:
                # Procurar botão por texto ou classe
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except NoSuchElementException:
                # Tentar pelo ID
                login_button = self.driver.find_element(By.ID, "botaoEntrar")
            
            login_button.click()
            
            # Aguardar redirecionamento ou mudança na página
            time.sleep(5)
            
            # Verificar se login foi bem sucedido
            current_url = self.driver.current_url
            logger.info(f"URL após login: {current_url}")
            
            self.take_screenshot("apos_login")
            
            # Verificar elementos que indicam login bem sucedido
            try:
                # Verificar se existe o menu ou elementos da dashboard
                self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "topo")))
                logger.info("Login realizado com sucesso!")
                
                # AGORA VAMOS DIRETO PARA A URL DE ESTOQUE
                return self.navigate_to_stock_page()
                
            except TimeoutException:
                # Verificar se há mensagem de erro
                try:
                    error_elements = self.driver.find_elements(By.CLASS_NAME, "toast")
                    if error_elements:
                        error_text = error_elements[0].text
                        logger.error(f"Erro de login: {error_text}")
                        return False
                except:
                    pass
                
                # Verificar se ainda está na página de login
                if "login" in current_url.lower():
                    logger.error("Falha no login - ainda na página de login")
                    return False
                else:
                    logger.info("Login aparentemente bem sucedido (URL mudou)")
                    # Tentar ir para a página de estoque mesmo assim
                    return self.navigate_to_stock_page()
                
        except Exception as e:
            logger.error(f"Erro durante login: {str(e)}")
            self.take_screenshot("erro_login")
            return False
    
    def navigate_to_stock_page(self):
        """Navega DIRETAMENTE para a página de consulta de estoque via URL do .env"""
        try:
            logger.info(f"Navegando DIRETAMENTE para página de consulta de estoque: {self.url_estoque}")
            
            # Ir DIRETAMENTE para a URL de estoque
            self.driver.get(self.url_estoque)
            
            # Aguardar carregamento da página
            time.sleep(5)
            
            # Verificar se estamos na página correta
            current_url = self.driver.current_url
            logger.info(f"URL atual após navegação: {current_url}")
            
            self.take_screenshot("depois_navegacao_estoque")
            
            # Tentar encontrar o campo de produto para confirmar que carregou
            try:
                # Primeiro tentar pelo ID
                produto_field = self.driver.find_element(By.ID, "produto")
                logger.info("Página de estoque carregada com sucesso! Campo 'produto' encontrado.")
                return True
            except NoSuchElementException:
                # Tentar por NAME
                try:
                    produto_field = self.driver.find_element(By.NAME, "produto")
                    logger.info("Campo 'produto' encontrado por NAME")
                    return True
                except:
                    # Tentar por XPath com texto parcial
                    try:
                        produto_field = self.driver.find_element(By.XPATH, "//input[contains(@name, 'produto') or contains(@id, 'produto')]")
                        logger.info("Campo 'produto' encontrado por XPath")
                        return True
                    except:
                        logger.warning("Não encontrou campo 'produto' específico")
            
            # Mesmo se não encontrar campo específico, verificar se a página carregou
            page_source = self.driver.page_source.lower()
            if "estoque" in page_source or "previsão" in page_source or "consulta" in page_source:
                logger.info("Página parece ser de estoque (palavras-chave encontradas)")
                return True
            else:
                logger.error("Não parece ser a página de estoque")
                return False
            
        except Exception as e:
            logger.error(f"Erro ao navegar para página de estoque: {str(e)}")
            self.take_screenshot("erro_navegacao_estoque")
            return False
    
    def search_product(self, produto_codigo, situacao="TINTO"):
        """Realiza pesquisa de um produto específico"""
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
            
            # Encontrar e preencher campo de produto
            try:
                # Tentar múltiplas estratégias para encontrar o campo
                produto_field = None
                strategies = [
                    (By.ID, "produto"),
                    (By.NAME, "produto"),
                    (By.CSS_SELECTOR, "input[name*='produto']"),
                    (By.XPATH, "//input[contains(@id, 'produto') or contains(@name, 'produto')]")
                ]
                
                for by, value in strategies:
                    try:
                        produto_field = self.driver.find_element(by, value)
                        logger.info(f"Campo produto encontrado usando {by}: {value}")
                        break
                    except:
                        continue
                
                if produto_field:
                    produto_field.clear()
                    produto_field.send_keys(str(produto_codigo))
                else:
                    logger.error("Não encontrou campo de produto")
                    return {
                        'success': False,
                        'codigo': produto_codigo,
                        'error': 'Campo de produto não encontrado'
                    }
                    
            except Exception as e:
                logger.error(f"Erro ao preencher produto: {str(e)}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Erro ao preencher produto: {str(e)}'
                }
            
            # Encontrar e preencher campo de situação
            try:
                situacao_field = None
                strategies = [
                    (By.ID, "situacao"),
                    (By.NAME, "situacao"),
                    (By.CSS_SELECTOR, "input[name*='situacao']"),
                    (By.XPATH, "//input[contains(@id, 'situacao') or contains(@name, 'situacao')]")
                ]
                
                for by, value in strategies:
                    try:
                        situacao_field = self.driver.find_element(by, value)
                        logger.info(f"Campo situação encontrado usando {by}: {value}")
                        break
                    except:
                        continue
                
                if situacao_field:
                    situacao_field.clear()
                    situacao_field.send_keys(situacao)
                else:
                    logger.warning("Não encontrou campo de situação específico")
                    # Tentar encontrar select em vez de input
                    try:
                        situacao_select = self.driver.find_element(By.CSS_SELECTOR, "select[name*='situacao']")
                        select = Select(situacao_select)
                        select.select_by_visible_text(situacao)
                        logger.info(f"Situação selecionada no dropdown: {situacao}")
                    except:
                        logger.warning("Também não encontrou dropdown de situação")
                    
            except Exception as e:
                logger.warning(f"Erro ao preencher situação: {str(e)}")
            
            self.take_screenshot(f"antes_pesquisa_{produto_codigo}")
            
            # Encontrar e clicar no botão Pesquisar
            try:
                pesquisar_button = None
                strategies = [
                    (By.CSS_SELECTOR, "input[value*='Pesquisar'], input[value*='PESQUISAR']"),
                    (By.XPATH, "//input[@type='submit' and contains(@value, 'Pesquisar')]"),
                    (By.XPATH, "//button[contains(text(), 'Pesquisar')]"),
                    (By.ID, "botaoPesquisar"),
                    (By.CSS_SELECTOR, "input[type='submit']")
                ]
                
                for by, value in strategies:
                    try:
                        if by == By.XPATH and "contains(text()" in value:
                            pesquisar_button = self.driver.find_element(by, value)
                        else:
                            pesquisar_button = self.driver.find_element(by, value)
                        logger.info(f"Botão pesquisar encontrado usando {by}")
                        break
                    except:
                        continue
                
                if pesquisar_button:
                    pesquisar_button.click()
                else:
                    logger.error("Não encontrou botão Pesquisar")
                    return {
                        'success': False,
                        'codigo': produto_codigo,
                        'error': 'Botão Pesquisar não encontrado'
                    }
                    
            except Exception as e:
                logger.error(f"Erro ao clicar no botão Pesquisar: {str(e)}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Erro ao clicar em Pesquisar: {str(e)}'
                }
            
            # Aguardar carregamento dos resultados
            time.sleep(5)
            
            # Verificar se há resultados
            try:
                # Aguardar carregamento
                time.sleep(3)
                
                self.take_screenshot(f"resultados_{produto_codigo}")
                
                # Extrair dados da página
                dados = self.extract_stock_data(produto_codigo)
                
                return {
                    'success': True,
                    'codigo': produto_codigo,
                    'situacao': situacao,
                    'dados': dados,
                    'timestamp': datetime.now().isoformat(),
                    'total_registros': len(dados) if dados else 0
                }
                
            except Exception as e:
                logger.error(f"Erro ao aguardar resultados: {str(e)}")
                # Verificar se há mensagem de "nenhum resultado"
                page_source = self.driver.page_source
                if "nenhum" in page_source.lower() or "não encontrado" in page_source.lower() or "no records" in page_source.lower():
                    logger.warning(f"Nenhum resultado encontrado para produto {produto_codigo}")
                    return {
                        'success': True,
                        'codigo': produto_codigo,
                        'situacao': situacao,
                        'dados': [],
                        'timestamp': datetime.now().isoformat(),
                        'total_registros': 0,
                        'mensagem': 'Nenhum resultado encontrado'
                    }
                else:
                    return {
                        'success': False,
                        'codigo': produto_codigo,
                        'error': f'Timeout ao aguardar resultados: {str(e)}'
                    }
                    
        except Exception as e:
            logger.error(f"Erro ao pesquisar produto {produto_codigo}: {str(e)}")
            self.take_screenshot(f"erro_pesquisa_{produto_codigo}")
            return {
                'success': False,
                'codigo': produto_codigo,
                'error': str(e)
            }
    
    def extract_stock_data(self, produto_codigo):
        """Extrai dados da tabela de estoque"""
        dados = []
        
        try:
            # Obter o HTML da página
            page_source = self.driver.page_source
            
            # Salvar HTML para análise
            html_path = f"html_produto_{produto_codigo}_{datetime.now().strftime('%H%M%S')}.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page_source)
            logger.info(f"HTML salvo: {html_path}")
            
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Estratégia 1: Procurar por tabelas
            tabelas = soup.find_all('table')
            logger.info(f"Encontradas {len(tabelas)} tabelas na página")
            
            for i, tabela in enumerate(tabelas):
                # Extrair linhas da tabela
                linhas = tabela.find_all('tr')
                
                for linha in linhas:
                    celulas = linha.find_all(['td', 'th'])
                    
                    if celulas:
                        dados_linha = []
                        for celula in celulas:
                            texto = celula.get_text(strip=True, separator=' ')
                            texto = ' '.join(texto.split())
                            if texto:
                                dados_linha.append(texto)
                        
                        if dados_linha:
                            # Adicionar informações adicionais
                            dados_linha.insert(0, str(produto_codigo))
                            dados_linha.insert(1, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                            dados.append(dados_linha)
            
            # Estratégia 2: Procurar por divs que possam conter dados
            if not dados:
                divs_com_dados = soup.find_all(['div', 'section', 'article'])
                for div in divs_com_dados:
                    texto = div.get_text(strip=True, separator='\n')
                    if len(texto) > 50 and ("estoque" in texto.lower() or "previsão" in texto.lower()):
                        linhas_texto = texto.split('\n')
                        for linha_texto in linhas_texto:
                            if linha_texto.strip() and len(linha_texto.strip()) > 10:
                                dados.append([produto_codigo, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), linha_texto])
            
            logger.info(f"Extraídos {len(dados)} registros para produto {produto_codigo}")
            
        except Exception as e:
            logger.error(f"Erro ao extrair dados: {str(e)}")
        
        return dados
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver fechado")
            except:
                pass

# Funções auxiliares para o Flask
def salvar_csv(dados, produto_codigo, tipo='individual'):
    """Salva os dados em um arquivo CSV"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if tipo == 'individual':
            filename = f"produto_{produto_codigo}_{timestamp}.csv"
            filepath = os.path.join(CSV_FOLDER, filename)
        else:
            filename = f"consolidado_{timestamp}.csv"
            filepath = os.path.join(CONSOLIDATED_FOLDER, filename)
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            
            # Escrever cabeçalho se for consolidado
            if tipo == 'consolidado' and dados:
                cabecalho = ['CODIGO_PRODUTO', 'DATA_HORA', 'PRODUTO_DESCRICAO', 
                           'SITUACAO', 'COR', 'DESENHO', 'VARIANTE', 
                           'PRONTA_ENTREGA', 'ESTOQUE', 'PEDIDOS', 'DISPONIVEL']
                writer.writerow(cabecalho)
            
            for linha in dados:
                writer.writerow(linha)
        
        logger.info(f"Dados salvos em {filepath}")
        return filename
    except Exception as e:
        logger.error(f"Erro ao salvar CSV: {str(e)}")
        return None

def consolidar_dados():
    """Consolida todos os CSVs em um único arquivo"""
    try:
        arquivos_csv = [f for f in os.listdir(CSV_FOLDER) if f.endswith('.csv')]
        
        if not arquivos_csv:
            return None, "Nenhum arquivo CSV encontrado para consolidar"
        
        dados_consolidados = []
        
        for arquivo in arquivos_csv:
            filepath = os.path.join(CSV_FOLDER, arquivo)
            
            try:
                # Extrair código do produto do nome do arquivo
                codigo_match = re.search(r'produto_(\d+)_', arquivo)
                codigo_produto = codigo_match.group(1) if codigo_match else 'N/A'
                
                # Ler o arquivo CSV
                with open(filepath, 'r', encoding='utf-8-sig') as csvfile:
                    reader = csv.reader(csvfile, delimiter=';')
                    
                    for linha in reader:
                        if linha:  # Ignorar linhas vazias
                            # Adicionar código do produto se não estiver presente
                            if len(linha) > 0 and linha[0] != codigo_produto:
                                linha.insert(0, codigo_produto)
                            dados_consolidados.append(linha)
                            
            except Exception as e:
                logger.error(f"Erro ao processar arquivo {arquivo}: {str(e)}")
                continue
        
        if dados_consolidados:
            # Salvar consolidado
            filename = salvar_csv(dados_consolidados, 'CONSOLIDADO', 'consolidado')
            return filename, f"Consolidados {len(dados_consolidados)} registros de {len(arquivos_csv)} arquivos"
        else:
            return None, "Nenhum dado para consolidar"
            
    except Exception as e:
        logger.error(f"Erro na consolidação: {str(e)}")
        return None, f"Erro na consolidação: {str(e)}"

def gerar_relatorio_pdf(dados_consolidados):
    """Gera relatório PDF com os dados consolidados"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"relatorio_consolidado_{timestamp}.pdf"
        filepath = os.path.join(PDF_FOLDER, filename)
        
        # Criar documento PDF
        doc = SimpleDocTemplate(
            filepath,
            pagesize=landscape(A4),
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Título
        titulo_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
            alignment=1  # Center
        )
        
        titulo = Paragraph(f"<b>RELATÓRIO CONSOLIDADO - DGB COMEX</b><br/>"
                          f"<font size=10>Data de geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</font>",
                          titulo_style)
        elements.append(titulo)
        
        # Resumo
        if dados_consolidados:
            total_registros = len(dados_consolidados)
            produtos_unicos = len(set([linha[0] for linha in dados_consolidados if len(linha) > 0]))
            
            resumo = Paragraph(
                f"<b>RESUMO:</b><br/>"
                f"Total de registros: {total_registros}<br/>"
                f"Produtos processados: {produtos_unicos}<br/>"
                f"Data da última coleta: {dados_consolidados[0][1] if len(dados_consolidados[0]) > 1 else 'N/A'}",
                styles['Normal']
            )
            elements.append(resumo)
            elements.append(Spacer(1, 20))
        
        # Tabela de dados
        if dados_consolidados:
            # Preparar dados para tabela (limitar a 50 linhas para o relatório)
            dados_tabela = dados_consolidados[:50]
            
            # Criar tabela
            tabela = Table(dados_tabela, repeatRows=1)
            
            # Estilizar tabela
            estilo = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ])
            
            tabela.setStyle(estilo)
            elements.append(tabela)
            
            if len(dados_consolidados) > 50:
                elements.append(Spacer(1, 10))
                aviso = Paragraph(
                    f"<i>Mostrando 50 de {len(dados_consolidados)} registros. "
                    f"Consulte o arquivo CSV para dados completos.</i>",
                    styles['Italic']
                )
                elements.append(aviso)
        else:
            elements.append(Paragraph("Nenhum dado disponível para exibição.", styles['Normal']))
        
        # Rodapé
        elements.append(Spacer(1, 20))
        rodape = Paragraph(
            f"<font size=7>Sistema de Web Scraping DGB COMEX - "
            f"Gerado automaticamente em {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</font>",
            styles['Normal']
        )
        elements.append(rodape)
        
        # Gerar PDF
        doc.build(elements)
        
        logger.info(f"PDF gerado: {filepath}")
        return filename
        
    except Exception as e:
        logger.error(f"Erro ao gerar PDF: {str(e)}")
        return None

# Variáveis globais para controle do scraping
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
                f.write('13,14,15,16,17')
        
        with open(produtos_file, 'r') as f:
            conteudo = f.read().strip()
            produtos = [p.strip() for p in conteudo.split(',') if p.strip()]
        
        scraping_status['total'] = len(produtos)
        scraping_status['message'] = f'Encontrados {len(produtos)} produtos para processar'
        scraping_status['results'] = []
        
        # Inicializar scraper
        scraper = DGBScraper(headless=False)  # False para debugging
        
        # Realizar login e navegar para estoque
        scraping_status['message'] = 'Realizando login e navegando para estoque...'
        if not scraper.login():
            scraping_status['message'] = 'Falha no login ou navegação para estoque.'
            scraping_status['running'] = False
            return
        
        # Processar cada produto
        for i, produto in enumerate(produtos, 1):
            if not scraping_status['running']:
                break
                
            scraping_status['current'] = produto
            scraping_status['progress'] = int((i / len(produtos)) * 100)
            scraping_status['message'] = f'Processando produto {produto} ({i}/{len(produtos)})'
            
            # Pesquisar produto
            resultado = scraper.search_product(produto, "TINTO")
            
            if resultado['success']:
                if resultado.get('dados'):
                    # Salvar CSV individual
                    filename = salvar_csv(resultado['dados'], produto)
                    resultado['arquivo'] = filename
                    scraping_status['message'] = f'Produto {produto} processado: {len(resultado["dados"])} registros'
                else:
                    scraping_status['message'] = f'Produto {produto}: nenhum dado encontrado'
                
                scraping_status['results'].append(resultado)
            else:
                scraping_status['message'] = f'Erro no produto {produto}: {resultado.get("error", "Erro desconhecido")}'
            
            # Pequena pausa entre requisições
            time.sleep(2)
        
        scraping_status['end_time'] = datetime.now().isoformat()
        scraping_status['message'] = 'Scraping concluído com sucesso!'
        
        # Consolidar dados
        scraping_status['message'] = 'Consolidando dados...'
        filename, mensagem = consolidar_dados()
        if filename:
            scraping_status['consolidated_file'] = filename
            scraping_status['consolidated_message'] = mensagem
            
            # Gerar PDF
            # Ler dados consolidados para gerar PDF
            consolidated_path = os.path.join(CONSOLIDATED_FOLDER, filename)
            if os.path.exists(consolidated_path):
                with open(consolidated_path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f, delimiter=';')
                    dados_consolidados = list(reader)[1:]  # Pular cabeçalho
                
                pdf_filename = gerar_relatorio_pdf(dados_consolidados)
                if pdf_filename:
                    scraping_status['pdf_file'] = pdf_filename
        
    except Exception as e:
        logger.error(f"Erro na thread de scraping: {str(e)}")
        scraping_status['message'] = f'Erro durante scraping: {str(e)}'
    finally:
        if scraper:
            scraper.close()
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

@app.route('/api/consolidate', methods=['POST'])
def consolidate():
    """Consolida os dados coletados"""
    filename, message = consolidar_dados()
    
    if filename:
        return jsonify({
            'success': True,
            'filename': filename,
            'message': message
        })
    else:
        return jsonify({
            'success': False,
            'message': message
        }), 400

@app.route('/api/files/csv')
def list_csv_files():
    """Lista arquivos CSV disponíveis"""
    try:
        files = []
        for filename in os.listdir(CSV_FOLDER):
            if filename.endswith('.csv'):
                filepath = os.path.join(CSV_FOLDER, filename)
                stats = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stats.st_size,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    'path': f'/download/csv/{filename}'
                })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/consolidated')
def list_consolidated_files():
    """Lista arquivos consolidados"""
    try:
        files = []
        for filename in os.listdir(CONSOLIDATED_FOLDER):
            if filename.endswith('.csv'):
                filepath = os.path.join(CONSOLIDATED_FOLDER, filename)
                stats = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stats.st_size,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    'path': f'/download/consolidated/{filename}'
                })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/files/pdf')
def list_pdf_files():
    """Lista arquivos PDF"""
    try:
        files = []
        for filename in os.listdir(PDF_FOLDER):
            if filename.endswith('.pdf'):
                filepath = os.path.join(PDF_FOLDER, filename)
                stats = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stats.st_size,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    'path': f'/download/pdf/{filename}'
                })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/csv/<filename>')
def download_csv(filename):
    """Baixa arquivo CSV"""
    return send_from_directory(CSV_FOLDER, filename, as_attachment=True)

@app.route('/download/consolidated/<filename>')
def download_consolidated(filename):
    """Baixa arquivo consolidado"""
    return send_from_directory(CONSOLIDATED_FOLDER, filename, as_attachment=True)

@app.route('/download/pdf/<filename>')
def download_pdf(filename):
    """Baixa arquivo PDF"""
    return send_from_directory(PDF_FOLDER, filename, as_attachment=True)

@app.route('/api/test-login', methods=['POST'])
def test_login():
    """Testa o login com as credenciais fornecidas via .env"""
    # Agora sempre usa as credenciais do .env
    scraper = DGBScraper(headless=False)
    try:
        success = scraper.login()
        scraper.close()
        return jsonify({'success': success})
    except Exception as e:
        scraper.close()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update-products', methods=['POST'])
def update_products():
    """Atualiza a lista de produtos"""
    data = request.json
    produtos = data.get('produtos', '')
    
    try:
        with open('produtos.txt', 'w') as f:
            f.write(produtos)
        return jsonify({'success': True, 'message': 'Lista de produtos atualizada'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/get-products')
def get_products():
    """Retorna a lista atual de produtos"""
    try:
        with open('produtos.txt', 'r') as f:
            produtos = f.read().strip()
        return jsonify({'produtos': produtos})
    except:
        return jsonify({'produtos': '13,14,15,16,17'})

@app.route('/api/config', methods=['GET'])
def get_config():
    """Retorna as configurações atuais do sistema"""
    config = {
        'usuario': DGB_USUARIO,
        'url_login': DGB_URL_LOGIN,
        'url_estoque': DGB_URL_ESTOQUE,
        'diretorios': {
            'csv': CSV_FOLDER,
            'pdf': PDF_FOLDER,
            'logs': LOG_FOLDER,
            'screenshots': SCREENSHOT_FOLDER,
            'consolidados': CONSOLIDATED_FOLDER
        }
    }
    return jsonify(config)

if __name__ == '__main__':
    # Verificar se o arquivo .env existe, se não, criar com valores padrão
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(f'''# Configurações DGB COMEX
DGB_USUARIO=tiago
DGB_SENHA=Esmeralda852456#&
DGB_URL_LOGIN=http://sistemadgb.4pu.com:90/dgb/login.jsf
DGB_URL_ESTOQUE=http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf
FLASK_SECRET_KEY=dgb-comex-scraper-secret-2024

# Configurações do Scraping
SCRAPING_DELAY=2
SCRAPING_TIMEOUT=30
SCRAPING_HEADLESS=False
''')
        logger.info("Arquivo .env criado com configurações padrão")
    
    # Recarregar variáveis de ambiente
    load_dotenv()
    
    # Atualizar variáveis com valores do .env
    DGB_USUARIO = os.getenv('DGB_USUARIO', 'tiago')
    DGB_SENHA = os.getenv('DGB_SENHA', 'Esmeralda852456#&')
    DGB_URL_LOGIN = os.getenv('DGB_URL_LOGIN', 'http://sistemadgb.4pu.com:90/dgb/login.jsf')
    DGB_URL_ESTOQUE = os.getenv('DGB_URL_ESTOQUE', 'http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf')
    
    # Criar arquivo de produtos padrão se não existir
    if not os.path.exists('produtos.txt'):
        with open('produtos.txt', 'w') as f:
            f.write('13,14,15,16,17')
    
    # Criar diretórios de templates e static
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    # Log das configurações carregadas
    logger.info(f"Configurações carregadas: Usuário={DGB_USUARIO}, URL Login={DGB_URL_LOGIN}, URL Estoque={DGB_URL_ESTOQUE}")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)