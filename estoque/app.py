# app.py - VERSÃO COM PARÂMETROS PRODUTO E SITUAÇÃO CORRIGIDA
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

# Configurações do sistema DGB
DGB_USUARIO = os.getenv('DGB_USUARIO', 'tiago')
DGB_SENHA = os.getenv('DGB_SENHA', 'Esmeralda852456#&')
DGB_URL_LOGIN = os.getenv('DGB_URL_LOGIN', 'http://sistemadgb.4pu.com:90/dgb/login.jsf')
DGB_URL_ESTOQUE = os.getenv('DGB_URL_ESTOQUE', 'http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf')

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
                
                # Extrair dados da página
                dados = self.extract_stock_data_corrigido(produto_codigo, situacao)
                
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
    
    def extract_stock_data_corrigido(self, produto_codigo, situacao):
        """Extrai dados da tabela de estoque - VERSÃO COMPLETAMENTE CORRIGIDA"""
        dados_estruturados = []
        
        try:
            logger.info(f"Extraindo dados para produto {produto_codigo}, situação {situacao}...")
            
            # Tirar screenshot para debug
            self.take_screenshot(f"extraindo_dados_{produto_codigo}")
            
            # Primeiro, extrair informações básicas da página
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            logger.debug(f"Texto da página (primeiros 500 chars): {page_text[:500]}")
            
            # Extrair dados usando múltiplas estratégias
            dados = self.extract_data_multiple_strategies(page_text, produto_codigo, situacao)
            
            if dados:
                dados_estruturados.extend(dados)
                logger.info(f"Extraídos {len(dados)} registros para produto {produto_codigo}")
            else:
                # Se não extraiu dados, tentar método direto
                logger.warning("Método principal não extraiu dados, tentando método alternativo...")
                dados_alternativos = self.extract_data_direct_method(produto_codigo, situacao)
                if dados_alternativos:
                    dados_estruturados.extend(dados_alternativos)
                    logger.info(f"Extraídos {len(dados_alternativos)} registros (método alternativo)")
            
            # Se ainda não tem dados, tentar última estratégia
            if not dados_estruturados:
                logger.warning("Nenhum dado extraído, tentando última estratégia...")
                dados_ultima = self.extract_data_last_resort(produto_codigo, situacao)
                if dados_ultima:
                    dados_estruturados.extend(dados_ultima)
            
        except Exception as e:
            logger.error(f"Erro na extração: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        return dados_estruturados
    
    def extract_data_multiple_strategies(self, page_text, produto_codigo, situacao):
        """Extrai dados usando múltiplas estratégias"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Normalizar texto
            page_text = page_text.replace('\n', ' ').replace('\t', ' ')
            page_text = ' '.join(page_text.split())
            
            # Extrair informações do produto
            produto_info = self.extract_product_info(page_text, produto_codigo)
            
            # Procurar por "Pronta entrega" e datas
            # Dividir texto em seções
            sections = self.split_into_sections(page_text)
            
            for section in sections:
                if section and len(section) > 20:
                    # Processar seção
                    registros = self.process_section(section, produto_info, timestamp)
                    if registros:
                        dados.extend(registros)
            
        except Exception as e:
            logger.error(f"Erro em extract_data_multiple_strategies: {e}")
        
        return dados
    
    def extract_product_info(self, page_text, produto_codigo):
        """Extrai informações do produto do texto da página"""
        info = {
            'artigo': str(produto_codigo).zfill(6),
            'descricao_completa': f"0000{produto_codigo} PRODUTO {produto_codigo} 001 TINTO / 00000 LISO / 00000 Padrao",
            'cor': "NÃO IDENTIFICADA",
            'cor_codigo': "00000"
        }
        
        try:
            # Procurar por padrão de produto: código + nome
            match_produto = re.search(r'(\d{6})\s+([A-Z][A-Z\s]+?)(?=\s+\d{3}|$)', page_text)
            if match_produto:
                artigo = match_produto.group(1)
                nome = match_produto.group(2).strip()
                
                # Procurar cor
                match_cor = re.search(r'/\s*(\d{5})\s+(\d+)\s*-\s*([A-Z\s]+?)(?=\s+\d{5}|00000|$)', page_text)
                
                if match_cor:
                    cor_codigo = match_cor.group(1)
                    cor_numero = match_cor.group(2)
                    cor_nome = match_cor.group(3).strip()
                    
                    info['artigo'] = artigo
                    info['descricao_completa'] = f"{artigo} {nome} 001 TINTO / {cor_codigo} {cor_numero} - {cor_nome} 00000 LISO / 00000 Padrao"
                    info['cor'] = f"{cor_numero} - {cor_nome}"
                    info['cor_codigo'] = cor_codigo
                else:
                    info['artigo'] = artigo
                    info['descricao_completa'] = f"{artigo} {nome} 001 TINTO / 00000 LISO / 00000 Padrao"
        
        except Exception as e:
            logger.debug(f"Erro ao extrair info do produto: {e}")
        
        return info
    
    def split_into_sections(self, text):
        """Divide o texto em seções para processamento"""
        sections = []
        
        try:
            # Dividir por padrões comuns
            split_patterns = [
                r'Pronta entrega',
                r'\d{2}/\d{2}/\d{4}',
                r'\b\d{6}\b'
            ]
            
            current_section = ""
            lines = text.split('  ')  # Separar por múltiplos espaços
            
            for line in lines:
                line = line.strip()
                if line:
                    # Se a linha começa com padrão importante, iniciar nova seção
                    if any(re.match(pattern, line) for pattern in split_patterns):
                        if current_section:
                            sections.append(current_section)
                        current_section = line
                    else:
                        current_section += " " + line
            
            if current_section:
                sections.append(current_section)
            
        except Exception as e:
            logger.error(f"Erro ao dividir em seções: {e}")
        
        return sections if sections else [text]
    
    def process_section(self, section, produto_info, timestamp):
        """Processa uma seção do texto extraído"""
        registros = []
        
        try:
            # Corrigir formatação de números
            section = self.corrigir_formatacao_numeros(section)
            
            # Procurar por "Pronta entrega"
            if 'Pronta entrega' in section:
                registro = self.create_pronta_entrega_record(section, produto_info, timestamp)
                if registro:
                    registros.append(registro)
            
            # Procurar por datas futuras
            datas = re.findall(r'\d{2}/\d{2}/\d{4}', section)
            for data in datas:
                registro = self.create_future_date_record(section, data, produto_info, timestamp)
                if registro:
                    registros.append(registro)
        
        except Exception as e:
            logger.error(f"Erro ao processar seção: {e}")
        
        return registros
    
    def corrigir_formatacao_numeros(self, texto):
        """Corrige formatação dos números no texto"""
        try:
            # Corrigir números com espaço: "16.605 30" -> "16.605,30"
            texto = re.sub(r'(\d{1,3}(?:\.\d{3})+)\s+(\d{2})(?=\s|$|[^\d])', r'\1,\2', texto)
            
            # Corrigir números simples: "100 60" -> "100,60"
            texto = re.sub(r'(\b\d{1,3})\s+(\d{2}\b)(?=\s|$|[^\d])', r'\1,\2', texto)
            
            # Normalizar "Pronta entrega"
            texto = re.sub(r'Pronta\s+entrega', 'Pronta entrega', texto, flags=re.IGNORECASE)
            
            # Normalizar datas
            texto = re.sub(r'(\d{2})\s*/\s*(\d{2})\s*/\s*(\d{4})', r'\1/\2/\3', texto)
            
            # Remover múltiplos espaços
            texto = ' '.join(texto.split())
            
        except Exception as e:
            logger.debug(f"Erro na correção de números: {e}")
        
        return texto
    
    def create_pronta_entrega_record(self, section, produto_info, timestamp):
        """Cria registro para 'Pronta entrega'"""
        try:
            # Encontrar números após "Pronta entrega"
            pattern = r'Pronta entrega\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)'
            match = re.search(pattern, section)
            
            if match:
                estoque = match.group(1)
                pedidos = match.group(2)
                disponivel = match.group(3)
                
                # Garantir formatação correta
                estoque = estoque.replace(' ', '').strip()
                pedidos = pedidos.replace(' ', '').strip()
                disponivel = disponivel.replace(' ', '').strip()
                
                registro = [
                    produto_info['artigo'],
                    timestamp,
                    produto_info['descricao_completa'],
                    'Pronta entrega',
                    estoque,
                    pedidos,
                    disponivel
                ]
                
                logger.debug(f"Registro Pronta entrega: {registro}")
                return registro
        
        except Exception as e:
            logger.error(f"Erro ao criar registro Pronta entrega: {e}")
        
        return None
    
    def create_future_date_record(self, section, data, produto_info, timestamp):
        """Cria registro para data futura"""
        try:
            # Encontrar números após a data
            pattern = re.escape(data) + r'\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)'
            match = re.search(pattern, section)
            
            if match:
                estoque = match.group(1)
                pedidos = match.group(2)
                disponivel = match.group(3)
                
                # Garantir formatação correta
                estoque = estoque.replace(' ', '').strip()
                pedidos = pedidos.replace(' ', '').strip()
                disponivel = disponivel.replace(' ', '').strip()
                
                registro = [
                    produto_info['artigo'],
                    timestamp,
                    produto_info['descricao_completa'],
                    data,
                    estoque,
                    pedidos,
                    disponivel
                ]
                
                logger.debug(f"Registro data {data}: {registro}")
                return registro
        
        except Exception as e:
            logger.error(f"Erro ao criar registro data {data}: {e}")
        
        return None
    
    def extract_data_direct_method(self, produto_codigo, situacao):
        """Método alternativo de extração de dados"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Usar JavaScript para extrair tabelas
            js_script = """
            function extractTableData() {
                var resultados = [];
                var tables = document.getElementsByTagName('table');
                
                for (var i = 0; i < tables.length; i++) {
                    var rows = tables[i].getElementsByTagName('tr');
                    
                    for (var j = 0; j < rows.length; j++) {
                        var cells = rows[j].getElementsByTagName('td');
                        if (cells.length >= 4) {
                            var rowData = [];
                            for (var k = 0; k < cells.length; k++) {
                                rowData.push(cells[k].textContent.trim());
                            }
                            resultados.push(rowData.join(' | '));
                        }
                    }
                }
                return resultados;
            }
            return extractTableData();
            """
            
            rows = self.driver.execute_script(js_script)
            
            if rows:
                for row in rows:
                    if len(row) > 50:  # Linha com dados
                        # Processar a linha
                        registro = self.process_table_row(row, produto_codigo, timestamp)
                        if registro:
                            dados.append(registro)
        
        except Exception as e:
            logger.error(f"Erro no método direto: {e}")
        
        return dados
    
    def process_table_row(self, row_text, produto_codigo, timestamp):
        """Processa uma linha da tabela"""
        try:
            # Simplificar: buscar padrões comuns
            # Exemplo: "Pronta entrega 16.605,30 16.605,30 0,00"
            match_pronta = re.search(r'Pronta entrega\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)', row_text)
            if match_pronta:
                return [
                    str(produto_codigo).zfill(6),
                    timestamp,
                    f"0000{produto_codigo} PRODUTO {produto_codigo} 001 TINTO / 00000 LISO / 00000 Padrao",
                    'Pronta entrega',
                    match_pronta.group(1),
                    match_pronta.group(2),
                    match_pronta.group(3)
                ]
            
            # Data futura: "19/01/2026 14.766,10 8.044,70 6.721,40"
            match_data = re.search(r'(\d{2}/\d{2}/\d{4})\s+([\d.,]+)\s+([\d.,]+)\s+([\d.,]+)', row_text)
            if match_data:
                return [
                    str(produto_codigo).zfill(6),
                    timestamp,
                    f"0000{produto_codigo} PRODUTO {produto_codigo} 001 TINTO / 00000 LISO / 00000 Padrao",
                    match_data.group(1),
                    match_data.group(2),
                    match_data.group(3),
                    match_data.group(4)
                ]
        
        except Exception as e:
            logger.error(f"Erro ao processar linha da tabela: {e}")
        
        return None
    
    def extract_data_last_resort(self, produto_codigo, situacao):
        """Última estratégia de extração"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Extrair texto completo
            full_text = self.driver.find_element(By.TAG_NAME, "body").text
            full_text = full_text.replace('\n', ' ').replace('\t', ' ')
            full_text = ' '.join(full_text.split())
            
            # Buscar padrões diretos
            # Padrão 1: "Pronta entrega" seguido de 3 números
            pattern1 = r'Pronta entrega\D*?(\d[\d.,]*\d)\D*?(\d[\d.,]*\d)\D*?(\d[\d.,]*\d)'
            matches1 = re.findall(pattern1, full_text, re.IGNORECASE)
            
            for match in matches1:
                dados.append([
                    str(produto_codigo).zfill(6),
                    timestamp,
                    f"0000{produto_codigo} PRODUTO {produto_codigo} 001 {situacao} / 00000 LISO / 00000 Padrao",
                    'Pronta entrega',
                    match[0].replace(' ', ''),
                    match[1].replace(' ', ''),
                    match[2].replace(' ', '')
                ])
            
            # Padrão 2: Data seguida de 3 números
            pattern2 = r'(\d{2}/\d{2}/\d{4})\D*?(\d[\d.,]*\d)\D*?(\d[\d.,]*\d)\D*?(\d[\d.,]*\d)'
            matches2 = re.findall(pattern2, full_text)
            
            for match in matches2:
                dados.append([
                    str(produto_codigo).zfill(6),
                    timestamp,
                    f"0000{produto_codigo} PRODUTO {produto_codigo} 001 {situacao} / 00000 LISO / 00000 Padrao",
                    match[0],
                    match[1].replace(' ', ''),
                    match[2].replace(' ', ''),
                    match[3].replace(' ', '')
                ])
        
        except Exception as e:
            logger.error(f"Erro na última estratégia: {e}")
        
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
            filename = f"produto_{produto_codigo}_{situacao}_{timestamp}.csv"
            filepath = os.path.join(CSV_FOLDER, filename)
            
            # Cabeçalho correto
            cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                        'Previsão', 'Estoque', 'Pedidos', 'Disponível']
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                # Escrever cabeçalho
                writer.writerow(cabecalho)
                
                # Escrever dados
                for linha in dados:
                    if len(linha) == 7:  # Verificar se tem todas as colunas
                        # Garantir que valores numéricos estão corretos
                        linha = [str(item).strip() for item in linha]
                        writer.writerow(linha)
            
            logger.info(f"✅ CSV salvo: {filepath}")
            
            # Logar amostra
            if dados:
                logger.info(f"📄 Amostra do arquivo {filename} (primeiras 3 linhas):")
                for i, linha in enumerate(dados[:3]):
                    logger.info(f"  Linha {i}: {linha}")
            
            return filename
            
        else:
            # Para arquivos consolidados
            filename = f"consolidado_{timestamp}.csv"
            filepath = os.path.join(CONSOLIDATED_FOLDER, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                if dados and len(dados) > 0:
                    # Usar o primeiro registro para determinar cabeçalho
                    if len(dados[0]) == 7:
                        cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                                    'Previsão', 'Estoque', 'Pedidos', 'Disponível']
                        writer.writerow(cabecalho)
                    
                    for linha in dados:
                        writer.writerow(linha)
            
            logger.info(f"✅ CSV consolidado salvo: {filepath}")
            return filename
            
    except Exception as e:
        logger.error(f"❌ Erro ao salvar CSV: {str(e)}")
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
                    # Salvar CSV individual
                    filename = salvar_csv_estruturado(resultado['dados'], produto, "TINTO")
                    resultado['arquivo'] = filename
                    resultado['situacao'] = "TINTO"
                    scraping_status['message'] = f'✅ Produto {produto} processado: {len(resultado["dados"])} registros'
                else:
                    scraping_status['message'] = f'⚠️ Produto {produto}: nenhum dado encontrado'
                    resultado['situacao'] = "TINTO"
                
                scraping_status['results'].append(resultado)
            else:
                scraping_status['message'] = f'❌ Erro no produto {produto}: {resultado.get("error", "Erro desconhecido")}'
            
            # Pausa entre requisições
            time.sleep(3)
        
        scraping_status['end_time'] = datetime.now().isoformat()
        scraping_status['message'] = '✅ Scraping concluído com sucesso!'
        
    except Exception as e:
        logger.error(f"❌ Erro na thread de scraping: {str(e)}")
        scraping_status['message'] = f'❌ Erro durante scraping: {str(e)}'
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
            if filename.endswith('.csv') or filename.endswith('.xlsx') or filename.endswith('.json'):
                filepath = os.path.join(CONSOLIDATED_FOLDER, filename)
                stats = os.stat(filepath)
                files.append({
                    'name': filename,
                    'size': stats.st_size,
                    'modified': datetime.fromtimestamp(stats.st_mtime).isoformat(),
                    'path': f'/download/consolidated/files/{filename}'
                })
        
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/consolidated/files/<filename>')
def download_consolidated_file(filename):
    """Baixa arquivo consolidado"""
    return send_from_directory('data/consolidated', filename, as_attachment=True)

@app.route('/download/csv/<filename>')
def download_csv(filename):
    """Baixa arquivo CSV"""
    return send_from_directory(CSV_FOLDER, filename, as_attachment=True)

@app.route('/api/test-login', methods=['POST'])
def test_login():
    """Testa o login"""
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

if __name__ == '__main__':
    if not os.path.exists('.env'):
        with open('.env', 'w') as f:
            f.write(f'''# Configurações DGB COMEX
DGB_USUARIO=tiago
DGB_SENHA=Esmeralda852456#&
DGB_URL_LOGIN=http://sistemadgb.4pu.com:90/dgb/login.jsf
DGB_URL_ESTOQUE=http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf
FLASK_SECRET_KEY=dgb-comex-scraper-secret-2024

# Configurações do Scraping
SCRAPING_DELAY=3
SCRAPING_TIMEOUT=30
SCRAPING_HEADLESS=False
''')
        logger.info("Arquivo .env criado com configurações padrão")
    
    load_dotenv()
    
    DGB_USUARIO = os.getenv('DGB_USUARIO', 'tiago')
    DGB_SENHA = os.getenv('DGB_SENHA', 'Esmeralda852456#&')
    DGB_URL_LOGIN = os.getenv('DGB_URL_LOGIN', 'http://sistemadgb.4pu.com:90/dgb/login.jsf')
    DGB_URL_ESTOQUE = os.getenv('DGB_URL_ESTOQUE', 'http://sistemadgb.4pu.com:90/dgb/estoquePrevisaoConsulta.jsf')
    
    if not os.path.exists('produtos.txt'):
        with open('produtos.txt', 'w') as f:
            f.write('13,14,15,16,17')
    
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('static/js', exist_ok=True)
    
    logger.info(f"Configurações carregadas. Sistema pronto.")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)