# scraper.py - Lógica principal de scraping
import os
import time
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from dotenv import load_dotenv

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
            
            return True
            
        except Exception as e:
            logger.error(f"Erro no login: {e}")
            return False
    
    def navigate_to_stock(self):
        """Navega para página de estoque"""
        try:
            self.driver.get(self.url_estoque)
            time.sleep(5)
            
            # Verificar se carregou
            return "estoquePrevisaoConsulta" in self.driver.current_url
            
        except Exception as e:
            logger.error(f"Erro ao navegar para estoque: {e}")
            return False
    
    def search_product(self, codigo, situacao="TINTO"):
        """Pesquisa um produto específico"""
        try:
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
    
    def close(self):
        """Fecha o navegador"""
        if self.driver:
            self.driver.quit()

def run_scraping_thread(status_dict):
    """Função executada na thread"""
    scraper = None
    
    try:
        # Carregar produtos
        with open('produtos.txt', 'r') as f:
            produtos = [p.strip() for p in f.read().split(',') if p.strip()]
        
        status_dict['total'] = len(produtos)
        status_dict['message'] = f'Processando {len(produtos)} produtos'
        
        # Iniciar scraper
        scraper = DGBScraper(headless=False)
        
        # Login
        if not scraper.login():
            status_dict['message'] = 'Falha no login'
            status_dict['running'] = False
            return
        
        # Navegar para estoque
        if not scraper.navigate_to_stock():
            status_dict['message'] = 'Erro ao acessar estoque'
            status_dict['running'] = False
            return
        
        # Processar cada produto
        for i, produto in enumerate(produtos, 1):
            if not status_dict['running']:
                break
            
            status_dict['current'] = produto
            status_dict['progress'] = int((i / len(produtos)) * 100)
            status_dict['message'] = f'Processando {produto} ({i}/{len(produtos)})'
            
            # Pesquisar produto
            resultado = scraper.search_product(produto)
            status_dict['results'].append(resultado)
            
            if resultado['success']:
                logger.info(f"✅ Produto {produto} processado")
            else:
                logger.error(f"❌ Erro em {produto}: {resultado.get('error')}")
            
            time.sleep(2)
        
        status_dict['message'] = '✅ Scraping concluído!'
        status_dict['end_time'] = datetime.now().isoformat()
        
    except Exception as e:
        logger.error(f"Erro no scraping: {e}")
        status_dict['message'] = f'❌ Erro: {str(e)}'
    
    finally:
        if scraper:
            scraper.close()
        status_dict['running'] = False