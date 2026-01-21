# app.py - ATUALIZADO com funcionalidade completa e debug
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
from pdf_generator import generate_pdf_report  # Novo import

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
PDF_FOLDER = 'pdfs'
os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(DEBUG_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)

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
                registros = parser_dgb.parse_dgb_completo(html, produto)
                
                if registros:
                    filename = scraper.DGBScraper.create_csv_from_html_static(html, produto)
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

@app.route('/api/generate-pdfs', methods=['POST'])
def generate_pdfs():
    """Gera PDFs consolidados"""
    try:
        # Verificar se há dados consolidados
        csv_files = [f for f in os.listdir(CSV_FOLDER) if f.startswith('consolidado_organizado_')]
        
        if not csv_files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo consolidado encontrado. Consolide os dados primeiro.'})
        
        # Encontrar o último arquivo consolidado
        csv_files.sort(reverse=True)
        latest_csv = os.path.join(CSV_FOLDER, csv_files[0])
        
        # Gerar PDFs
        resultado = generate_pdf_report(latest_csv)
        
        if resultado['success']:
            return jsonify({
                'success': True,
                'message': resultado['message'],
                'pdf_files': resultado['pdf_files']
            })
        else:
            return jsonify({'success': False, 'error': resultado['error']})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/clean-data', methods=['POST'])
