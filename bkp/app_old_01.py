# app.py - SCRAPER INTELIGENTE PARA QUALQUER PRODUTO
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
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(CONSOLIDATED_FOLDER, exist_ok=True)

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
                situacao_preenchida = self.fill_situacao_field(situacao)
                if not situacao_preenchida:
                    logger.warning(f"Não conseguiu preencher situação '{situacao}'")
            except Exception as e:
                logger.warning(f"Erro ao preencher situação: {e}")
            
            self.take_screenshot(f"antes_pesquisa_{produto_codigo}")
            
            # Encontrar e clicar no botão Pesquisar
            try:
                pesquisar_clicado = self.click_pesquisar_button()
                if not pesquisar_clicado:
                    logger.error("Botão Pesquisar não clicado")
                    return {
                        'success': False,
                        'codigo': produto_codigo,
                        'error': 'Botão Pesquisar não encontrado'
                    }
                
                logger.info("Botão Pesquisar clicado")
            except Exception as e:
                logger.error(f"Erro ao clicar no botão Pesquisar: {e}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Erro ao clicar em Pesquisar: {e}'
                }
            
            # Aguardar resultados
            time.sleep(5)
            
            # Verificar se há resultados
            try:
                self.take_screenshot(f"resultados_{produto_codigo}")
                
                # Extrair dados da página usando método inteligente
                dados = self.extract_stock_data_inteligente(produto_codigo, situacao)
                
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
                    # Verificar se há mensagem de "nenhum resultado"
                    page_source = self.driver.page_source.lower()
                    if "nenhum" in page_source or "não encontrado" in page_source or "no records" in page_source:
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
    
    def fill_situacao_field(self, situacao="TINTO"):
        """Preenche o campo de situação"""
        try:
            # Estratégia 1: Tentar por ID
            try:
                situacao_field = self.driver.find_element(By.ID, "situacao")
                situacao_field.clear()
                situacao_field.send_keys(situacao)
                logger.info(f"Situação '{situacao}' preenchida por ID")
                return True
            except:
                pass
            
            # Estratégia 2: Tentar por NAME
            try:
                situacao_field = self.driver.find_element(By.NAME, "situacao")
                situacao_field.clear()
                situacao_field.send_keys(situacao)
                logger.info(f"Situação '{situacao}' preenchida por NAME")
                return True
            except:
                pass
            
            # Estratégia 3: Tentar por XPath
            try:
                situacao_field = self.driver.find_element(By.XPATH, "//input[contains(@id, 'situacao') or contains(@name, 'situacao')]")
                situacao_field.clear()
                situacao_field.send_keys(situacao)
                logger.info(f"Situação '{situacao}' preenchida por XPath")
                return True
            except:
                pass
            
            # Estratégia 4: Tentar por label
            try:
                situacao_label = self.driver.find_element(By.XPATH, "//label[contains(text(), 'Situação')]")
                situacao_field = situacao_label.find_element(By.XPATH, "following-sibling::input")
                situacao_field.clear()
                situacao_field.send_keys(situacao)
                logger.info(f"Situação '{situacao}' preenchida por label")
                return True
            except:
                pass
            
            # Estratégia 5: Tentar dropdown select
            try:
                situacao_select = self.driver.find_element(By.CSS_SELECTOR, "select[name*='situacao']")
                select = Select(situacao_select)
                select.select_by_visible_text(situacao)
                logger.info(f"Situação '{situacao}' selecionada no dropdown")
                return True
            except:
                pass
            
            logger.warning(f"Não encontrou campo de situação para preencher '{situacao}'")
            return False
            
        except Exception as e:
            logger.warning(f"Erro ao preencher situação '{situacao}': {e}")
            return False
    
    def click_pesquisar_button(self):
        """Clica no botão Pesquisar"""
        try:
            # Estratégia 1: Botão por texto
            try:
                pesquisar_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Pesquisar') or contains(text(), 'PESQUISAR')]")
                pesquisar_button.click()
                return True
            except:
                pass
            
            # Estratégia 2: Input submit
            try:
                pesquisar_button = self.driver.find_element(By.XPATH, "//input[@type='submit' and contains(@value, 'Pesquisar')]")
                pesquisar_button.click()
                return True
            except:
                pass
            
            # Estratégia 3: Por ID específico
            try:
                pesquisar_button = self.driver.find_element(By.ID, "j_idt67")
                pesquisar_button.click()
                return True
            except:
                pass
            
            # Estratégia 4: Qualquer botão submit
            try:
                pesquisar_button = self.driver.find_element(By.CSS_SELECTOR, "input[type='submit']")
                pesquisar_button.click()
                return True
            except:
                pass
            
            # Estratégia 5: Qualquer botão
            try:
                pesquisar_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
                pesquisar_button.click()
                return True
            except:
                pass
            
            logger.error("Nenhuma estratégia encontrou o botão Pesquisar")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao clicar no botão Pesquisar: {e}")
            return False
    
    def extract_stock_data_inteligente(self, produto_codigo, situacao):
        """Extrai dados da tabela de estoque - MÉTODO INTELIGENTE PARA QUALQUER PRODUTO"""
        dados_estruturados = []
        
        try:
            logger.info(f"Extraindo dados inteligente para produto {produto_codigo}, situação {situacao}...")
            
            # Tirar screenshot para debug
            self.take_screenshot(f"extraindo_dados_{produto_codigo}")
            
            # Obter o HTML da página
            html_content = self.driver.page_source
            
            # Usar BeautifulSoup para parsear
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Obter todo o texto da página
            full_text = soup.get_text()
            
            # Processar o texto para extrair dados
            dados = self.process_page_text_inteligente(full_text, produto_codigo)
            
            if dados:
                dados_estruturados.extend(dados)
                logger.info(f"Extraídos {len(dados)} registros para produto {produto_codigo}")
            else:
                logger.warning("Nenhum dado extraído com método inteligente")
            
        except Exception as e:
            logger.error(f"Erro na extração inteligente: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        return dados_estruturados
    
    def process_page_text_inteligente(self, text, produto_codigo):
        """Processa o texto da página de forma inteligente"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Dividir o texto em linhas
            lines = text.split('\n')
            
            current_product_info = None
            current_color_info = None
            current_design_info = None
            current_variant_info = None
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                
                # Ignorar linhas vazias ou muito curtas
                if not line or len(line) < 3:
                    i += 1
                    continue
                
                # Verificar se é uma linha de cabeçalho de produto (começa com 6 dígitos)
                if re.match(r'^\d{6}\s+[A-Z]', line):
                    # Esta é uma nova linha de produto
                    current_product_info = line
                    
                    # Verificar próxima linha para informações de cor
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if 'TINTO' in next_line or re.search(r'/\s*\d{5}\s+\d+\s*-\s*[A-Z]', next_line):
                            current_color_info = next_line
                            i += 1
                    
                    # Verificar linha seguinte para desenho/variante
                    if i + 1 < len(lines):
                        next_line = lines[i + 1].strip()
                        if 'LISO' in next_line or 'Padrao' in next_line or re.match(r'^\d{5}\s+', next_line):
                            current_design_info = next_line
                            i += 1
                    
                    # Agora processar as linhas seguintes que contêm dados
                    # Avançar para a próxima linha
                    i += 1
                    continue
                
                # Verificar se é "Pronta entrega"
                elif line.lower() == 'pronta entrega' or line.startswith('Pronta entrega'):
                    # As próximas 3 linhas são os números
                    if i + 3 < len(lines):
                        estoque_line = lines[i + 1].strip()
                        pedidos_line = lines[i + 2].strip()
                        disponivel_line = lines[i + 3].strip()
                        
                        # Formatar os números
                        estoque = self.format_number_inteligente(estoque_line)
                        pedidos = self.format_number_inteligente(pedidos_line)
                        disponivel = self.format_number_inteligente(disponivel_line)
                        
                        # Construir descrição completa
                        descricao_completa = self.build_full_description(
                            current_product_info, current_color_info, 
                            current_design_info, current_variant_info
                        )
                        
                        if descricao_completa and estoque and pedidos and disponivel:
                            registro = [
                                str(produto_codigo),
                                timestamp,
                                descricao_completa,
                                'Pronta entrega',
                                estoque,
                                pedidos,
                                disponivel
                            ]
                            dados.append(registro)
                        
                        i += 4  # Pular as 4 linhas (Pronta entrega + 3 números)
                        continue
                
                # Verificar se é uma data (formato DD/MM/YYYY)
                elif re.match(r'^\d{2}/\d{2}/\d{4}$', line):
                    date = line
                    
                    # As próximas 3 linhas são os números
                    if i + 3 < len(lines):
                        estoque_line = lines[i + 1].strip()
                        pedidos_line = lines[i + 2].strip()
                        disponivel_line = lines[i + 3].strip()
                        
                        # Formatar os números
                        estoque = self.format_number_inteligente(estoque_line)
                        pedidos = self.format_number_inteligente(pedidos_line)
                        disponivel = self.format_number_inteligente(disponivel_line)
                        
                        # Construir descrição completa
                        descricao_completa = self.build_full_description(
                            current_product_info, current_color_info, 
                            current_design_info, current_variant_info
                        )
                        
                        if descricao_completa and estoque and pedidos and disponivel:
                            registro = [
                                str(produto_codigo),
                                timestamp,
                                descricao_completa,
                                date,
                                estoque,
                                pedidos,
                                disponivel
                            ]
                            dados.append(registro)
                        
                        i += 4  # Pular as 4 linhas (data + 3 números)
                        continue
                
                # Avançar para próxima linha
                i += 1
        
        except Exception as e:
            logger.error(f"Erro no processamento inteligente: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        return dados
    
    def format_number_inteligente(self, num_str):
        """Formata número de forma inteligente"""
        try:
            # Remover espaços extras
            num_str = str(num_str).strip()
            
            # Se estiver vazio, retornar "0,00"
            if not num_str:
                return "0,00"
            
            # Remover caracteres não numéricos exceto ponto, vírgula e traço (para números negativos)
            clean_num = re.sub(r'[^\d.,\-]', '', num_str)
            
            # Se não tem ponto nem vírgula, adicionar ",00"
            if '.' not in clean_num and ',' not in clean_num:
                clean_num = clean_num + ",00"
            
            # Se tem múltiplos pontos, é formato brasileiro (1.234,56)
            if clean_num.count('.') > 1:
                # Garantir que a vírgula está no lugar certo
                if ',' not in clean_num:
                    # Último ponto vira vírgula
                    parts = clean_num.split('.')
                    clean_num = '.'.join(parts[:-1]) + ',' + parts[-1]
            
            return clean_num
        
        except Exception as e:
            logger.error(f"Erro ao formatar número {num_str}: {e}")
            return num_str
    
    def build_full_description(self, product_info, color_info, design_info, variant_info):
        """Constrói descrição completa do produto"""
        parts = []
        
        if product_info:
            parts.append(product_info.strip())
        
        if color_info:
            parts.append(color_info.strip())
        
        if design_info:
            parts.append(design_info.strip())
        
        if variant_info:
            parts.append(variant_info.strip())
        
        return ' '.join(parts) if parts else None
    
    def extract_data_direct_html(self):
        """Tenta extrair dados diretamente do HTML"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Encontrar todos os elementos que podem conter dados
            elements = self.driver.find_elements(By.XPATH, "//div | //tr | //td | //span")
            
            current_product_block = []
            in_product_block = False
            
            for element in elements:
                text = element.text.strip()
                if not text:
                    continue
                
                # Verificar se é início de um bloco de produto
                if re.match(r'^\d{6}\s+', text):
                    if current_product_block:
                        # Processar bloco anterior
                        block_data = self.process_product_block(current_product_block, timestamp)
                        if block_data:
                            dados.extend(block_data)
                    
                    # Iniciar novo bloco
                    current_product_block = [text]
                    in_product_block = True
                
                elif in_product_block:
                    current_product_block.append(text)
            
            # Processar último bloco
            if current_product_block:
                block_data = self.process_product_block(current_product_block, timestamp)
                if block_data:
                    dados.extend(block_data)
        
        except Exception as e:
            logger.error(f"Erro na extração direta HTML: {e}")
        
        return dados
    
    def process_product_block(self, block_lines, timestamp):
        """Processa um bloco de linhas de produto"""
        dados = []
        
        try:
            # Encontrar o código do produto (primeiros 6 dígitos da primeira linha)
            first_line = block_lines[0]
            match = re.search(r'(\d{6})', first_line)
            if match:
                produto_codigo = match.group(1)
            else:
                return dados  # Não encontrou código, pular
            
            # Reconstruir descrição completa
            descricao_parts = []
            i = 0
            
            while i < len(block_lines):
                line = block_lines[i]
                
                # Adicionar à descrição
                descricao_parts.append(line)
                
                # Verificar se próxima linha é "Pronta entrega"
                if i + 1 < len(block_lines) and 'Pronta entrega' in block_lines[i + 1]:
                    # Processar Pronta entrega
                    if i + 4 < len(block_lines):
                        descricao = ' '.join(descricao_parts)
                        estoque = self.format_number_inteligente(block_lines[i + 2])
                        pedidos = self.format_number_inteligente(block_lines[i + 3])
                        disponivel = self.format_number_inteligente(block_lines[i + 4])
                        
                        dados.append([
                            produto_codigo.lstrip('0'),
                            timestamp,
                            descricao,
                            'Pronta entrega',
                            estoque,
                            pedidos,
                            disponivel
                        ])
                        
                        i += 4  # Pular as 4 linhas
                
                # Verificar se é uma data
                elif re.match(r'^\d{2}/\d{2}/\d{4}$', line):
                    if i + 3 < len(block_lines):
                        date = line
                        descricao = ' '.join(descricao_parts[:-1])  # Excluir a data da descrição
                        estoque = self.format_number_inteligente(block_lines[i + 1])
                        pedidos = self.format_number_inteligente(block_lines[i + 2])
                        disponivel = self.format_number_inteligente(block_lines[i + 3])
                        
                        dados.append([
                            produto_codigo.lstrip('0'),
                            timestamp,
                            descricao,
                            date,
                            estoque,
                            pedidos,
                            disponivel
                        ])
                        
                        i += 3  # Pular as 3 linhas de números
                
                i += 1
        
        except Exception as e:
            logger.error(f"Erro ao processar bloco: {e}")
        
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
def salvar_csv_estruturado(dados, produto_codigo, situacao, tipo='individual'):
    """Salva os dados em um arquivo CSV com estrutura correta"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if tipo == 'individual':
            # Ajustar o código do produto
            artigo_codigo = str(produto_codigo)
            artigo_codigo = artigo_codigo.lstrip('0')
            if not artigo_codigo:
                artigo_codigo = str(produto_codigo)
            
            filename = f"produto_{artigo_codigo}_{situacao}_{timestamp}.csv"
            filepath = os.path.join(CSV_FOLDER, filename)
            
            # Cabeçalho correto
            cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                        'Previsão', 'Estoque', 'Pedidos', 'Disponível']
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                # Escrever cabeçalho
                writer.writerow(cabecalho)
                
                # Escrever dados
                registros_validos = 0
                for linha in dados:
                    if len(linha) == 7:  # Verificar se tem todas as colunas
                        # Validar os dados
                        if validar_registro_csv(linha):
                            # Garantir formatação correta
                            linha_formatada = []
                            for j, valor in enumerate(linha):
                                if valor is None:
                                    linha_formatada.append('')
                                else:
                                    valor_str = str(valor).strip()
                                    # Para números, garantir formato
                                    if j >= 4:  # Colunas numéricas
                                        valor_str = formatar_numero_csv(valor_str)
                                    linha_formatada.append(valor_str)
                            
                            writer.writerow(linha_formatada)
                            registros_validos += 1
                        else:
                            logger.warning(f"Registro inválido ignorado: {linha}")
                    else:
                        logger.warning(f"Linha com número incorreto de colunas: {len(linha)} -> {linha}")
            
            logger.info(f"✅ CSV salvo: {filepath} ({registros_validos} registros válidos)")
            
            # Logar amostra
            if dados and registros_validos > 0:
                logger.info(f"📄 Amostra do arquivo {filename}:")
                logger.info(f"  Cabeçalho: {cabecalho}")
                for i, linha in enumerate(dados[:3]):
                    if len(linha) == 7 and validar_registro_csv(linha):
                        logger.info(f"  Linha {i}: {linha}")
            
            return filename
            
        else:
            # Para arquivos consolidados
            filename = f"consolidado_{timestamp}.csv"
            filepath = os.path.join(CONSOLIDATED_FOLDER, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                if dados and len(dados) > 0:
                    # Usar cabeçalho padrão
                    cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                                'Previsão', 'Estoque', 'Pedidos', 'Disponível']
                    writer.writerow(cabecalho)
                    
                    registros_validos = 0
                    for linha in dados:
                        if len(linha) == 7 and validar_registro_csv(linha):
                            # Garantir formatação correta
                            linha_formatada = []
                            for j, valor in enumerate(linha):
                                if valor is None:
                                    linha_formatada.append('')
                                else:
                                    valor_str = str(valor).strip()
                                    if j >= 4:
                                        valor_str = formatar_numero_csv(valor_str)
                                    linha_formatada.append(valor_str)
                            
                            writer.writerow(linha_formatada)
                            registros_validos += 1
            
            logger.info(f"✅ CSV consolidado salvo: {filepath} ({registros_validos} registros)")
            return filename
            
    except Exception as e:
        logger.error(f"❌ Erro ao salvar CSV: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def formatar_numero_csv(num_str):
    """Formata número para CSV"""
    try:
        num_str = str(num_str).strip()
        
        # Se estiver vazio
        if not num_str:
            return "0,00"
        
        # Remover espaços
        num_str = num_str.replace(' ', '')
        
        # Se não tem vírgula, adicionar
        if ',' not in num_str:
            # Se tem ponto, último ponto vira vírgula
            if '.' in num_str:
                parts = num_str.split('.')
                if len(parts[-1]) == 2:  # Dois dígitos após o ponto
                    num_str = '.'.join(parts[:-1]) + ',' + parts[-1]
                else:
                    num_str = num_str + ',00'
            else:
                num_str = num_str + ',00'
        
        return num_str
    
    except Exception as e:
        logger.error(f"Erro ao formatar número CSV {num_str}: {e}")
        return num_str

def validar_registro_csv(registro):
    """Valida se um registro CSV é válido"""
    try:
        if len(registro) != 7:
            return False
        
        artigo = str(registro[0]).strip()
        previsao = str(registro[3]).strip()
        estoque = str(registro[4]).strip()
        pedidos = str(registro[5]).strip()
        disponivel = str(registro[6]).strip()
        
        # Verificar se artigo é válido
        if not artigo or not artigo.isdigit():
            return False
        
        # Verificar se previsão é válida
        if not previsao or (previsao != 'Pronta entrega' and not re.match(r'^\d{2}/\d{2}/\d{4}$', previsao)):
            return False
        
        # Verificar se valores numéricos são válidos
        for num in [estoque, pedidos, disponivel]:
            if not num:
                return False
            
            # Deve conter pelo menos um número
            if not re.search(r'\d', num):
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Erro na validação: {e}")
        return False

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
                f.write('13,14,15,16,17,19,20,23,24,27,28,29,30')
        
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
        if not scraper.login():
            scraping_status['message'] = 'Falha no login.'
            scraping_status['running'] = False
            return
        
        scraping_status['message'] = 'Login realizado! Iniciando consultas...'
        
        # Processar cada produto
        for i, produto in enumerate(produtos, 1):
            if not scraping_status['running']:
                break
                
            scraping_status['current'] = produto
            scraping_status['progress'] = int((i / len(produtos)) * 100)
            scraping_status['message'] = f'Processando produto {produto} ({i}/{len(produtos)})'
            
            # Pesquisar produto com situação TINTO
            resultado = scraper.search_product(produto, "TINTO")
            
            if resultado['success']:
                if resultado.get('dados'):
                    # Filtrar apenas registros válidos
                    dados_validos = []
                    for registro in resultado['dados']:
                        if len(registro) == 7 and validar_registro_csv(registro):
                            dados_validos.append(registro)
                    
                    if dados_validos:
                        # Salvar CSV individual
                        filename = salvar_csv_estruturado(dados_validos, produto, "TINTO")
                        resultado['arquivo'] = filename
                        resultado['situacao'] = "TINTO"
                        resultado['dados_validos'] = len(dados_validos)
                        scraping_status['message'] = f'✅ Produto {produto} processado: {len(dados_validos)} registros válidos'
                    else:
                        scraping_status['message'] = f'⚠️ Produto {produto}: nenhum registro válido encontrado'
                        resultado['situacao'] = "TINTO"
                else:
                    scraping_status['message'] = f'⚠️ Produto {produto}: nenhum dado encontrado'
                    resultado['situacao'] = "TINTO"
                
                scraping_status['results'].append(resultado)
            else:
                scraping_status['message'] = f'❌ Erro no produto {produto}: {resultado.get("error", "Erro desconhecido")}'
            
            # Pausa entre requisições
            time.sleep(2)
        
        scraping_status['end_time'] = datetime.now().isoformat()
        scraping_status['message'] = '✅ Scraping concluído com sucesso!'
        
    except Exception as e:
        logger.error(f"❌ Erro na thread de scraping: {str(e)}")
        scraping_status['message'] = f"❌ Erro durante scraping: {str(e)}"
    finally:
        if scraper:
            scraper.close()
        scraping_status['running'] = False
        scraping_status['end_time'] = scraping_status['end_time'] or datetime.now().isoformat()

# Rotas Flask (mantenha as mesmas rotas)
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
    try:
        from consolidator import consolidar_dados_estruturados
        
        resultado, mensagem = consolidar_dados_estruturados()
        
        if resultado:
            return jsonify({
                'success': True,
                'message': mensagem,
                'resultado': resultado,
                'arquivos': {
                    'csv': resultado.get('arquivo_csv'),
                    'excel': resultado.get('arquivo_excel'),
                    'json': f"resumo_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                },
                'estatisticas': {
                    'total_registros': resultado.get('total_registros', 0),
                    'total_estoque': resultado.get('total_estoque', 0),
                    'total_pedidos': resultado.get('total_pedidos', 0),
                    'total_disponivel': resultado.get('total_disponivel', 0),
                    'produtos_unicos': resultado.get('produtos_unicos', 0),
                    'cores_unicas': resultado.get('cores_unicas', 0),
                    'arquivos_processados': resultado.get('arquivos_processados', 0)
                }
            })
        else:
            return jsonify({
                'success': False,
                'message': mensagem
            }), 400
            
    except Exception as e:
        logger.error(f"Erro na consolidação: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Erro na consolidação: {str(e)}'
        }), 500

# ... (mantenha todas as outras rotas do código anterior)

if __name__ == '__main__':
    # Verificar se o arquivo .env existe
    if not os.path.exists('.env'):
        logger.error("❌ Arquivo .env não encontrado!")
        logger.info("📝 Por favor, crie um arquivo .env com as seguintes variáveis:")
        logger.info("   DGB_USUARIO=seu_usuario")
        logger.info("   DGB_SENHA=sua_senha")
        logger.info("   DGB_URL_LOGIN=http://sistemadgb.4pu.com:90/dgb/login.jsf")
        logger.info("   DGB_URL_ESTOQUE=http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf")
        logger.info("   FLASK_SECRET_KEY=sua_chave_secreta")
        logger.info("   SCRAPING_DELAY=2")
        logger.info("   SCRAPING_TIMEOUT=30")
        logger.info("   SCRAPING_HEADLESS=False")
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
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    logger.info("✅ Configurações carregadas. Sistema pronto.")
    logger.info(f"👤 Usuário: {os.getenv('DGB_USUARIO')}")
    logger.info(f"🔗 URL Login: {os.getenv('DGB_URL_LOGIN')}")
    
    # Verificar se existe arquivo de produtos
    if not os.path.exists('produtos.txt'):
        with open('produtos.txt', 'w') as f:
            f.write('13,14,15,16,17,19,20,23,24,27,28,29,30')
        logger.info("📝 Arquivo produtos.txt criado com valores padrão")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)