# app.py - SCRAPER INTELIGENTE PARA QUALQUER PRODUTO - VERSÃO CORRIGIDA E TESTADA
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
            
            # Aguardar resultados - aumentar tempo para carregamento
            time.sleep(8)
            
            # Verificar se há resultados
            try:
                self.take_screenshot(f"resultados_{produto_codigo}")
                
                # Extrair dados da página usando método DIRETO
                dados = self.extract_stock_data_direto(produto_codigo)
                
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
                        # Tentar método alternativo
                        dados_alternativo = self.extract_stock_data_alternativo(produto_codigo)
                        if dados_alternativo:
                            return {
                                'success': True,
                                'codigo': produto_codigo,
                                'situacao': situacao,
                                'dados': dados_alternativo,
                                'timestamp': datetime.now().isoformat(),
                                'total_registros': len(dados_alternativo)
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
    
    def extract_stock_data_direto(self, produto_codigo):
        """Extrai dados DIRETAMENTE da página - método PRINCIPAL"""
        dados_estruturados = []
        
        try:
            logger.info(f"Extraindo dados DIRETOS para produto {produto_codigo}...")
            
            # Obter o HTML da página
            html_content = self.driver.page_source
            
            # Salvar HTML para debug
            debug_file = os.path.join(LOG_FOLDER, f"debug_html_{produto_codigo}_{datetime.now().strftime('%H%M%S')}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"HTML salvo para debug: {debug_file}")
            
            # Usar BeautifulSoup para parsear
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # PROCURAR OS DADOS DE FORMA DIRETA
            # Procurar por padrões específicos na página
            
            # Método 1: Procurar por div com id 'estoquePrevisaoList'
            lista_div = soup.find('div', id='estoquePrevisaoList')
            
            if lista_div:
                logger.info("Encontrada div 'estoquePrevisaoList'")
                # Extrair todo o texto
                texto_completo = lista_div.get_text(separator='\n', strip=True)
                logger.info(f"Texto extraído ({len(texto_completo)} caracteres)")
                
                # Processar o texto
                dados = self.processar_texto_direto(texto_completo, produto_codigo)
                if dados:
                    dados_estruturados.extend(dados)
            else:
                logger.warning("Div 'estoquePrevisaoList' não encontrada")
            
            # Método 2: Procurar por todas as divs que podem conter dados
            if not dados_estruturados:
                all_divs = soup.find_all('div')
                for div in all_divs:
                    text = div.get_text(strip=True)
                    if text and re.search(r'^\d{6}\s+[A-Z]', text):
                        # Pode ser um produto
                        logger.info(f"Encontrado possível produto: {text[:50]}...")
            
            # Método 3: Tentar extrair por tabelas
            if not dados_estruturados:
                dados_tabela = self.extract_from_tables(soup, produto_codigo)
                if dados_tabela:
                    dados_estruturados.extend(dados_tabela)
            
            # Método 4: Último recurso - usar JavaScript para obter texto visível
            if not dados_estruturados:
                try:
                    # Executar JavaScript para obter texto visível
                    script = """
                    var elementos = document.querySelectorAll('div, span, td, tr');
                    var textos = [];
                    for (var i = 0; i < elementos.length; i++) {
                        var texto = elementos[i].innerText.trim();
                        if (texto && texto.length > 10) {
                            textos.push(texto);
                        }
                    }
                    return textos.join('\\n\\n');
                    """
                    texto_js = self.driver.execute_script(script)
                    if texto_js and len(texto_js) > 100:
                        dados_js = self.processar_texto_direto(texto_js, produto_codigo)
                        if dados_js:
                            dados_estruturados.extend(dados_js)
                except Exception as e:
                    logger.error(f"Erro no JavaScript: {e}")
            
            logger.info(f"Extraídos {len(dados_estruturados)} registros no total")
            
        except Exception as e:
            logger.error(f"Erro na extração direta: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
        
        return dados_estruturados
    
    def processar_texto_direto(self, texto, produto_codigo):
        """Processa texto diretamente extraído da página"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Dividir em linhas
            linhas = texto.split('\n')
            
            logger.info(f"Processando {len(linhas)} linhas de texto")
            
            i = 0
            while i < len(linhas):
                linha = linhas[i].strip()
                
                # Procurar por padrão de produto (6 dígitos seguido de texto)
                if re.match(r'^\d{6}\s+[A-Za-z]', linha):
                    logger.info(f"Encontrado produto na linha {i}: {linha[:50]}...")
                    
                    # Esta é a linha do produto
                    linha_produto = linha
                    
                    # Coletar informações seguintes
                    linhas_info = []
                    j = i + 1
                    while j < len(linhas) and j < i + 10:  # Limitar busca
                        linha_info = linhas[j].strip()
                        
                        # Parar se encontrar próxima data ou "Pronta entrega"
                        if re.match(r'^\d{2}/\d{2}/\d{4}$', linha_info) or linha_info.lower() == 'pronta entrega':
                            break
                        
                        if linha_info:
                            linhas_info.append(linha_info)
                        
                        j += 1
                    
                    # Combinar descrição
                    descricao_completa = linha_produto
                    if linhas_info:
                        descricao_completa += ' ' + ' '.join(linhas_info)
                    
                    # Agora procurar por datas e valores
                    k = i + 1 + len(linhas_info)
                    while k < len(linhas) and k < i + 20:  # Limitar busca
                        linha_atual = linhas[k].strip()
                        
                        # Se é "Pronta entrega" ou data
                        if linha_atual.lower() == 'pronta entrega' or re.match(r'^\d{2}/\d{2}/\d{4}$', linha_atual):
                            previsao = linha_atual
                            
                            # Procurar valores nas próximas linhas
                            if k + 1 < len(linhas):
                                linha_valores = linhas[k + 1].strip()
                                
                                # Tentar extrair 3 valores numéricos
                                valores = re.findall(r'[\d.,]+', linha_valores)
                                
                                if len(valores) >= 3:
                                    estoque = self.formatar_valor(valores[0])
                                    pedidos = self.formatar_valor(valores[1])
                                    disponivel = self.formatar_valor(valores[2])
                                    
                                    # Criar registro
                                    registro = [
                                        str(produto_codigo).lstrip('0'),
                                        timestamp,
                                        descricao_completa,
                                        previsao,
                                        estoque,
                                        pedidos,
                                        disponivel
                                    ]
                                    
                                    dados.append(registro)
                                    logger.info(f"Registro extraído: {produto_codigo} - {previsao} - Estoque: {estoque}")
                                    
                                    k += 2  # Pular linha de valores
                                    continue
                        
                        k += 1
                    
                    # Avançar i para continuar busca
                    i = j
                else:
                    i += 1
            
            logger.info(f"Processados {len(dados)} registros do texto")
            
        except Exception as e:
            logger.error(f"Erro no processamento direto: {e}")
        
        return dados
    
    def extract_stock_data_alternativo(self, produto_codigo):
        """Método alternativo de extração - mais agressivo"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            logger.info("Tentando método alternativo de extração...")
            
            # Obter TODO o texto da página
            texto_completo = self.driver.find_element(By.TAG_NAME, 'body').text
            
            # Procurar padrões específicos
            # Padrão: código do produto (6 dígitos) seguido de descrição
            padrao_produto = re.compile(r'(\d{6})\s+([A-Za-z\s]+?)(?=\s+\d{3}|$)')
            
            # Procurar por blocos de produto
            linhas = texto_completo.split('\n')
            
            for i in range(len(linhas)):
                linha = linhas[i].strip()
                
                # Se linha contém o código do produto que estamos procurando
                if str(produto_codigo) in linha and re.search(r'[A-Za-z]{3,}', linha):
                    logger.info(f"Possível linha de produto encontrada: {linha[:100]}")
                    
                    # Tentar extrair informações deste bloco
                    bloco_info = self.extrair_bloco_produto(linhas, i, produto_codigo, timestamp)
                    if bloco_info:
                        dados.extend(bloco_info)
        
        except Exception as e:
            logger.error(f"Erro no método alternativo: {e}")
        
        return dados
    
    def extrair_bloco_produto(self, linhas, inicio, produto_codigo, timestamp):
        """Extrai informações de um bloco de produto específico"""
        dados_bloco = []
        
        try:
            # Coletar até 15 linhas a partir do início
            bloco = []
            for j in range(inicio, min(inicio + 15, len(linhas))):
                bloco.append(linhas[j].strip())
            
            # Procurar por "Pronta entrega" e datas
            for k in range(len(bloco)):
                item = bloco[k]
                
                if item.lower() == 'pronta entrega' or re.match(r'^\d{2}/\d{2}/\d{4}$', item):
                    previsao = item
                    
                    # Procurar valores nas próximas 3 linhas
                    if k + 3 < len(bloco):
                        # Tentar encontrar linha com 3 valores numéricos
                        for l in range(k + 1, min(k + 4, len(bloco))):
                            linha_valores = bloco[l]
                            valores = re.findall(r'[\d.,]+', linha_valores)
                            
                            if len(valores) >= 3:
                                estoque = self.formatar_valor(valores[0])
                                pedidos = self.formatar_valor(valores[1])
                                disponivel = self.formatar_valor(valores[2])
                                
                                # Construir descrição (linhas anteriores)
                                descricao_parts = []
                                for m in range(max(0, k - 3), k):
                                    if bloco[m] and bloco[m] != previsao:
                                        descricao_parts.append(bloco[m])
                                
                                descricao = ' '.join(descricao_parts) if descricao_parts else f"Produto {produto_codigo}"
                                
                                registro = [
                                    str(produto_codigo).lstrip('0'),
                                    timestamp,
                                    descricao,
                                    previsao,
                                    estoque,
                                    pedidos,
                                    disponivel
                                ]
                                
                                dados_bloco.append(registro)
                                break
        
        except Exception as e:
            logger.error(f"Erro ao extrair bloco: {e}")
        
        return dados_bloco
    
    def extract_from_tables(self, soup, produto_codigo):
        """Tenta extrair dados de tabelas"""
        dados = []
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            # Procurar por tabelas
            tables = soup.find_all('table')
            logger.info(f"Encontradas {len(tables)} tabelas")
            
            for table in tables:
                # Extrair texto da tabela
                table_text = table.get_text(separator=' ', strip=True)
                
                # Se a tabela contém o código do produto
                if str(produto_codigo) in table_text:
                    # Processar linhas da tabela
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        cell_texts = [cell.get_text(strip=True) for cell in cells]
                        
                        # Procurar por valores numéricos
                        for text in cell_texts:
                            if re.search(r'[\d.,]+\s+[\d.,]+\s+[\d.,]+', text):
                                # Possível linha com valores
                                valores = re.findall(r'[\d.,]+', text)
                                if len(valores) >= 3:
                                    # Tentar encontrar descrição nas células anteriores
                                    descricao = f"Produto {produto_codigo}"
                                    
                                    # Determinar previsão (data ou "Pronta entrega")
                                    previsao = "Pronta entrega"
                                    for cell_text in cell_texts:
                                        if re.match(r'^\d{2}/\d{2}/\d{4}$', cell_text):
                                            previsao = cell_text
                                            break
                                    
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
            logger.error(f"Erro na extração de tabelas: {e}")
        
        return dados
    
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
            
            logger.error("Nenhuma estratégia encontrou o botão Pesquisar")
            return False
            
        except Exception as e:
            logger.error(f"Erro ao clicar no botão Pesquisar: {e}")
            return False
    
    def close(self):
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver fechado")
            except:
                pass

# Funções auxiliares
def salvar_csv_estruturado(dados, produto_codigo, situacao, tipo='individual'):
    """Salva os dados em um arquivo CSV"""
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if tipo == 'individual':
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
                        # Validar básico
                        if linha[0] and linha[3]:  # artigo e previsão
                            writer.writerow(linha)
                            registros_validos += 1
            
            logger.info(f"✅ CSV salvo: {filepath} ({registros_validos} registros)")
            
            # Logar amostra
            if dados and registros_validos > 0:
                logger.info(f"📄 Amostra do arquivo {filename}:")
                for i, linha in enumerate(dados[:3]):
                    logger.info(f"  Linha {i}: {linha}")
            
            return filename
        else:
            # Consolidado
            filename = f"consolidado_{timestamp}.csv"
            filepath = os.path.join(CONSOLIDATED_FOLDER, filename)
            
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                
                if dados and len(dados) > 0:
                    cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                                'Previsão', 'Estoque', 'Pedidos', 'Disponível']
                    writer.writerow(cabecalho)
                    
                    for linha in dados:
                        if len(linha) == 7:
                            writer.writerow(linha)
            
            logger.info(f"✅ CSV consolidado salvo: {filepath}")
            return filename
            
    except Exception as e:
        logger.error(f"❌ Erro ao salvar CSV: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

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
            
            # Pesquisar produto com situação TINTO
            resultado = scraper.search_product(produto, "TINTO")
            
            if resultado['success']:
                if resultado.get('dados'):
                    dados = resultado['dados']
                    
                    if dados:
                        # Salvar CSV individual
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
        logger.info(f"Status final: {scraping_status}")

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

@app.route('/download/csv/<filename>')
def download_csv(filename):
    """Download de arquivo CSV"""
    try:
        return send_from_directory(CSV_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return f"Erro ao baixar arquivo: {str(e)}", 404

@app.route('/api/debug/html')
def debug_html():
    """Retorna HTML da página atual para debug"""
    try:
        scraper = DGBScraper(headless=False)
        scraper.login()
        scraper.driver.get(scraper.url_estoque)
        time.sleep(3)
        
        html = scraper.driver.page_source
        scraper.close()
        
        # Salvar para arquivo
        debug_file = os.path.join(LOG_FOLDER, f"debug_html_{datetime.now().strftime('%H%M%S')}.html")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(html)
        
        return jsonify({
            'success': True,
            'file': debug_file,
            'preview': html[:1000] + '...' if len(html) > 1000 else html
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

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