def clean_data():
    """Limpa todos os dados coletados"""
    try:
        data = request.json
        clean_csv = data.get('clean_csv', True)
        clean_debug = data.get('clean_debug', True)
        clean_pdfs = data.get('clean_pdfs', True)
        
        files_deleted = []
        folders_cleaned = []
        
        # Limpar CSV
        if clean_csv and os.path.exists(CSV_FOLDER):
            csv_files = [f for f in os.listdir(CSV_FOLDER) if f.endswith('.csv')]
            for file in csv_files:
                try:
                    os.remove(os.path.join(CSV_FOLDER, file))
                    files_deleted.append(f"csv/{file}")
                except:
                    pass
        
        # Limpar debug
        if clean_debug and os.path.exists(DEBUG_FOLDER):
            debug_files = [f for f in os.listdir(DEBUG_FOLDER) if f.endswith('.html')]
            for file in debug_files:
                try:
                    os.remove(os.path.join(DEBUG_FOLDER, file))
                    files_deleted.append(f"debug/{file}")
                except:
                    pass
        
        # Limpar PDFs
        if clean_pdfs and os.path.exists(PDF_FOLDER):
            pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
            for file in pdf_files:
                try:
                    os.remove(os.path.join(PDF_FOLDER, file))
                    files_deleted.append(f"pdfs/{file}")
                except:
                    pass
        
        # Resetar status
        scraping_status['results'] = []
        scraping_status['csv_files'] = []
        
        return jsonify({
            'success': True,
            'message': f'Dados limpos: {len(files_deleted)} arquivos removidos',
            'files_deleted': files_deleted
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/download/csv/<filename>')
def download_csv(filename):
    """Baixa arquivo CSV"""
    try:
        return send_file(os.path.join(CSV_FOLDER, filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/download/pdf/<filename>')
def download_pdf(filename):
    """Baixa arquivo PDF"""
    try:
        return send_file(os.path.join(PDF_FOLDER, filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/files')
def list_files():
    """Lista arquivos CSV e PDF"""
    try:
        files = []
        
        # CSV files
        for file in os.listdir(CSV_FOLDER):
            if file.endswith('.csv'):
                filepath = os.path.join(CSV_FOLDER, file)
                files.append({
                    'name': file,
                    'type': 'csv',
                    'size': os.path.getsize(filepath),
                    'url': f'/api/download/csv/{file}'
                })
        
        # PDF files
        for file in os.listdir(PDF_FOLDER):
            if file.endswith('.pdf'):
                filepath = os.path.join(PDF_FOLDER, file)
                files.append({
                    'name': file,
                    'type': 'pdf',
                    'size': os.path.getsize(filepath),
                    'url': f'/api/download/pdf/{file}'
                })
        
        return jsonify({'files': sorted(files, key=lambda x: x['name'], reverse=True)})
    except Exception as e:
        return jsonify({'files': [], 'error': str(e)})

@app.route('/api/debug/<produto>')
def debug_produto(produto):
    """Página de debug para ver HTML"""
    try:
        # Verificar se pasta debug existe
        if not os.path.exists('debug'):
            return "Pasta debug não encontrada"
        
        # Carregar o último HTML salvo deste produto
        debug_files = [f for f in os.listdir('debug') if f.startswith(f'debug_produto_{produto}_')]
        
        if debug_files:
            debug_files.sort(reverse=True)
            latest = debug_files[0]
            
            with open(os.path.join('debug', latest), 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Renderizar página de debug simples
            return f'''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Debug - Produto {produto}</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    .header {{ background: #f0f0f0; padding: 10px; margin-bottom: 20px; }}
                    .content {{ border: 1px solid #ccc; padding: 10px; max-height: 600px; overflow: auto; }}
                    pre {{ white-space: pre-wrap; word-wrap: break-word; }}
                    .back {{ margin-bottom: 20px; }}
                </style>
            </head>
            <body>
                <div class="back">
                    <a href="/">← Voltar</a>
                </div>
                <div class="header">
                    <h2>Debug: Produto {produto}</h2>
                    <p>Arquivo: {latest}</p>
                    <p><a href="/api/test-parser/{produto}" target="_blank">Testar Parser</a></p>
                </div>
                
                <div class="content">
                    <h3>HTML Capturado:</h3>
                    <pre>{html_content[:5000]}...</pre>
                </div>
            </body>
            </html>
            '''
        else:
            return f"Nenhum arquivo de debug encontrado para produto {produto}"
    except Exception as e:
        return f"Erro ao carregar debug: {str(e)}"

@app.route('/api/test-parser/<produto>')
def test_parser(produto):
    """Testa o parser com o último HTML capturado"""
    try:
        # Encontrar o último arquivo de debug deste produto
        debug_files = [f for f in os.listdir('debug') if f.startswith(f'debug_produto_{produto}_')]
        
        if not debug_files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo de debug encontrado'})
        
        debug_files.sort(reverse=True)
        latest_file = debug_files[0]
        
        with open(os.path.join('debug', latest_file), 'r', encoding='utf-8') as f:
            html_content = f.read()
        
        # Testar TODOS os métodos de parsing
        
        # Método 1: Parser específico
        registros_especifico = parser_dgb.parse_html_dgb_simples(html_content, produto)
        
        # Método 2: Parser agressivo
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        artigo = str(produto).lstrip('0')
        registros_agressivo = parser_dgb.parse_html_agressivo_especifico(html_content, produto, timestamp, artigo)
        
        # Método 3: Parser estrutura exata
        registros_estrutura = parser_dgb.parse_html_estrutura_exata(html_content, produto)
        
        # Método 4: Parser emergência
        registros_emergencia = parser_dgb.parse_emergencia_simples(html_content, produto)
        
        # Método 5: Parser completo
        registros_completo = parser_dgb.parse_dgb_completo(html_content, produto)
        
        return jsonify({
            'success': True,
            'arquivo': latest_file,
            'tamanho_html': len(html_content),
            'resultados': {
                'parser_especifico': {
                    'registros': len(registros_especifico),
                    'amostra': registros_especifico[:3] if registros_especifico else []
                },
                'parser_agressivo': {
                    'registros': len(registros_agressivo),
                    'amostra': registros_agressivo[:3] if registros_agressivo else []
                },
                'parser_estrutura': {
                    'registros': len(registros_estrutura),
                    'amostra': registros_estrutura[:3] if registros_estrutura else []
                },
                'parser_emergencia': {
                    'registros': len(registros_emergencia),
                    'amostra': registros_emergencia[:3] if registros_emergencia else []
                },
                'parser_completo': {
                    'registros': len(registros_completo),
                    'amostra': registros_completo[:3] if registros_completo else []
                }
            },
            'recomendado': 'parser_completo' if registros_completo else 'parser_emergencia'
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/dashboard')
def get_dashboard():
    """Retorna dados para o dashboard"""
    try:
        # Contar arquivos
        csv_files = [f for f in os.listdir(CSV_FOLDER) if f.endswith('.csv')]
        pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
        
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
            'pdf_files_count': len(pdf_files),
            'last_scraping': last_scraping,
            'is_running': scraping_status['running']
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/test-scrape-single/<produto>', methods=['POST'])
def test_scrape_single(produto):
    """Testa o scraping de um único produto"""
    try:
        scraper_instance = scraper.DGBScraper(headless=False)
        
        # Login
        if not scraper_instance.login():
            scraper_instance.close()
            return jsonify({'success': False, 'error': 'Falha no login'})
        
        # Navegar para estoque
        if not scraper_instance.navigate_to_stock():
            scraper_instance.close()
            return jsonify({'success': False, 'error': 'Falha ao acessar estoque'})
        
        # Pesquisar produto
        resultado = scraper_instance.search_product(produto)
        
        if resultado['success'] and 'html' in resultado:
            # Criar CSV
            csv_filename = scraper_instance.create_csv_from_html(resultado['html'], produto)
            
            scraper_instance.close()
            
            return jsonify({
                'success': True,
                'message': f'Produto {produto} processado',
                'csv_file': csv_filename,
                'html_size': len(resultado['html'])
            })
        else:
            scraper_instance.close()
            return jsonify({
                'success': False,
                'error': resultado.get('error', 'Erro desconhecido')
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
    
    # Criar pastas se não existirem
    os.makedirs('csv', exist_ok=True)
    os.makedirs('debug', exist_ok=True)
    os.makedirs('pdfs', exist_ok=True)
    
    logger.info("✅ Sistema iniciado com sucesso!")
    logger.info(f"👤 Usuário: {os.getenv('DGB_USUARIO')}")
    logger.info(f"📁 Pasta CSV: {os.path.abspath('csv')}")
    logger.info(f"🐛 Pasta Debug: {os.path.abspath('debug')}")
    logger.info(f"📄 Pasta PDFs: {os.path.abspath('pdfs')}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)