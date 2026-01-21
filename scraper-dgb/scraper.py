# scraper.py - ATUALIZADO para salvar CSVs automaticamente
import os
import time
import csv
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

# Importar parser
import parser_dgb

load_dotenv()
logger = logging.getLogger(__name__)

class DGBScraper:
    def __init__(self, headless=True):
        self.headless = headless
        self.driver = None
        self.usuario = os.getenv('DGB_USUARIO')
        self.senha = os.getenv('DGB_SENHA')
        self.url_login = os.getenv('DGB_URL_LOGIN')
        self.url_estoque = os.getenv('DGB_URL_ESTOQUE')
        self.setup_driver()
    
    def setup_driver(self):
        """Configura o navegador"""
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    def login(self):
        """Realiza login no sistema"""
        try:
            logger.info("Realizando login...")
            self.driver.get(self.url_login)
            time.sleep(3)
            
            # Preencher login
            login_field = self.driver.find_element(By.ID, "login")
            login_field.clear()
            login_field.send_keys(self.usuario)
            
            # Preencher senha
            senha_field = self.driver.find_element(By.ID, "senha")
            senha_field.clear()
            senha_field.send_keys(self.senha)
            
            # Clicar em entrar
            try:
                login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except:
                login_button = self.driver.find_element(By.ID, "botaoEntrar")
            
            login_button.click()
            time.sleep(5)
            
            logger.info("Login realizado com sucesso!")
            return True
            
        except Exception as e:
            logger.error(f"Erro no login: {e}")
            return False
    
    def navigate_to_stock(self):
        """Navega para página de estoque"""
        try:
            logger.info("Navegando para página de estoque...")
            self.driver.get(self.url_estoque)
            time.sleep(5)
            
            # Verificar se carregou
            if "estoquePrevisaoConsulta" in self.driver.current_url:
                logger.info("Página de estoque carregada com sucesso!")
                return True
            else:
                # Tentar encontrar campo de produto
                try:
                    self.driver.find_element(By.ID, "produto")
                    logger.info("Campo 'produto' encontrado")
                    return True
                except:
                    logger.error("Não conseguiu carregar página de estoque")
                    return False
                
        except Exception as e:
            logger.error(f"Erro ao navegar para estoque: {e}")
            return False
    
    def search_product(self, codigo, situacao="TINTO"):
        """Pesquisa um produto específico e retorna HTML"""
        try:
            logger.info(f"Pesquisando produto {codigo}...")
            
            # Preencher produto
            produto_field = self.driver.find_element(By.ID, "produto")
            produto_field.clear()
            produto_field.send_keys(str(codigo))
            
            # Preencher situação
            situacao_field = self.driver.find_element(By.ID, "situacao")
            situacao_field.clear()
            situacao_field.send_keys(situacao)
            
            # Clicar em pesquisar
            pesquisar_button = self.driver.find_element(By.ID, "j_idt67")
            pesquisar_button.click()
            
            time.sleep(5)
            
            # Obter HTML
            html = self.driver.page_source
            
            return {
                'success': True,
                'codigo': codigo,
                'html': html,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erro ao pesquisar produto {codigo}: {e}")
            return {
                'success': False,
                'codigo': codigo,
                'error': str(e)
            }
    
    def create_csv_from_html(self, html_content, produto_codigo):
        """Cria CSV a partir do HTML"""
        try:
            # Parsear HTML
            registros = parser_dgb.parse_html_dgb_simples(html_content, produto_codigo)
            
            if not registros:
                logger.warning(f"Nenhum registro extraído para {produto_codigo}")
                return None
            
            # Criar pasta csv se não existir
            os.makedirs('csv', exist_ok=True)
            
            # Nome do arquivo
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"produto_{produto_codigo}_{timestamp}.csv"
            filepath = os.path.join('csv', filename)
            
            # Escrever CSV
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante',
                               'Previsão', 'Estoque', 'Pedidos', 'Disponível'])
                writer.writerows(registros)
            
            logger.info(f"CSV criado: {filename} ({len(registros)} registros)")
            return filename
            
        except Exception as e:
            logger.error(f"Erro ao criar CSV para {produto_codigo}: {e}")
            return None
    
    def close(self):
        """Fecha o navegador"""
        if self.driver:
            self.driver.quit()
            logger.info("Navegador fechado")

def run_scraping_thread(status_dict):
    """Função executada na thread - ATUALIZADA para salvar CSVs"""
    scraper = None
    
    try:
        # Carregar produtos
        with open('produtos.txt', 'r') as f:
            produtos = [p.strip() for p in f.read().split(',') if p.strip()]
        
        status_dict['total'] = len(produtos)
        status_dict['message'] = f'Processando {len(produtos)} produtos'
        status_dict['csv_files'] = []  # Lista de CSVs criados
        
        # Iniciar scraper
        scraper = DGBScraper(headless=False)
        
        # Login
        status_dict['message'] = 'Realizando login...'
        if not scraper.login():
            status_dict['message'] = 'Falha no login'
            status_dict['running'] = False
            return
        
        # Navegar para estoque
        status_dict['message'] = 'Navegando para estoque...'
        if not scraper.navigate_to_stock():
            status_dict['message'] = 'Erro ao acessar estoque'
            status_dict['running'] = False
            return
        
        status_dict['message'] = 'Iniciando consultas...'
        
        # Processar cada produto
        for i, produto in enumerate(produtos, 1):
            if not status_dict['running']:
                break
            
            status_dict['current'] = produto
            status_dict['progress'] = int((i / len(produtos)) * 100)
            status_dict['message'] = f'Processando {produto} ({i}/{len(produtos)})'
            
            # Pesquisar produto
            resultado = scraper.search_product(produto)
            
            # Se obteve HTML com sucesso, criar CSV
            if resultado['success'] and 'html' in resultado:
                csv_filename = scraper.create_csv_from_html(resultado['html'], produto)
                if csv_filename:
                    resultado['csv_file'] = csv_filename
                    status_dict['csv_files'].append(csv_filename)
                    logger.info(f"✅ Produto {produto} processado - CSV criado")
                else:
                    resultado['success'] = False
                    resultado['error'] = 'Não foi possível criar CSV'
                    logger.error(f"❌ Produto {produto}: erro ao criar CSV")
            
            status_dict['results'].append(resultado)
            
            # Pequena pausa entre consultas
            time.sleep(2)
        
        # Resumo final
        sucessos = sum(1 for r in status_dict['results'] if r.get('success'))
        erros = sum(1 for r in status_dict['results'] if not r.get('success'))
        
        status_dict['message'] = f'✅ Scraping concluído! {sucessos} sucessos, {erros} erros'
        status_dict['end_time'] = datetime.now().isoformat()
        
        logger.info(f"📊 Resumo: {sucessos} sucessos, {erros} erros")
        logger.info(f"📁 CSVs criados: {len(status_dict['csv_files'])}")
        
    except Exception as e:
        logger.error(f"Erro no scraping: {e}")
        status_dict['message'] = f'❌ Erro: {str(e)}'
    
    finally:
        if scraper:
            scraper.close()
        status_dict['running'] = False