# app.py - ATUALIZADO com funcionalidade completa
import os
import json
import threading
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Import dos módulos
import scraper
import consolidator
import parser_dgb

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__)
CORS(app)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pastas
CSV_FOLDER = 'csv'
os.makedirs(CSV_FOLDER, exist_ok=True)

# Status global
scraping_status = {
    'running': False,
    'progress': 0,
    'total': 0,
    'current': '',
    'message': '',
    'results': [],
    'csv_files': [],
    'start_time': None,
    'end_time': None
}

# Variável para a thread
scraper_thread = None

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    """Retorna o status atual"""
    return jsonify(scraping_status)

@app.route('/api/start', methods=['POST'])
def start_scraping():
    """Inicia o scraping"""
    global scraping_status, scraper_thread
    
    if scraping_status['running']:
        return jsonify({'error': 'Scraping já está em execução'}), 400
    
    # Reiniciar status
    scraping_status.update({
        'running': True,
        'progress': 0,
        'total': 0,
        'current': '',
        'message': 'Iniciando...',
        'results': [],
        'csv_files': [],
        'start_time': datetime.now().isoformat(),
        'end_time': None
    })
    
    # Iniciar thread
    scraper_thread = threading.Thread(target=scraper.run_scraping_thread, args=(scraping_status,))
    scraper_thread.daemon = True
    scraper_thread.start()
    
    return jsonify({'success': True, 'message': 'Scraping iniciado'})

@app.route('/api/stop', methods=['POST'])
def stop_scraping():
    """Para o scraping"""
    global scraping_status
    scraping_status['running'] = False
    return jsonify({'success': True, 'message': 'Scraping sendo interrompido'})

@app.route('/api/test-login', methods=['POST'])
def test_login():
    """Testa as credenciais"""
    try:
        scraper_instance = scraper.DGBScraper(headless=True)
        success = scraper_instance.login()
        scraper_instance.close()
        
        if success:
            return jsonify({'success': True, 'message': 'Login realizado com sucesso!'})
        else:
            return jsonify({'success': False, 'error': 'Falha no login. Verifique credenciais.'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/products', methods=['GET', 'POST'])
def manage_products():
    """Gerencia lista de produtos"""
    if request.method == 'GET':
        try:
            with open('produtos.txt', 'r') as f:
                produtos = f.read().strip()
            return jsonify({'produtos': produtos})
        except:
            return jsonify({'produtos': '14,15,19,20,23,24,27,28,29,30'})
    
    else:  # POST
        try:
            data = request.json
            produtos = data.get('produtos', '')
            
            with open('produtos.txt', 'w') as f:
                f.write(produtos)
            
            return jsonify({'success': True, 'message': 'Lista salva'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/create-csvs', methods=['POST'])
def create_csvs():
    """Cria CSVs a partir dos resultados do scraping"""
    try:
        # Verificar se há resultados
        if not scraping_status['results']:
            return jsonify({'success': False, 'error': 'Nenhum resultado disponível. Execute o scraping primeiro.'})
        
        csv_files_created = []
        
        for result in scraping_status['results']:
            if result.get('success') and 'html' in result:
                produto = result['codigo']
                html = result['html']
                
                # Parsear HTML e criar CSV
                registros = parser_dgb.parse_html_dgb_simples(html, produto)
                
                if registros:
                    filename = scraper.DGBScraper.create_csv_from_html(None, html, produto)
                    if filename:
                        csv_files_created.append({
                            'produto': produto,
                            'filename': filename
                        })
        
        if csv_files_created:
            return jsonify({
                'success': True,
                'message': f'Criados {len(csv_files_created)} CSVs',
                'files': csv_files_created
            })
        else:
            return jsonify({'success': False, 'error': 'Não foi possível criar nenhum CSV'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/consolidate', methods=['POST'])
def consolidate():
    """Consolida todos os CSVs"""
    try:
        resultado, mensagem = consolidator.consolidar_dados_estruturados()
        
        if resultado:
            return jsonify({
                'success': True,
                'message': mensagem,
                'resultado': resultado
            })
        else:
            return jsonify({'success': False, 'error': mensagem})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download/csv/<filename>')
def download_csv(filename):
    """Baixa arquivo CSV"""
    try:
        return send_file(os.path.join(CSV_FOLDER, filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/files')
def list_files():
    """Lista arquivos CSV"""
    try:
        files = []
        for file in os.listdir(CSV_FOLDER):
            if file.endswith('.csv'):
                filepath = os.path.join(CSV_FOLDER, file)
                files.append({
                    'name': file,
                    'size': os.path.getsize(filepath),
                    'url': f'/api/download/csv/{file}'
                })
        return jsonify({'files': sorted(files, key=lambda x: x['name'], reverse=True)})
    except Exception as e:
        return jsonify({'files': [], 'error': str(e)})
    
@app.route('/api/debug/<produto>')
def debug_produto(produto):
    """Página de debug para ver HTML"""
    try:
        # Carregar o último HTML salvo deste produto
        debug_files = [f for f in os.listdir('debug') if f.startswith(f'debug_produto_{produto}_')]
        
        if debug_files:
            debug_files.sort(reverse=True)
            latest = debug_files[0]
            
            with open(os.path.join('debug', latest), 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            return render_template('debug.html', 
                                 produto=produto,
                                 html_content=html_content,
                                 filename=latest)
        else:
            return "Nenhum arquivo de debug encontrado para este produto"
    except:
        return "Erro ao carregar debug"
    

@app.route('/api/dashboard')
def get_dashboard():
    """Retorna dados para o dashboard"""
    try:
        # Contar arquivos
        csv_files = [f for f in os.listdir(CSV_FOLDER) if f.endswith('.csv')]
        
        # Último scraping
        last_scraping = {
            'start_time': scraping_status.get('start_time'),
            'end_time': scraping_status.get('end_time'),
            'total': scraping_status.get('total', 0),
            'success': sum(1 for r in scraping_status['results'] if r.get('success')),
            'errors': sum(1 for r in scraping_status['results'] if not r.get('success'))
        }
        
        return jsonify({
            'success': True,
            'csv_files_count': len(csv_files),
            'last_scraping': last_scraping,
            'is_running': scraping_status['running']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    # Verificar variáveis de ambiente
    required_vars = ['DGB_USUARIO', 'DGB_SENHA', 'DGB_URL_LOGIN', 'DGB_URL_ESTOQUE']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"❌ Variáveis faltando: {', '.join(missing)}")
        logger.info("📝 Crie um arquivo .env com essas variáveis:")
        for var in missing:
            logger.info(f"   {var}=seu_valor")
        exit(1)
    
    # Criar pasta csv se não existir
    os.makedirs('csv', exist_ok=True)
    
    logger.info("✅ Sistema iniciado com sucesso!")
    logger.info(f"👤 Usuário: {os.getenv('DGB_USUARIO')}")
    logger.info(f"📁 Pasta CSV: {os.path.abspath('csv')}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)