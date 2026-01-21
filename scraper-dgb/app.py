# app.py - Sistema Simplificado de Scraping DGB
import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv

# Import dos módulos personalizados
from scraper import DGBScraper, run_scraping_thread
from consolidator import consolidar_dados_estruturados
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
DEBUG_FOLDER = 'debug'
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(DEBUG_FOLDER, exist_ok=True)

# Status global
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
    global scraping_status
    
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
        'start_time': datetime.now().isoformat(),
        'end_time': None
    })
    
    # Iniciar thread
    import threading
    thread = threading.Thread(target=run_scraping_thread, args=(scraping_status,))
    thread.daemon = True
    thread.start()
    
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
        scraper = DGBScraper(headless=True)
        success = scraper.login()
        scraper.close()
        
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

@app.route('/api/parse-html', methods=['POST'])
def parse_html():
    """Processa HTML e cria CSV"""
    try:
        data = request.json
        html_content = data.get('html', '')
        produto_codigo = data.get('produto', '')
        
        # Parsear HTML
        registros = parser_dgb.parse_html_dgb_simples(html_content, produto_codigo)
        
        if not registros:
            return jsonify({'success': False, 'error': 'Nenhum dado extraído'})
        
        # Criar CSV
        filename = f"produto_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        filepath = os.path.join(CSV_FOLDER, filename)
        
        import csv
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';', quotechar='"')
            writer.writerow(['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante',
                           'Previsão', 'Estoque', 'Pedidos', 'Disponível'])
            writer.writerows(registros)
        
        return jsonify({
            'success': True,
            'filename': filename,
            'registros': len(registros),
            'download_url': f'/api/download/csv/{filename}'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/consolidate', methods=['POST'])
def consolidate():
    """Consolida todos os CSVs"""
    try:
        resultado, mensagem = consolidar_dados_estruturados()
        
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
                files.append({
                    'name': file,
                    'size': os.path.getsize(os.path.join(CSV_FOLDER, file)),
                    'url': f'/api/download/csv/{file}'
                })
        return jsonify({'files': sorted(files, key=lambda x: x['name'], reverse=True)})
    except Exception as e:
        return jsonify({'files': [], 'error': str(e)})

if __name__ == '__main__':
    # Verificar variáveis de ambiente
    required_vars = ['DGB_USUARIO', 'DGB_SENHA', 'DGB_URL_LOGIN', 'DGB_URL_ESTOQUE']
    missing = [var for var in required_vars if not os.getenv(var)]
    
    if missing:
        logger.error(f"Variáveis faltando: {', '.join(missing)}")
        exit(1)
    
    app.run(host='0.0.0.0', port=5000, debug=True)