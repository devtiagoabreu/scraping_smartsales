# app.py - SCRAPER COM DEBUG, PARSER AVANÇADO E FULL PAGE SCREENSHOT
import os
import csv
import json
import time
import threading
import logging
import re
import base64
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
from PIL import Image
import io

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
FULLPAGE_SCREENSHOT_FOLDER = 'data/screenshots/fullpage'
CONSOLIDATED_FOLDER = 'data/consolidated'
DEBUG_FOLDER = 'data/debug'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)
os.makedirs(SCREENSHOT_FOLDER, exist_ok=True)
os.makedirs(FULLPAGE_SCREENSHOT_FOLDER, exist_ok=True)
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
    def __init__(self, headless=False, keep_open=False):
        self.headless = headless
        self.keep_open = keep_open  # Nova flag para manter aberto
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
        
        # Opções para manter aberto
        if self.keep_open:
            chrome_options.add_experimental_option("detach", True)
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.wait = WebDriverWait(self.driver, 30)
    
    def take_fullpage_screenshot(self, name):
        """
        Tira screenshot de toda a página (scroll screenshot) - similar ao GoFullPage
        Retorna o caminho do arquivo salvo
        """
        try:
            logger.info(f"Tirando screenshot fullpage: {name}")
            
            # Salvar posição original do scroll
            original_scroll_position = self.driver.execute_script("return window.pageYOffset;")
            
            # Obter dimensões da página
            total_height = self.driver.execute_script("return Math.max(document.body.scrollHeight, document.body.offsetHeight, document.documentElement.clientHeight, document.documentElement.scrollHeight, document.documentElement.offsetHeight);")
            viewport_height = self.driver.execute_script("return window.innerHeight;")
            
            # Calcular número de capturas necessárias
            total_slices = (total_height + viewport_height - 1) // viewport_height
            
            logger.info(f"Dimensões da página - Altura total: {total_height}, Viewport: {viewport_height}, Slices: {total_slices}")
            
            # Criar imagem combinada
            screenshot_list = []
            
            for slice_idx in range(total_slices):
                # Scroll para a posição
                scroll_position = slice_idx * viewport_height
                self.driver.execute_script(f"window.scrollTo(0, {scroll_position});")
                time.sleep(0.5)  # Esperar renderização
                
                # Tirar screenshot do slice
                screenshot = self.driver.get_screenshot_as_png()
                screenshot_list.append(screenshot)
                
                logger.debug(f"Slice {slice_idx + 1}/{total_slices} capturado (scroll: {scroll_position})")
            
            # Restaurar posição original do scroll
            self.driver.execute_script(f"window.scrollTo(0, {original_scroll_position});")
            
            # Combinar todas as screenshots
            if screenshot_list:
                # Converter PNG para Image objects
                images = []
                for screenshot_png in screenshot_list:
                    img = Image.open(io.BytesIO(screenshot_png))
                    images.append(img)
                
                # Calcular dimensões da imagem final
                final_width = images[0].width
                final_height = total_height
                
                # Criar imagem final
                final_image = Image.new('RGB', (final_width, final_height))
                
                # Colar cada slice
                current_y = 0
                for i, img in enumerate(images):
                    # Para o último slice, pode ser necessário cortar
                    if i == len(images) - 1:
                        remaining_height = total_height - (i * viewport_height)
                        if remaining_height < viewport_height:
                            img = img.crop((0, 0, final_width, remaining_height))
                    
                    final_image.paste(img, (0, current_y))
                    current_y += img.height
                
                # Salvar imagem
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{self.session_id}_{name}_FULLPAGE_{timestamp}.png"
                filepath = os.path.join(FULLPAGE_SCREENSHOT_FOLDER, filename)
                
                final_image.save(filepath, 'PNG', optimize=True, quality=95)
                
                logger.info(f"✅ Screenshot fullpage salvo: {filename} ({final_width}x{final_height})")
                
                # Também salvar uma miniatura
                thumbnail_path = os.path.join(FULLPAGE_SCREENSHOT_FOLDER, f"thumb_{filename}")
                thumbnail = final_image.copy()
                thumbnail.thumbnail((800, 800))
                thumbnail.save(thumbnail_path, 'PNG', optimize=True, quality=85)
                
                return filepath
            else:
                logger.error("Nenhum slice capturado")
                return None
                
        except Exception as e:
            logger.error(f"❌ Erro ao tirar screenshot fullpage: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    def take_screenshot(self, name):
        """Tira screenshot normal da viewport atual"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{self.session_id}_{name}_{timestamp}.png"
            filepath = os.path.join(SCREENSHOT_FOLDER, filename)
            self.driver.save_screenshot(filepath)
            logger.info(f"Screenshot normal salvo: {filename}")
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
            
            # Verificar se login foi bem sucedido
            current_url = self.driver.current_url
            if "login" in current_url or "erro" in current_url.lower():
                logger.error("Parece que o login falhou - ainda na página de login")
                self.take_screenshot("login_falhou")
                return False
            
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
            logger.info(f"Navegando para página de estoque: {self.url_estoque}")
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
                    self.take_screenshot("erro_pagina_estoque")
                    return False
                    
        except Exception as e:
            logger.error(f"Erro ao navegar para página de estoque: {str(e)}")
            return False
    
    def search_product(self, produto_codigo, situacao="TINTO", fullpage_screenshot=True):
        """Realiza pesquisa de um produto específico COM SITUAÇÃO"""
        try:
            logger.info(f"Pesquisando produto {produto_codigo}, situação {situacao}...")
            
            # Verificar se estamos na página correta
            if "estoquePrevisaoConsulta" not in self.driver.current_url:
                logger.warning("Não está na página de estoque, navegando...")
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
                self.take_screenshot("campo_produto_nao_encontrado")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Campo de produto não encontrado: {e}'
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
            
            # Tirar screenshot fullpage se solicitado
            fullpage_path = None
            if fullpage_screenshot:
                fullpage_path = self.take_fullpage_screenshot(f"resultados_{produto_codigo}")
            
            # Tirar screenshot normal também
            normal_screenshot = self.take_screenshot(f"resultados_{produto_codigo}")
            
            # OBTER HTML PARA DEBUG
            html_content = self.driver.page_source
            
            # SALVAR HTML PARA DEBUG
            debug_file = os.path.join(DEBUG_FOLDER, f"debug_html_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"✅ HTML salvo para debug: {debug_file}")
            
            # SALVAR TEXTO PARA DEBUG
            soup = BeautifulSoup(html_content, 'html.parser')
            texto_completo = soup.get_text(separator='\n')
            debug_text_file = os.path.join(DEBUG_FOLDER, f"debug_texto_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            with open(debug_text_file, 'w', encoding='utf-8') as f:
                f.write(texto_completo)
            logger.info(f"✅ Texto salvo para debug: {debug_text_file}")
            
            return {
                'success': True,
                'codigo': produto_codigo,
                'situacao': situacao,
                'arquivo_html': debug_file,
                'arquivo_texto': debug_text_file,
                'screenshot_normal': normal_screenshot,
                'screenshot_fullpage': fullpage_path,
                'timestamp': datetime.now().isoformat()
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
    
    def close(self):
        """Fecha o driver - apenas se não estiver marcado para manter aberto"""
        if self.driver and not self.keep_open:
            try:
                self.driver.quit()
                logger.info("Driver fechado")
            except:
                pass
        elif self.driver and self.keep_open:
            logger.info("Driver configurado para permanecer aberto")
    
    def keep_alive(self):
        """Mantém o navegador aberto (não faz nada, apenas para documentação)"""
        pass

# ============================================================================
# VARIÁVEIS GLOBAIS PARA SESSÕES PERSISTENTES
# ============================================================================

# Dicionário para armazenar sessões ativas
active_sessions = {}

def get_or_create_session(session_id=None, keep_open=True):
    """Obtém ou cria uma sessão persistente do scraper"""
    global active_sessions
    
    if session_id and session_id in active_sessions:
        scraper = active_sessions[session_id]
        # Verificar se o driver ainda está ativo
        try:
            # Tenta obter a URL atual para verificar se o driver está ativo
            scraper.driver.current_url
            logger.info(f"Reutilizando sessão existente: {session_id}")
            return scraper, session_id
        except:
            # Driver morreu, criar novo
            logger.info(f"Driver da sessão {session_id} morreu, criando novo...")
            del active_sessions[session_id]
    
    # Criar nova sessão COM KEEP_OPEN=True
    session_id = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    logger.info(f"Criando nova sessão: {session_id} (keep_open={keep_open})")
    scraper = DGBScraper(headless=False, keep_open=keep_open)
    active_sessions[session_id] = scraper
    
    # Limpar sessões antigas (manter apenas as últimas 3)
    if len(active_sessions) > 3:
        oldest_key = list(active_sessions.keys())[0]
        try:
            if not active_sessions[oldest_key].keep_open:
                active_sessions[oldest_key].close()
        except:
            pass
        del active_sessions[oldest_key]
        logger.info(f"Sessão antiga {oldest_key} removida")
    
    return scraper, session_id

# ============================================================================
# FUNÇÕES DE PARSING AVANÇADO
# ============================================================================

def formatar_valor_csv(valor_str):
    """Formata valor para CSV no padrão brasileiro"""
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
            elif len(decimal) > 2:
                decimal = decimal[:2]
            
            return f"{inteiro},{decimal}"
        else:
            valor_str = valor_str.replace('.', '')
            return f"{valor_str},00"
            
    except Exception as e:
        return "0,00"

def parse_html_avancado(html_content, produto_codigo):
    """Parser avançado baseado no exemplo fornecido"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # MÉTODO 1: Procura por estruturas específicas do DGB
        # Procura por divs com classes que podem conter dados
        divs_candidatos = soup.find_all(['div', 'tr', 'td', 'span'])
        
        for elemento in divs_candidatos:
            texto = elemento.get_text(strip=True)
            
            # Se contém o produto e tem padrão de data + números
            if str(produto_codigo) in texto and (re.search(r'\d{2}/\d{2}/\d{4}', texto) or re.search(r'[\d.,]+\s+[\d.,]+\s+[\d.,]+', texto)):
                # Tentar extrair dados deste elemento
                dados_elemento = extrair_dados_elemento(elemento, artigo, timestamp, produto_codigo)
                registros.extend(dados_elemento)
        
        # MÉTODO 2: Análise por linhas de texto
        if not registros:
            all_text = soup.get_text(separator='\n')
            lines = all_text.split('\n')
            
            for i, line in enumerate(lines):
                line = line.strip()
                
                # Se linha contém o produto
                if str(produto_codigo) in line:
                    logger.info(f"📄 Linha com produto {produto_codigo}: {line[:100]}")
                    
                    # Procurar linhas seguintes que tenham dados
                    for j in range(i, min(i + 10, len(lines))):
                        data_line = lines[j].strip()
                        
                        # Verificar se é uma linha de dados (tem data ou "Pronta entrega" e números)
                        if re.match(r'^\d{2}/\d{2}/\d{4}$', data_line) or data_line.lower() == 'pronta entrega':
                            previsao = data_line
                            
                            # Procurar 3 números nas próximas 5 linhas
                            valores = []
                            for k in range(j + 1, min(j + 6, len(lines))):
                                num_line = lines[k].strip()
                                nums = re.findall(r'[\d.,]+', num_line)
                                if nums:
                                    valores.extend(nums)
                                if len(valores) >= 3:
                                    break
                            
                            if len(valores) >= 3:
                                # Descrição é a linha do produto
                                descricao = line
                                
                                registro = [
                                    artigo,
                                    timestamp,
                                    descricao,
                                    previsao,
                                    formatar_valor_csv(valores[0]),
                                    formatar_valor_csv(valores[1]),
                                    formatar_valor_csv(valores[2])
                                ]
                                registros.append(registro)
                                logger.info(f"✅ Registro extraído: {previsao} - {valores[0]}, {valores[1]}, {valores[2]}")
        
        # MÉTODO 3: Procura por blocos de texto com padrão específico
        if not registros:
            all_text = soup.get_text(separator=' ')
            # Padrão: código do produto seguido de texto, depois data e 3 números
            padrao = re.compile(rf'(\b{produto_codigo}\b)[^0-9]*?(\d{{2}}/\d{{2}}/\d{{4}}|Pronta entrega)[^0-9]*?([\d.,]+)[^0-9]*?([\d.,]+)[^0-9]*?([\d.,]+)', re.IGNORECASE)
            
            matches = padrao.findall(all_text)
            for match in matches:
                if len(match) == 5:
                    # Encontrar descrição completa
                    contexto = re.search(rf'.{{0,200}}{produto_codigo}.{{0,200}}', all_text, re.IGNORECASE)
                    descricao = f"Produto {produto_codigo}"
                    if contexto:
                        descricao = contexto.group(0).strip()
                    
                    registro = [
                        artigo,
                        timestamp,
                        descricao,
                        match[1],
                        formatar_valor_csv(match[2]),
                        formatar_valor_csv(match[3]),
                        formatar_valor_csv(match[4])
                    ]
                    registros.append(registro)
        
        logger.info(f"✅ Parser avançado: {len(registros)} registros para produto {produto_codigo}")
        
    except Exception as e:
        logger.error(f"❌ Erro no parser avançado: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return registros

def extrair_dados_elemento(elemento, artigo, timestamp, produto_codigo):
    """Extrai dados de um elemento HTML específico"""
    registros = []
    
    try:
        # Pegar todo o texto do elemento e seus filhos
        texto_completo = elemento.get_text(separator=' ', strip=True)
        
        # Procurar por datas neste elemento
        datas = re.findall(r'\d{2}/\d{2}/\d{4}', texto_completo)
        
        for data in datas:
            # Encontrar a posição da data
            pos_data = texto_completo.find(data)
            # Pegar texto após a data
            texto_apos = texto_completo[pos_data + len(data):]
            
            # Extrair os 3 primeiros números após a data
            valores = re.findall(r'[\d.,]+', texto_apos)[:3]
            
            if len(valores) == 3:
                # Pegar texto antes da data como descrição
                texto_antes = texto_completo[:pos_data].strip()
                descricao = texto_antes if texto_antes else f"Produto {produto_codigo}"
                
                registro = [
                    artigo,
                    timestamp,
                    descricao,
                    data,
                    formatar_valor_csv(valores[0]),
                    formatar_valor_csv(valores[1]),
                    formatar_valor_csv(valores[2])
                ]
                registros.append(registro)
        
        # Procurar por "Pronta entrega"
        if 'pronta entrega' in texto_completo.lower():
            pos_pronta = texto_completo.lower().find('pronta entrega')
            texto_apos = texto_completo[pos_pronta + len('pronta entrega'):]
            
            valores = re.findall(r'[\d.,]+', texto_apos)[:3]
            
            if len(valores) == 3:
                texto_antes = texto_completo[:pos_pronta].strip()
                descricao = texto_antes if texto_antes else f"Produto {produto_codigo}"
                
                registro = [
                    artigo,
                    timestamp,
                    descricao,
                    "Pronta entrega",
                    formatar_valor_csv(valores[0]),
                    formatar_valor_csv(valores[1]),
                    formatar_valor_csv(valores[2])
                ]
                registros.append(registro)
    
    except Exception as e:
        logger.error(f"Erro ao extrair dados do elemento: {e}")
    
    return registros

def criar_csv_de_html(produto_codigo):
    """Cria CSV a partir dos arquivos HTML de debug"""
    try:
        logger.info(f"🔧 Criando CSV para produto {produto_codigo}...")
        
        # Procurar arquivo HTML mais recente para este produto
        debug_files = []
        for file in os.listdir(DEBUG_FOLDER):
            if file.startswith(f"debug_html_{produto_codigo}_") and file.endswith('.html'):
                debug_files.append(file)
        
        if not debug_files:
            logger.error(f"❌ Nenhum arquivo HTML encontrado para produto {produto_codigo}")
            return None
        
        # Pegar o arquivo mais recente
        debug_files.sort(reverse=True)
        html_file = debug_files[0]
        html_path = os.path.join(DEBUG_FOLDER, html_file)
        
        logger.info(f"📁 Processando arquivo: {html_file}")
        
        # Ler HTML
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        # Usar parser avançado
        dados = parse_html_avancado(html_content, produto_codigo)
        
        if not dados:
            logger.warning(f"⚠️ Nenhum dado extraído do HTML para produto {produto_codigo}")
            # Salvar HTML para análise
            debug_file = os.path.join(DEBUG_FOLDER, f"FALHA_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html")
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            logger.info(f"💾 HTML salvo para análise: {debug_file}")
            return None
        
        # Criar CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"produto_{produto_codigo}_TINTO_{timestamp}.csv"
        filepath = os.path.join(CSV_FOLDER, filename)
        
        # Cabeçalho
        cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                    'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(cabecalho)
            
            for registro in dados:
                if len(registro) == 7:
                    writer.writerow(registro)
        
        logger.info(f"✅ CSV criado com sucesso: {filename} ({len(dados)} registros)")
        
        # Amostra no log
        if dados:
            logger.info(f"📄 Amostra do CSV para {produto_codigo}:")
            for i, linha in enumerate(dados[:3]):
                logger.info(f"Linha {i+1}: {linha}")
        
        return filename
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar CSV do HTML: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

# ============================================================================
# FUNÇÕES AUXILIARES E VARIÁVEIS GLOBAIS
# ============================================================================

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
    """Função executada na thread para realizar o scraping - AGORA NÃO FECHA O NAVEGADOR"""
    global scraping_status
    
    scraper = None
    try:
        scraping_status['start_time'] = datetime.now().isoformat()
        logger.info("=" * 60)
        logger.info("🚀 INICIANDO SCRAPING COMPLETO")
        logger.info("=" * 60)
        
        # Ler lista de produtos
        produtos_file = 'produtos.txt'
        if not os.path.exists(produtos_file):
            with open(produtos_file, 'w') as f:
                f.write('14,15,19,20,23,24,27,28,29,30')
            logger.info("📝 Arquivo produtos.txt criado com valores padrão")
        
        with open(produtos_file, 'r') as f:
            conteudo = f.read().strip()
            produtos = [p.strip() for p in conteudo.split(',') if p.strip()]
        
        logger.info(f"📋 Produtos encontrados: {produtos}")
        logger.info(f"📊 Total de produtos: {len(produtos)}")
        
        if not produtos:
            scraping_status['message'] = '❌ Nenhum produto encontrado na lista!'
            logger.error("❌ Nenhum produto encontrado na lista!")
            scraping_status['running'] = False
            return
        
        scraping_status['total'] = len(produtos)
        scraping_status['message'] = f'Encontrados {len(produtos)} produtos para processar'
        scraping_status['results'] = []
        
        # Inicializar scraper COM KEEP_OPEN=True
        logger.info("🔄 Inicializando navegador...")
        scraper = DGBScraper(headless=False, keep_open=True)
        logger.info("✅ Navegador inicializado com sucesso")
        
        # Realizar login
        scraping_status['message'] = 'Realizando login...'
        logger.info("🔐 Tentando login...")
        
        login_success = scraper.login()
        
        if not login_success:
            scraping_status['message'] = '❌ Falha no login.'
            scraping_status['running'] = False
            logger.error("❌ Login falhou")
            
            # Tentar tirar screenshot do erro
            try:
                scraper.take_screenshot("erro_login_final")
                logger.info("📸 Screenshot do erro de login salvo")
            except:
                pass
                
            return
        
        scraping_status['message'] = '✅ Login realizado! Iniciando consultas...'
        logger.info("✅ Login realizado com sucesso")
        
        # Processar cada produto
        for i, produto in enumerate(produtos, 1):
            if not scraping_status['running']:
                logger.warning(f"⚠️ Scraping interrompido pelo usuário")
                break
                
            scraping_status['current'] = produto
            scraping_status['progress'] = int((i / len(produtos)) * 100)
            scraping_status['message'] = f'Processando produto {produto} ({i}/{len(produtos)})'
            
            logger.info("=" * 40)
            logger.info(f"🔄 Processando produto {produto} ({i}/{len(produtos)})")
            logger.info("=" * 40)
            
            # Pesquisar produto - GERA DEBUG E FULLPAGE SCREENSHOT
            logger.info(f"🔍 Pesquisando produto {produto}...")
            resultado = scraper.search_product(produto, "TINTO", fullpage_screenshot=True)
            
            # Adicionar resultado
            scraping_status['results'].append(resultado)
            
            if resultado['success']:
                scraping_status['message'] = f'✅ Produto {produto} processado: Debug gerado'
                logger.info(f"✅ Produto {produto} processado com sucesso")
                
                # Log dos arquivos gerados
                if 'arquivo_html' in resultado:
                    logger.info(f"  📄 HTML debug: {os.path.basename(resultado['arquivo_html'])}")
                if 'arquivo_texto' in resultado:
                    logger.info(f"  📝 Texto debug: {os.path.basename(resultado['arquivo_texto'])}")
                if 'screenshot_fullpage' in resultado and resultado['screenshot_fullpage']:
                    logger.info(f"  📸 Screenshot fullpage: {os.path.basename(resultado['screenshot_fullpage'])}")
                    
                # Mostrar amostra dos dados extraídos (se houver)
                if 'arquivo_html' in resultado:
                    try:
                        # Ler o arquivo HTML para verificar se tem dados
                        with open(resultado['arquivo_html'], 'r', encoding='utf-8') as f:
                            html_content = f.read()
                            if str(produto) in html_content:
                                logger.info(f"  ✅ Produto {produto} encontrado no HTML")
                            else:
                                logger.warning(f"  ⚠️ Produto {produto} NÃO encontrado no HTML")
                    except:
                        pass
            else:
                error_msg = resultado.get('error', 'Erro desconhecido')
                scraping_status['message'] = f'❌ Erro no produto {produto}: {error_msg}'
                logger.error(f"❌ Erro no produto {produto}: {error_msg}")
                
                # Tentar tirar screenshot do erro
                try:
                    scraper.take_screenshot(f"erro_produto_{produto}")
                    logger.info(f"📸 Screenshot do erro salvo")
                except:
                    pass
            
            # Pausa entre requisições
            if i < len(produtos):  # Não pausar após o último produto
                logger.info(f"⏱️  Aguardando 2 segundos antes do próximo produto...")
                time.sleep(2)
        
        scraping_status['end_time'] = datetime.now().isoformat()
        
        # Calcular estatísticas finais
        sucessos = sum(1 for r in scraping_status['results'] if r.get('success'))
        erros = sum(1 for r in scraping_status['results'] if not r.get('success'))
        
        scraping_status['message'] = f'✅ Scraping concluído! {sucessos} sucessos, {erros} erros. NAVEGADOR MANTIDO ABERTO!'
        
        logger.info("=" * 60)
        logger.info("🏁 SCRAPING CONCLUÍDO")
        logger.info(f"📊 RESUMO: {sucessos} sucessos, {erros} erros")
        logger.info("🚀 Navegador mantido aberto para interação manual")
        logger.info("=" * 60)
        
        # NÃO FECHA O NAVEGADOR - adiciona à sessão ativa
        session_id = f"scraping_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_sessions[session_id] = scraper
        logger.info(f"📋 Sessão de scraping {session_id} adicionada às sessões ativas")
        
        # Mostrar lista de arquivos gerados
        logger.info("📁 Arquivos gerados durante o scraping:")
        for result in scraping_status['results']:
            if result.get('success'):
                produto = result.get('codigo', 'N/A')
                logger.info(f"  Produto {produto}:")
                if 'arquivo_html' in result:
                    logger.info(f"    - HTML: {os.path.basename(result['arquivo_html'])}")
                if 'screenshot_fullpage' in result and result['screenshot_fullpage']:
                    logger.info(f"    - Screenshot: {os.path.basename(result['screenshot_fullpage'])}")
        
    except Exception as e:
        logger.error(f"❌ ERRO CRÍTICO na thread de scraping: {str(e)}")
        scraping_status['message'] = f"❌ Erro durante scraping: {str(e)}"
        import traceback
        logger.error(f"🔧 Traceback completo:\n{traceback.format_exc()}")
        
        # Tentar salvar screenshot do erro
        try:
            if scraper:
                scraper.take_screenshot("erro_critico_scraping")
                logger.info("📸 Screenshot do erro crítico salvo")
        except:
            pass
            
    finally:
        # NÃO FECHA O NAVEGADOR AQUI!
        # Apenas atualiza o status
        scraping_status['running'] = False
        scraping_status['end_time'] = scraping_status['end_time'] or datetime.now().isoformat()
        logger.info("🧵 Thread de scraping finalizada - navegador mantido aberto")

# ============================================================================
# ROTAS FLASK
# ============================================================================

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
    
    return jsonify({'success': True, 'message': 'Scraping iniciado. Navegador será mantido aberto após conclusão.'})

@app.route('/api/stop', methods=['POST'])
def stop_scraping():
    """Para o scraping em execução"""
    global scraping_status
    scraping_status['running'] = False
    return jsonify({'success': True, 'message': 'Scraping sendo interrompido'})

@app.route('/api/debug/analyze/<produto_codigo>', methods=['GET'])
def debug_analyze(produto_codigo):
    """Analisa o HTML de um produto específico - NÃO FECHA O NAVEGADOR"""
    try:
        scraper, session_id = get_or_create_session(keep_open=True)
        
        # Login se necessário
        if "estoquePrevisaoConsulta" not in scraper.driver.current_url:
            if not scraper.login():
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
        
        # NÃO FECHA O NAVEGADOR - mantém a sessão ativa
        
        return jsonify({
            'success': True,
            'analysis': {
                'produto': produto_codigo,
                'html_file': debug_file,
                'html_preview': html_content[:2000] + '...' if len(html_content) > 2000 else html_content,
                'session_id': session_id,
                'message': 'Navegador mantido aberto. Você pode continuar digitando.'
            }
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/close-session/<session_id>', methods=['POST'])
def close_session(session_id):
    """Fecha uma sessão específica do navegador"""
    global active_sessions
    try:
        if session_id in active_sessions:
            scraper = active_sessions[session_id]
            # Forçar fechamento mesmo se keep_open=True
            scraper.driver.quit()
            del active_sessions[session_id]
            logger.info(f"Sessão {session_id} fechada manualmente")
            return jsonify({'success': True, 'message': 'Sessão fechada'})
        else:
            return jsonify({'success': False, 'error': 'Sessão não encontrada'})
    except Exception as e:
        logger.error(f"Erro ao fechar sessão {session_id}: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/keep-alive/<session_id>', methods=['POST'])
def keep_alive_session(session_id):
    """Mantém uma sessão viva (pode ser usada para ping)"""
    global active_sessions
    if session_id in active_sessions:
        scraper = active_sessions[session_id]
        try:
            # Verificar se o driver está ativo
            scraper.driver.current_url
            return jsonify({'success': True, 'message': 'Sessão ativa'})
        except:
            # Driver morreu
            del active_sessions[session_id]
            return jsonify({'success': False, 'error': 'Sessão expirada'})
    else:
        return jsonify({'success': False, 'error': 'Sessão não encontrada'})

@app.route('/api/active-sessions', methods=['GET'])
def list_active_sessions():
    """Lista todas as sessões ativas"""
    global active_sessions
    sessions_list = []
    for session_id, scraper in active_sessions.items():
        try:
            url = scraper.driver.current_url
            sessions_list.append({
                'session_id': session_id,
                'url': url,
                'alive': True
            })
        except:
            sessions_list.append({
                'session_id': session_id,
                'url': 'N/A',
                'alive': False
            })
    
    return jsonify({'sessions': sessions_list})

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

@app.route('/api/files/screenshots')
def list_screenshot_files():
    """Lista arquivos de screenshot"""
    try:
        files = []
        # Screenshots normais
        for file in os.listdir(SCREENSHOT_FOLDER):
            if file.endswith('.png'):
                filepath = os.path.join(SCREENSHOT_FOLDER, file)
                files.append({
                    'name': file,
                    'size': os.path.getsize(filepath),
                    'path': f'/download/screenshots/{file}',
                    'type': 'normal'
                })
        
        # Screenshots fullpage
        for file in os.listdir(FULLPAGE_SCREENSHOT_FOLDER):
            if file.endswith('.png') and not file.startswith('thumb_'):
                filepath = os.path.join(FULLPAGE_SCREENSHOT_FOLDER, file)
                files.append({
                    'name': file,
                    'size': os.path.getsize(filepath),
                    'path': f'/download/screenshots/fullpage/{file}',
                    'type': 'fullpage'
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

@app.route('/download/screenshots/<filename>')
def download_screenshot(filename):
    """Download de screenshot normal"""
    try:
        return send_from_directory(SCREENSHOT_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return f"Erro ao baixar arquivo: {str(e)}", 404

@app.route('/download/screenshots/fullpage/<filename>')
def download_fullpage_screenshot(filename):
    """Download de screenshot fullpage"""
    try:
        return send_from_directory(FULLPAGE_SCREENSHOT_FOLDER, filename, as_attachment=True)
    except Exception as e:
        return f"Erro ao baixar arquivo: {str(e)}", 404

@app.route('/api/screenshot/preview/<filename>')
def preview_screenshot(filename):
    """Preview de screenshot (retorna base64)"""
    try:
        filepath = os.path.join(FULLPAGE_SCREENSHOT_FOLDER, filename)
        if not os.path.exists(filepath):
            # Tentar encontrar thumbnail
            thumb_path = os.path.join(FULLPAGE_SCREENSHOT_FOLDER, f"thumb_{filename}")
            if os.path.exists(thumb_path):
                filepath = thumb_path
            else:
                return jsonify({'success': False, 'error': 'Arquivo não encontrado'})
        
        with open(filepath, 'rb') as f:
            image_data = f.read()
        
        base64_image = base64.b64encode(image_data).decode('utf-8')
        
        return jsonify({
            'success': True,
            'image': f'data:image/png;base64,{base64_image}',
            'filename': filename
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-login', methods=['POST'])
def test_login():
    """Testa as credenciais de login - FECHA APÓS O TESTE (opcional)"""
    try:
        scraper = DGBScraper(headless=False, keep_open=False)  # keep_open=False para fechar após teste
        success = scraper.login()
        scraper.close()
        
        if success:
            return jsonify({'success': True, 'message': 'Login testado com sucesso!'})
        else:
            return jsonify({'success': False, 'error': 'Falha no login. Verifique as credenciais no arquivo .env'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/create-csv-from-debug/<produto_codigo>', methods=['POST'])
def create_csv_from_debug(produto_codigo):
    """Cria CSV a partir dos arquivos de debug para um produto específico"""
    try:
        filename = criar_csv_de_html(produto_codigo)
        
        if filename:
            return jsonify({
                'success': True,
                'message': f'CSV criado com sucesso para produto {produto_codigo}',
                'filename': filename,
                'download_url': f'/download/csv/{filename}'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Não foi possível criar CSV para produto {produto_codigo}. Verifique se existe arquivo de debug.'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/create-all-csvs', methods=['POST'])
def create_all_csvs():
    """Cria CSVs para todos os produtos com arquivos de debug"""
    try:
        # Ler lista de produtos
        with open('produtos.txt', 'r') as f:
            conteudo = f.read().strip()
            produtos = [p.strip() for p in conteudo.split(',') if p.strip()]
        
        resultados = []
        csvs_criados = 0
        
        for produto in produtos:
            logger.info(f"Processando produto {produto}...")
            filename = criar_csv_de_html(produto)
            
            if filename:
                resultados.append({
                    'produto': produto,
                    'success': True,
                    'filename': filename
                })
                csvs_criados += 1
            else:
                resultados.append({
                    'produto': produto,
                    'success': False,
                    'error': 'Não foi possível criar CSV'
                })
        
        return jsonify({
            'success': True,
            'message': f'Processados {len(resultados)} produtos: {csvs_criados} CSVs criados, {len(resultados)-csvs_criados} falhas',
            'resultados': resultados,
            'total_criados': csvs_criados,
            'total_falhas': len(resultados) - csvs_criados
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/consolidate', methods=['POST'])
def consolidate_data():
    """Consolida dados usando o consolidator.py"""
    try:
        import subprocess
        import sys
        
        logger.info("Iniciando consolidação de dados...")
        
        # Executar o consolidator diretamente
        result = subprocess.run([sys.executable, "consolidator.py"], 
                               capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            logger.info("Consolidação concluída com sucesso")
            return jsonify({
                'success': True,
                'message': 'Consolidação realizada com sucesso',
                'output': result.stdout[:1000] + '...' if len(result.stdout) > 1000 else result.stdout
            })
        else:
            logger.error(f"Erro na consolidação: {result.stderr}")
            return jsonify({
                'success': False,
                'message': 'Erro na consolidação',
                'error': result.stderr[:1000] if result.stderr else 'Erro desconhecido'
            })
            
    except Exception as e:
        logger.error(f"Erro ao executar consolidação: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fullpage-screenshot/<produto_codigo>', methods=['POST'])
def take_fullpage_screenshot_api(produto_codigo):
    """Tira screenshot fullpage de um produto específico - MANTÉM NAVEGADOR ABERTO"""
    try:
        scraper, session_id = get_or_create_session(keep_open=True)
        
        # Login se necessário
        if "estoquePrevisaoConsulta" not in scraper.driver.current_url:
            if not scraper.login():
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
        
        # Tirar screenshot fullpage
        screenshot_path = scraper.take_fullpage_screenshot(f"api_{produto_codigo}")
        
        # NÃO FECHA O NAVEGADOR - mantém a sessão ativa
        
        if screenshot_path:
            filename = os.path.basename(screenshot_path)
            return jsonify({
                'success': True,
                'message': f'Screenshot fullpage criado para produto {produto_codigo}',
                'filename': filename,
                'path': f'/download/screenshots/fullpage/{filename}',
                'preview_url': f'/api/screenshot/preview/{filename}',
                'session_id': session_id,
                'note': 'Navegador mantido aberto para interação adicional'
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Não foi possível criar screenshot fullpage para produto {produto_codigo}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/manual-browser-control', methods=['POST'])
def manual_browser_control():
    """Controle manual do navegador para debugging"""
    try:
        data = request.json
        action = data.get('action')
        
        scraper, session_id = get_or_create_session(keep_open=True)
        
        if action == 'open':
            scraper.driver.get(scraper.url_login)
            time.sleep(3)
            return jsonify({
                'success': True,
                'message': 'Navegador aberto na página de login',
                'session_id': session_id,
                'url': scraper.driver.current_url
            })
        
        elif action == 'close':
            scraper.driver.quit()
            if session_id in active_sessions:
                del active_sessions[session_id]
            return jsonify({
                'success': True,
                'message': 'Navegador fechado',
                'session_id': session_id
            })
        
        elif action == 'status':
            try:
                current_url = scraper.driver.current_url
                return jsonify({
                    'success': True,
                    'url': current_url,
                    'title': scraper.driver.title,
                    'session_id': session_id
                })
            except:
                return jsonify({
                    'success': False,
                    'error': 'Navegador não está mais disponível',
                    'session_id': session_id
                })
        
        else:
            return jsonify({
                'success': False,
                'error': f'Ação desconhecida: {action}'
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/test-single-product/<produto_codigo>', methods=['POST'])
def test_single_product(produto_codigo):
    """Testa um único produto para debugging"""
    try:
        scraper, session_id = get_or_create_session(keep_open=True)
        
        logger.info(f"🧪 TESTE MANUAL - Produto: {produto_codigo}")
        
        # Login se necessário
        if "estoquePrevisaoConsulta" not in scraper.driver.current_url:
            logger.info("🔐 Fazendo login...")
            if not scraper.login():
                return jsonify({'success': False, 'error': 'Falha no login'})
        
        logger.info("🔍 Pesquisando produto...")
        resultado = scraper.search_product(produto_codigo, "TINTO", fullpage_screenshot=True)
        
        return jsonify({
            'success': True,
            'resultado': resultado,
            'session_id': session_id,
            'message': f'Teste do produto {produto_codigo} concluído'
        })
        
    except Exception as e:
        logger.error(f"❌ Erro no teste manual: {e}")
        import traceback
        logger.error(traceback.format_exc())
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
    
    logger.info("=" * 60)
    logger.info("✅ Configurações carregadas. Sistema pronto.")
    logger.info(f"👤 Usuário: {os.getenv('DGB_USUARIO')}")
    logger.info(f"🔗 URL Login: {os.getenv('DGB_URL_LOGIN')}")
    logger.info("🚀 Navegador será mantido aberto após scraping!")
    logger.info("=" * 60)
    
    # Verificar se existe arquivo de produtos
    if not os.path.exists('produtos.txt'):
        with open('produtos.txt', 'w') as f:
            f.write('14,15,19,20,23,24,27,28,29,30')
        logger.info("📝 Arquivo produtos.txt criado com valores padrão")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)