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
                    'timestamp': datetime.now().isoformat()
                }
                    
            except Exception as e:
                logger.error(f"Erro ao aguardar resultados: {e}")
                return {
                    'success': False,
                    'codigo': produto_codigo,
                    'error': f'Erro no processamento: {e}'
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
        """Fecha o driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("Driver fechado")
            except:
                pass

# Funções auxiliares
def criar_csv_de_html(produto_codigo):
    """Cria CSV a partir dos arquivos HTML de debug"""
    try:
        logger.info(f"🔧 Criando CSV para produto {produto_codigo} a partir dos arquivos de debug...")
        
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
        
        # Ler HTML
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Parsear HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        texto_completo = soup.get_text(separator='\n')
        
        # Processar texto para extrair dados
        dados = processar_texto_para_csv(texto_completo, produto_codigo)
        
        if not dados:
            logger.warning(f"⚠️ Nenhum dado extraído do HTML para produto {produto_codigo}")
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
            logger.info(f"Amostra do CSV para {produto_codigo}:")
            for i, linha in enumerate(dados[:2]):
                logger.info(f"Linha {i+1}: {linha}")
        
        return filename
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar CSV do HTML: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return None

def processar_texto_para_csv(texto_completo, produto_codigo):
    """Processa texto completo para extrair dados no formato CSV"""
    dados = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo_codigo = str(produto_codigo).lstrip('0')
    
    try:
        linhas = texto_completo.split('\n')
        
        # Procurar por blocos que contenham o produto
        for i in range(len(linhas)):
            linha = linhas[i].strip()
            
            # Verificar se contém o produto (com 6 dígitos)
            produto_match = re.search(r'\b(\d{6})\b', linha)
            if produto_match and produto_match.group(1).lstrip('0') == artigo_codigo:
                # Encontrou o produto, agora procurar os dados
                logger.info(f"Encontrado produto {produto_codigo} na linha {i}: {linha[:50]}...")
                
                # Procurar pelas próximas linhas que contenham os dados
                for j in range(i, min(i + 20, len(linhas))):
                    linha_atual = linhas[j].strip()
                    
                    # Verificar se é uma linha de dados (contém datas e valores)
                    if eh_linha_de_dados(linha_atual):
                        # Extrair dados desta linha
                        registro = extrair_dados_linha(linha_atual, artigo_codigo, timestamp, linha)
                        if registro:
                            dados.append(registro)
                
                # Se encontrou dados, pode pular para o próximo produto
                if dados:
                    break
        
        # Se não encontrou pelo padrão exato, tentar método mais amplo
        if not dados:
            dados = buscar_dados_alternativo(texto_completo, produto_codigo, timestamp)
    
    except Exception as e:
        logger.error(f"Erro no processamento de texto: {e}")
    
    return dados

def eh_linha_de_dados(linha):
    """Verifica se a linha contém dados de estoque"""
    # Verificar padrões comuns: datas e 3 valores numéricos
    padrao_data_valores = r'(\d{2}/\d{2}/\d{4}|Pronta entrega).*?[\d.,]+\s+[\d.,]+\s+[\d.,]+'
    if re.search(padrao_data_valores, linha, re.IGNORECASE):
        return True
    
    # Verificar se tem 3 valores numéricos seguidos
    valores = re.findall(r'[\d.,]+', linha)
    if len(valores) >= 3:
        return True
    
    return False

def extrair_dados_linha(linha_dados, artigo_codigo, timestamp, descricao_original):
    """Extrai dados de uma linha específica"""
    try:
        # Extrair previsão (data ou "Pronta entrega")
        previsao = "Pronta entrega"
        match_data = re.search(r'\d{2}/\d{2}/\d{4}', linha_dados)
        if match_data:
            previsao = match_data.group(0)
        
        # Extrair os 3 valores numéricos
        valores = re.findall(r'[\d.,]+', linha_dados)
        if len(valores) >= 3:
            estoque = formatar_valor_csv(valores[0])
            pedidos = formatar_valor_csv(valores[1])
            disponivel = formatar_valor_csv(valores[2])
            
            # Limpar descrição
            descricao_limpa = limpar_descricao(descricao_original)
            
            return [
                artigo_codigo,
                timestamp,
                descricao_limpa,
                previsao,
                estoque,
                pedidos,
                disponivel
            ]
    
    except Exception as e:
        logger.error(f"Erro ao extrair dados da linha: {e}")
    
    return None

def buscar_dados_alternativo(texto_completo, produto_codigo, timestamp):
    """Método alternativo para buscar dados quando o padrão não funciona"""
    dados = []
    artigo_codigo = str(produto_codigo).lstrip('0')
    
    try:
        # Procurar qualquer menção ao produto
        linhas = texto_completo.split('\n')
        
        for i in range(len(linhas)):
            linha = linhas[i].strip()
            
            # Verificar se a linha contém valores numéricos
            valores = re.findall(r'[\d.,]+', linha)
            if len(valores) >= 3:
                # Verificar se está próxima de uma menção ao produto
                # Verificar linhas anteriores e posteriores
                contexto = ""
                for j in range(max(0, i-3), min(len(linhas), i+4)):
                    contexto += linhas[j].strip() + " "
                
                # Se o contexto contém o produto
                if str(produto_codigo) in contexto or f" {artigo_codigo} " in contexto:
                    # Tentar extrair previsão
                    previsao = "Pronta entrega"
                    for k in range(max(0, i-2), min(len(linhas), i+3)):
                        linha_previsao = linhas[k].strip()
                        match_data = re.search(r'\d{2}/\d{2}/\d{4}', linha_previsao)
                        if match_data:
                            previsao = match_data.group(0)
                            break
                    
                    # Extrair descrição do contexto
                    descricao = f"Produto {produto_codigo}"
                    for k in range(max(0, i-5), i):
                        linha_desc = linhas[k].strip()
                        if len(linha_desc) > 10 and not re.search(r'[\d.,]+\s+[\d.,]+\s+[\d.,]+', linha_desc):
                            descricao = linha_desc
                            break
                    
                    registro = [
                        artigo_codigo,
                        timestamp,
                        descricao,
                        previsao,
                        formatar_valor_csv(valores[0]),
                        formatar_valor_csv(valores[1]),
                        formatar_valor_csv(valores[2])
                    ]
                    
                    dados.append(registro)
    
    except Exception as e:
        logger.error(f"Erro no método alternativo: {e}")
    
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

def limpar_descricao(descricao):
    """Limpa a descrição do produto"""
    try:
        # Remover múltiplos espaços
        descricao = re.sub(r'\s+', ' ', descricao)
        # Remover caracteres especiais problemáticos
        descricao = descricao.replace(';', ',')
        return descricao.strip()
    except:
        return descricao

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
            
            # Pesquisar produto - APENAS GERA DEBUG
            resultado = scraper.search_product(produto, "TINTO")
            
            # Adicionar resultado
            scraping_status['results'].append(resultado)
            
            if resultado['success']:
                scraping_status['message'] = f'✅ Produto {produto} processado: Debug gerado'
                logger.info(f"Produto {produto} processado: Debug gerado")
                
                # Log dos arquivos gerados
                if 'arquivo_html' in resultado:
                    logger.info(f"  → HTML debug: {os.path.basename(resultado['arquivo_html'])}")
                if 'arquivo_texto' in resultado:
                    logger.info(f"  → Texto debug: {os.path.basename(resultado['arquivo_texto'])}")
            else:
                scraping_status['message'] = f'❌ Erro no produto {produto}: {resultado.get("error", "Erro desconhecido")}'
                logger.error(f"Erro no produto {produto}: {resultado.get('error', 'Erro desconhecido')}")
            
            # Pausa entre requisições
            time.sleep(2)
        
        scraping_status['end_time'] = datetime.now().isoformat()
        scraping_status['message'] = '✅ Scraping concluído com sucesso!'
        logger.info("Scraping concluído com sucesso!")
        
        # Resumo final
        sucessos = sum(1 for r in scraping_status['results'] if r.get('success'))
        erros = sum(1 for r in scraping_status['results'] if not r.get('success'))
        
        logger.info(f"📊 RESUMO FINAL: {sucessos} sucessos, {erros} erros")
        
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
        
        scraper.close()
        
        return jsonify({
            'success': True,
            'analysis': {
                'produto': produto_codigo,
                'html_file': debug_file,
                'html_preview': html_content[:2000] + '...' if len(html_content) > 2000 else html_content
            }
        })
        
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

@app.route('/api/create-csv-from-debug/<produto_codigo>', methods=['POST'])
def create_csv_from_debug(produto_codigo):
    """Cria CSV a partir dos arquivos de debug"""
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
                'error': f'Não foi possível criar CSV para produto {produto_codigo}'
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
        
        for produto in produtos:
            filename = criar_csv_de_html(produto)
            if filename:
                resultados.append({
                    'produto': produto,
                    'success': True,
                    'filename': filename
                })
            else:
                resultados.append({
                    'produto': produto,
                    'success': False,
                    'error': 'Não foi possível criar CSV'
                })
        
        sucessos = sum(1 for r in resultados if r['success'])
        
        return jsonify({
            'success': True,
            'message': f'Processados {len(resultados)} produtos: {sucessos} sucessos, {len(resultados)-sucessos} falhas',
            'resultados': resultados
        })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/consolidate', methods=['POST'])
def consolidate_data():
    """Consolida dados usando o consolidator.py"""
    try:
        import subprocess
        import sys
        
        # Executar o consolidator diretamente
        result = subprocess.run([sys.executable, "consolidator.py"], 
                               capture_output=True, text=True, encoding='utf-8')
        
        if result.returncode == 0:
            return jsonify({
                'success': True,
                'message': 'Consolidação realizada com sucesso',
                'output': result.stdout
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Erro na consolidação',
                'error': result.stderr
            })
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ROTA REMOVIDA - Não existe mais /api/config
# @app.route('/api/config', methods=['GET', 'POST'])
# def api_config():
#     """API para gerenciar configurações - REMOVIDA"""
#     return jsonify({'error': 'Endpoint removido. Use arquivo .env'}), 404

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