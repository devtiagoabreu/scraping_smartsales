# app.py - ATUALIZADO com funcionalidade de Email Avançado
import os
import json
import threading
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders
import mimetypes
import base64
import re
import uuid

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
IMAGE_FOLDER = 'images'
XLSX_FOLDER = 'xlsx'
EMAIL_TEMPLATES_FOLDER = 'email_templates'  # Nova pasta para templates de email
EMAIL_ATTACHMENTS_FOLDER = 'email_attachments'  # Nova pasta para anexos de email
EMAIL_LOGS_FOLDER = 'email_logs'  # Nova pasta para logs de email
STATIC_FOLDER = 'static'  # Nova pasta para arquivos estáticos

os.makedirs(CSV_FOLDER, exist_ok=True)
os.makedirs(DEBUG_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(IMAGE_FOLDER, exist_ok=True)
os.makedirs(XLSX_FOLDER, exist_ok=True)
os.makedirs(EMAIL_TEMPLATES_FOLDER, exist_ok=True)  # Criar pasta para templates
os.makedirs(EMAIL_ATTACHMENTS_FOLDER, exist_ok=True)  # Criar pasta para anexos
os.makedirs(EMAIL_LOGS_FOLDER, exist_ok=True)  # Criar pasta para logs
os.makedirs(STATIC_FOLDER, exist_ok=True)  # Criar pasta para estáticos
os.makedirs(os.path.join(STATIC_FOLDER, 'js'), exist_ok=True)  # Subpasta JS
os.makedirs(os.path.join(STATIC_FOLDER, 'css'), exist_ok=True)  # Subpasta CSS

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

# ============================================
# ROTA PARA ARQUIVOS ESTÁTICOS (NOVA)
# ============================================

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve arquivos estáticos (JS, CSS, imagens)"""
    return send_from_directory('static', filename)

# ============================================
# ROTAS PRINCIPAIS (existentes - MANTIDAS)
# ============================================

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

# ... (o resto do app.py permanece IGUAL até o final) ...

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
                'pdf_files': resultado.get('pdf_files', []),
                'image_files': resultado.get('image_files', [])
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
        clean_images = data.get('clean_images', True)
        clean_xlsx = data.get('clean_xlsx', True)
        
        files_deleted = []
        
        # Limpar CSV
        if clean_csv and os.path.exists(CSV_FOLDER):
            for file in os.listdir(CSV_FOLDER):
                if file.endswith('.csv'):
                    try:
                        os.remove(os.path.join(CSV_FOLDER, file))
                        files_deleted.append(f"csv/{file}")
                    except:
                        pass
        
        # Limpar debug
        if clean_debug and os.path.exists(DEBUG_FOLDER):
            for file in os.listdir(DEBUG_FOLDER):
                if file.endswith('.html'):
                    try:
                        os.remove(os.path.join(DEBUG_FOLDER, file))
                        files_deleted.append(f"debug/{file}")
                    except:
                        pass
        
        # Limpar PDFs
        if clean_pdfs and os.path.exists(PDF_FOLDER):
            for file in os.listdir(PDF_FOLDER):
                if file.endswith('.pdf'):
                    try:
                        os.remove(os.path.join(PDF_FOLDER, file))
                        files_deleted.append(f"pdfs/{file}")
                    except:
                        pass
        
        # Limpar imagens
        if clean_images and os.path.exists(IMAGE_FOLDER):
            for file in os.listdir(IMAGE_FOLDER):
                if file.endswith(('.jpg', '.jpeg', '.png')):
                    try:
                        os.remove(os.path.join(IMAGE_FOLDER, file))
                        files_deleted.append(f"images/{file}")
                    except:
                        pass
        
        # Limpar XLSX
        if clean_xlsx and os.path.exists(XLSX_FOLDER):
            for file in os.listdir(XLSX_FOLDER):
                if file.endswith('.xlsx'):
                    try:
                        os.remove(os.path.join(XLSX_FOLDER, file))
                        files_deleted.append(f"xlsx/{file}")
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

# ============================================
# ROTAS DE EMAIL BÁSICO (existentes - MANTIDAS)
# ============================================

@app.route('/api/send-email', methods=['POST'])
def send_email():
    """Envia email com relatório PDF usando Gmail"""
    try:
        # Verificar se há PDF disponível
        pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.startswith('relatorio_todos_produtos_')]
        
        if not pdf_files:
            return jsonify({'success': False, 'error': 'Nenhum relatório PDF encontrado. Gere os PDFs primeiro.'})
        
        # Encontrar o último PDF
        pdf_files.sort(reverse=True)
        latest_pdf = os.path.join(PDF_FOLDER, pdf_files[0])
        
        # Carregar lista de contatos
        try:
            with open('contatos.txt', 'r') as f:
                contacts_content = f.read().strip()
            contacts = [c.strip() for c in contacts_content.split(';') if c.strip()]
        except:
            contacts = []
        
        if not contacts:
            return jsonify({'success': False, 'error': 'Nenhum contato encontrado. Adicione emails em contatos.txt'})
        
        # Carregar mensagem do email
        try:
            with open('mensagem_email.txt', 'r', encoding='utf-8') as f:
                email_message = f.read()
        except:
            email_message = """Prezado(a),

Segue em anexo o relatório consolidado de estoque DGB.

Este relatório foi gerado automaticamente pelo sistema DGB Scraper.

Atenciosamente,
Sistema DGB Scraper"""
        
        # CONFIGURAÇÕES CORRETAS PARA GMAIL
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_username = 'dgbcomex@gmail.com'
        smtp_password = 'rsxc jmaz qocw ywmy'
        email_from = 'dgbcomex@gmail.com'
        
        logger.info(f"📧 Usando Gmail: {smtp_username}")
        
        # Enviar email para cada contato
        emails_sent = []
        emails_failed = []
        
        for contact in contacts:
            try:
                # Criar mensagem
                msg = MIMEMultipart()
                msg['From'] = email_from
                msg['To'] = contact
                msg['Subject'] = f'Relatório de Estoque DGB - {datetime.now().strftime("%d/%m/%Y")}'
                
                # Corpo do email
                msg.attach(MIMEText(email_message, 'plain', 'utf-8'))
                
                # Anexar PDF
                with open(latest_pdf, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', 
                                  f'attachment; filename="{os.path.basename(latest_pdf)}"')
                    msg.attach(part)
                
                # Conectar e enviar usando Gmail
                logger.info(f"📤 Enviando para {contact} via Gmail...")
                
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                server.set_debuglevel(1)
                
                try:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(smtp_username, smtp_password)
                    server.send_message(msg)
                    server.quit()
                    
                    emails_sent.append(contact)
                    logger.info(f"✅ Email enviado para: {contact}")
                    
                except Exception as e:
                    server.quit()
                    raise e
                
                # Pequena pausa entre emails
                import time
                time.sleep(1)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Falha para {contact}: {error_msg}")
                emails_failed.append({
                    'email': contact, 
                    'error': error_msg
                })
        
        # Resultado
        if not emails_sent:
            return jsonify({
                'success': False,
                'error': 'Falha ao enviar emails. A conexão foi fechada inesperadamente.',
                'emails_sent': emails_sent,
                'emails_failed': emails_failed,
                'config': {
                    'server': smtp_server,
                    'port': smtp_port,
                    'username': smtp_username,
                    'password_length': len(smtp_password)
                }
            })
        
        return jsonify({
            'success': True,
            'message': f'✅ Emails enviados: {len(emails_sent)} sucesso, {len(emails_failed)} falhas',
            'emails_sent': emails_sent,
            'emails_failed': emails_failed,
            'pdf_file': os.path.basename(latest_pdf)
        })
        
    except Exception as e:
        logger.error(f'❌ Erro geral no envio: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Erro no envio: {str(e)}'})

@app.route('/api/test-email-setup', methods=['GET'])
def test_email_setup():
    """Testa a configuração de email atual"""
    try:
        # Usar configurações fixas para Gmail
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_username = 'dgbcomex@gmail.com'
        smtp_password = 'rsxc jmaz qocw ywmy'
        
        logger.info(f"🔍 Testando configuração de Gmail...")
        logger.info(f"   Servidor: {smtp_server}")
        logger.info(f"   Porta: {smtp_port}")
        logger.info(f"   Usuário: {smtp_username}")
        
        # Testar conexão
        try:
            logger.info("📡 Conectando ao servidor SMTP...")
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.set_debuglevel(1)
            
            logger.info("👋 Enviando EHLO...")
            server.ehlo()
            
            logger.info("🔒 Iniciando TLS...")
            server.starttls()
            
            logger.info("👋 EHLO após TLS...")
            server.ehlo()
            
            logger.info("🔐 Tentando login...")
            server.login(smtp_username, smtp_password)
            
            logger.info("✅ Login bem-sucedido!")
            
            server.quit()
            
            return jsonify({
                'success': True,
                'message': '✅ Configuração de Gmail funcionando perfeitamente!',
                'config': {
                    'server': smtp_server,
                    'port': smtp_port,
                    'username': smtp_username,
                    'auth_method': 'TLS'
                }
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ Falha na conexão: {error_msg}")
            
            # Análise do erro
            error_analysis = ""
            if "535" in error_msg or "Invalid" in error_msg:
                error_analysis = "ERRO DE AUTENTICAÇÃO: Senha de aplicativo incorreta ou conta não tem verificação em duas etapas ativada."
            elif "Connection refused" in error_msg:
                error_analysis = "CONEXÃO RECUSADA: Firewall pode estar bloqueando a porta 587."
            elif "timeout" in error_msg.lower():
                error_analysis = "TIMEOUT: Servidor não respondeu. Verifique sua conexão com a internet."
            
            return jsonify({
                'success': False,
                'error': f'Falha na conexão: {error_msg}',
                'analysis': error_analysis,
                'config': {
                    'server': smtp_server,
                    'port': smtp_port,
                    'username': smtp_username
                },
                'solutions': [
                    '1. Verifique se a senha de aplicativo está correta: rsxc jmaz qocw ywmy',
                    '2. Verifique se a verificação em duas etapas está ativa no Gmail',
                    '3. Acesse: https://myaccount.google.com/security',
                    '4. Vá para "Senhas de aplicativo" e gere uma nova se necessário',
                    '5. Teste manualmente no terminal Python:',
                    '   python -c "import smtplib; s=smtplib.SMTP(\'smtp.gmail.com\',587); s.starttls(); s.login(\'dgbcomex@gmail.com\',\'rsxc jmaz qocw ywmy\'); print(\'OK\')"'
                ]
            })
            
    except Exception as e:
        logger.error(f"❌ Erro no teste de conexão: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-contacts', methods=['GET', 'POST'])
def manage_email_contacts():
    """Gerencia lista de contatos de email"""
    if request.method == 'GET':
        try:
            with open('contatos.txt', 'r', encoding='utf-8') as f:
                contatos = f.read().strip()
            return jsonify({'contatos': contatos})
        except:
            return jsonify({'contatos': 'email1@exemplo.com;email2@exemplo.com'})
    
    else:  # POST
        try:
            data = request.json
            contatos = data.get('contatos', '')
            
            with open('contatos.txt', 'w', encoding='utf-8') as f:
                f.write(contatos)
            
            return jsonify({'success': True, 'message': 'Lista de contatos salva'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-message', methods=['GET', 'POST'])
def manage_email_message():
    """Gerencia mensagem do email"""
    if request.method == 'GET':
        try:
            with open('mensagem_email.txt', 'r', encoding='utf-8') as f:
                mensagem = f.read()
            return jsonify({'mensagem': mensagem})
        except:
            default_msg = """Prezado(a),

Segue em anexo o relatório consolidado de estoque DGB.

Este relatório foi gerado automaticamente pelo sistema DGB Scraper.

Atenciosamente,
Sistema DGB Scraper"""
            return jsonify({'mensagem': default_msg})
    
    else:  # POST
        try:
            data = request.json
            mensagem = data.get('mensagem', '')
            
            with open('mensagem_email.txt', 'w', encoding='utf-8') as f:
                f.write(mensagem)
            
            return jsonify({'success': True, 'message': 'Mensagem do email salva'})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

# ============================================
# ROTAS DE EMAIL AVANÇADO (NOVAS)
# ============================================

@app.route('/api/email-avancado/contatos', methods=['GET', 'POST', 'DELETE'])
def manage_advanced_contacts():
    """Gerencia lista de contatos avançada (email;nome)"""
    contacts_file = 'contatos_avancado.txt'
    
    if request.method == 'GET':
        try:
            if os.path.exists(contacts_file):
                with open(contacts_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                # Parsear contatos
                contacts = []
                for line in content.split('\n'):
                    line = line.strip()
                    if line and ';' in line:
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            contacts.append({
                                'email': parts[0].strip(),
                                'nome': parts[1].strip()
                            })
                
                return jsonify({
                    'success': True,
                    'contacts': contacts,
                    'raw_content': content
                })
            else:
                # Criar arquivo com exemplo
                example = "exemplo1@dominio.com;João Silva\nexemplo2@dominio.com;Maria Santos"
                with open(contacts_file, 'w', encoding='utf-8') as f:
                    f.write(example)
                
                return jsonify({
                    'success': True,
                    'contacts': [
                        {'email': 'exemplo1@dominio.com', 'nome': 'João Silva'},
                        {'email': 'exemplo2@dominio.com', 'nome': 'Maria Santos'}
                    ],
                    'raw_content': example
                })
                
        except Exception as e:
            logger.error(f"Erro ao carregar contatos avançados: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    elif request.method == 'POST':
        try:
            data = request.json
            contacts_data = data.get('contacts', '')
            
            # Validar formato
            contacts_list = []
            for line in contacts_data.split('\n'):
                line = line.strip()
                if line:
                    if ';' in line:
                        parts = line.split(';', 1)
                        if len(parts) == 2:
                            email = parts[0].strip()
                            nome = parts[1].strip()
                            # Validar email básico
                            if '@' in email and '.' in email:
                                contacts_list.append(f"{email};{nome}")
                    else:
                        # Se não tem ;, considerar apenas email
                        if '@' in line and '.' in line:
                            contacts_list.append(f"{line};")
            
            # Salvar arquivo
            with open(contacts_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(contacts_list))
            
            return jsonify({
                'success': True,
                'message': f'Lista salva com {len(contacts_list)} contatos',
                'count': len(contacts_list)
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar contatos avançados: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    elif request.method == 'DELETE':
        try:
            # Limpar arquivo
            with open(contacts_file, 'w', encoding='utf-8') as f:
                f.write('')
            
            return jsonify({
                'success': True,
                'message': 'Lista de contatos limpa'
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-avancado/templates', methods=['GET', 'POST', 'DELETE'])
def manage_email_templates():
    """Gerencia templates de email"""
    if request.method == 'GET':
        try:
            templates = []
            if os.path.exists(EMAIL_TEMPLATES_FOLDER):
                for filename in os.listdir(EMAIL_TEMPLATES_FOLDER):
                    if filename.endswith('.html') or filename.endswith('.txt'):
                        filepath = os.path.join(EMAIL_TEMPLATES_FOLDER, filename)
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        templates.append({
                            'name': filename,
                            'content': content,
                            'type': 'html' if filename.endswith('.html') else 'text',
                            'size': len(content)
                        })
            
            return jsonify({
                'success': True,
                'templates': templates
            })
            
        except Exception as e:
            logger.error(f"Erro ao carregar templates: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    elif request.method == 'POST':
        try:
            data = request.json
            template_name = data.get('name', '').strip()
            template_content = data.get('content', '')
            template_type = data.get('type', 'html')
            
            if not template_name:
                return jsonify({'success': False, 'error': 'Nome do template é obrigatório'})
            
            # Garantir extensão correta
            if template_type == 'html' and not template_name.endswith('.html'):
                template_name += '.html'
            elif template_type == 'text' and not template_name.endswith('.txt'):
                template_name += '.txt'
            
            # Salvar template
            filepath = os.path.join(EMAIL_TEMPLATES_FOLDER, template_name)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            return jsonify({
                'success': True,
                'message': f'Template "{template_name}" salvo',
                'filename': template_name
            })
            
        except Exception as e:
            logger.error(f"Erro ao salvar template: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    elif request.method == 'DELETE':
        try:
            data = request.json
            template_name = data.get('name', '')
            
            if not template_name:
                return jsonify({'success': False, 'error': 'Nome do template é obrigatório'})
            
            filepath = os.path.join(EMAIL_TEMPLATES_FOLDER, template_name)
            if os.path.exists(filepath):
                os.remove(filepath)
                return jsonify({
                    'success': True,
                    'message': f'Template "{template_name}" removido'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Template "{template_name}" não encontrado'
                })
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-avancado/upload', methods=['POST'])
def upload_email_attachment():
    """Faz upload de arquivos para anexar em emails"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'Nenhum arquivo enviado'})
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'Nenhum arquivo selecionado'})
        
        # Gerar nome único para o arquivo
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        filepath = os.path.join(EMAIL_ATTACHMENTS_FOLDER, filename)
        
        # Salvar arquivo
        file.save(filepath)
        
        # Obter informações do arquivo
        file_size = os.path.getsize(filepath)
        file_type = mimetypes.guess_type(filepath)[0] or 'application/octet-stream'
        
        return jsonify({
            'success': True,
            'message': 'Arquivo enviado com sucesso',
            'filename': filename,
            'original_name': file.filename,
            'path': filepath,
            'size': file_size,
            'type': file_type,
            'url': f'/api/email-avancado/download/{filename}'
        })
        
    except Exception as e:
        logger.error(f"Erro no upload de arquivo: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-avancado/download/<filename>')
def download_email_attachment(filename):
    """Baixa arquivo anexado"""
    try:
        filepath = os.path.join(EMAIL_ATTACHMENTS_FOLDER, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True)
        else:
            return jsonify({'error': 'Arquivo não encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/email-avancado/attachments', methods=['GET', 'DELETE'])
def manage_attachments():
    """Lista ou remove anexos"""
    if request.method == 'GET':
        try:
            attachments = []
            if os.path.exists(EMAIL_ATTACHMENTS_FOLDER):
                for filename in os.listdir(EMAIL_ATTACHMENTS_FOLDER):
                    filepath = os.path.join(EMAIL_ATTACHMENTS_FOLDER, filename)
                    if os.path.isfile(filepath):
                        file_size = os.path.getsize(filepath)
                        file_type = mimetypes.guess_type(filepath)[0] or 'Desconhecido'
                        
                        # Extrair nome original (remover UUID)
                        original_name = filename
                        if '_' in filename:
                            original_name = '_'.join(filename.split('_')[1:])
                        
                        attachments.append({
                            'filename': filename,
                            'original_name': original_name,
                            'size': file_size,
                            'type': file_type,
                            'path': filepath,
                            'url': f'/api/email-avancado/download/{filename}'
                        })
            
            return jsonify({
                'success': True,
                'attachments': attachments
            })
            
        except Exception as e:
            logger.error(f"Erro ao listar anexos: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    elif request.method == 'DELETE':
        try:
            data = request.json
            filename = data.get('filename', '')
            
            if not filename:
                return jsonify({'success': False, 'error': 'Nome do arquivo é obrigatório'})
            
            filepath = os.path.join(EMAIL_ATTACHMENTS_FOLDER, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                return jsonify({
                    'success': True,
                    'message': f'Anexo "{filename}" removido'
                })
            else:
                return jsonify({
                    'success': False,
                    'error': f'Anexo "{filename}" não encontrado'
                })
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-avancado/send', methods=['POST'])
def send_advanced_email():
    """Envia email avançado com template, anexos e personalização"""
    try:
        data = request.json
        
        # Obter dados do request
        subject = data.get('subject', '').strip()
        html_content = data.get('html_content', '')
        text_content = data.get('text_content', '')
        contacts = data.get('contacts', [])  # Lista de {email, nome}
        attachments = data.get('attachments', [])  # Lista de nomes de arquivos
        send_type = data.get('send_type', 'individual')  # individual, cc, bcc
        
        # Validações
        if not subject:
            return jsonify({'success': False, 'error': 'Assunto do email é obrigatório'})
        
        if not html_content and not text_content:
            return jsonify({'success': False, 'error': 'Conteúdo do email é obrigatório'})
        
        if not contacts:
            return jsonify({'success': False, 'error': 'Lista de contatos está vazia'})
        
        # Configurações SMTP
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587
        smtp_username = 'dgbcomex@gmail.com'
        smtp_password = 'rsxc jmaz qocw ywmy'
        email_from = 'dgbcomex@gmail.com'
        
        logger.info(f"📧 Enviando email avançado para {len(contacts)} contatos")
        
        # Preparar logs
        send_log = {
            'timestamp': datetime.now().isoformat(),
            'subject': subject,
            'total_contacts': len(contacts),
            'sent': 0,
            'failed': 0,
            'details': []
        }
        
        # Enviar emails
        emails_sent = []
        emails_failed = []
        
        for i, contact in enumerate(contacts):
            try:
                email = contact.get('email', '').strip()
                nome = contact.get('nome', '').strip()
                
                if not email or '@' not in email:
                    logger.warning(f"Email inválido: {email}")
                    emails_failed.append({
                        'email': email,
                        'nome': nome,
                        'error': 'Email inválido'
                    })
                    continue
                
                # Personalizar conteúdo
                personalized_html = html_content
                personalized_text = text_content
                
                if nome:
                    personalized_html = personalized_html.replace('{{nome}}', nome)
                    personalized_html = personalized_html.replace('{{email}}', email)
                    personalized_text = personalized_text.replace('{{nome}}', nome)
                    personalized_text = personalized_text.replace('{{email}}', email)
                
                # Criar mensagem MIME
                msg = MIMEMultipart('alternative')
                msg['From'] = email_from
                msg['Subject'] = subject
                
                # Configurar destinatários baseado no tipo de envio
                if send_type == 'individual':
                    msg['To'] = email
                    to_addresses = [email]
                elif send_type == 'cc':
                    msg['To'] = email_from
                    msg['Cc'] = email
                    to_addresses = [email_from, email]
                elif send_type == 'bcc':
                    msg['To'] = email_from
                    to_addresses = [email_from]
                    # BCC será adicionado na chamada SMTP
                
                # Adicionar corpo do email
                if personalized_html:
                    msg.attach(MIMEText(personalized_html, 'html', 'utf-8'))
                if personalized_text:
                    msg.attach(MIMEText(personalized_text, 'plain', 'utf-8'))
                
                # Adicionar anexos
                for attachment_name in attachments:
                    attachment_path = os.path.join(EMAIL_ATTACHMENTS_FOLDER, attachment_name)
                    if os.path.exists(attachment_path):
                        with open(attachment_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            
                            # Extrair nome original
                            original_name = attachment_name
                            if '_' in attachment_name:
                                original_name = '_'.join(attachment_name.split('_')[1:])
                            
                            part.add_header('Content-Disposition', 
                                          f'attachment; filename="{original_name}"')
                            msg.attach(part)
                
                # Enviar email
                server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
                
                try:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(smtp_username, smtp_password)
                    
                    # Enviar com base no tipo
                    if send_type == 'bcc':
                        # Para BCC, enviar para o remetente com BCC oculto
                        server.sendmail(email_from, to_addresses, msg.as_string())
                        # Enviar cópia oculta
                        bcc_msg = msg.copy()
                        bcc_msg.replace_header('To', email)
                        server.sendmail(email_from, [email], bcc_msg.as_string())
                    else:
                        server.sendmail(email_from, to_addresses, msg.as_string())
                    
                    server.quit()
                    
                    emails_sent.append({
                        'email': email,
                        'nome': nome
                    })
                    
                    logger.info(f"✅ Email enviado para: {email} ({nome})")
                    
                except Exception as e:
                    server.quit()
                    raise e
                
                # Pequena pausa entre emails para evitar bloqueio
                import time
                time.sleep(1)
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"❌ Falha para {contact.get('email', 'desconhecido')}: {error_msg}")
                emails_failed.append({
                    'email': contact.get('email', ''),
                    'nome': contact.get('nome', ''),
                    'error': error_msg
                })
        
        # Salvar log do envio
        log_filename = f"envio_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_path = os.path.join(EMAIL_LOGS_FOLDER, log_filename)
        
        send_log.update({
            'sent': len(emails_sent),
            'failed': len(emails_failed),
            'emails_sent': emails_sent,
            'emails_failed': emails_failed,
            'completed_at': datetime.now().isoformat()
        })
        
        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(send_log, f, ensure_ascii=False, indent=2)
        
        # Retornar resultado
        return jsonify({
            'success': True,
            'message': f'✅ Envio concluído: {len(emails_sent)} sucesso, {len(emails_failed)} falhas',
            'sent': len(emails_sent),
            'failed': len(emails_failed),
            'emails_sent': emails_sent,
            'emails_failed': emails_failed,
            'log_file': log_filename
        })
        
    except Exception as e:
        logger.error(f'❌ Erro no envio avançado: {e}')
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f'Erro no envio: {str(e)}'})

@app.route('/api/email-avancado/logs', methods=['GET'])
def get_email_logs():
    """Obtém logs de envios anteriores"""
    try:
        logs = []
        if os.path.exists(EMAIL_LOGS_FOLDER):
            for filename in sorted(os.listdir(EMAIL_LOGS_FOLDER), reverse=True):
                if filename.endswith('.json'):
                    filepath = os.path.join(EMAIL_LOGS_FOLDER, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            log_data = json.load(f)
                        
                        logs.append({
                            'filename': filename,
                            'timestamp': log_data.get('timestamp', ''),
                            'subject': log_data.get('subject', ''),
                            'total_contacts': log_data.get('total_contacts', 0),
                            'sent': log_data.get('sent', 0),
                            'failed': log_data.get('failed', 0),
                            'size': os.path.getsize(filepath)
                        })
                    except:
                        continue
        
        return jsonify({
            'success': True,
            'logs': logs
        })
        
    except Exception as e:
        logger.error(f"Erro ao carregar logs: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-avancado/log/<filename>')
def get_email_log_detail(filename):
    """Obtém detalhes de um log específico"""
    try:
        filepath = os.path.join(EMAIL_LOGS_FOLDER, filename)
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                log_data = json.load(f)
            
            return jsonify({
                'success': True,
                'log': log_data
            })
        else:
            return jsonify({'success': False, 'error': 'Log não encontrado'})
            
    except Exception as e:
        logger.error(f"Erro ao carregar log: {e}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/email-avancado/clean-attachments', methods=['POST'])
def clean_email_attachments():
    """Limpa todos os anexos temporários"""
    try:
        files_deleted = []
        if os.path.exists(EMAIL_ATTACHMENTS_FOLDER):
            for filename in os.listdir(EMAIL_ATTACHMENTS_FOLDER):
                try:
                    filepath = os.path.join(EMAIL_ATTACHMENTS_FOLDER, filename)
                    os.remove(filepath)
                    files_deleted.append(filename)
                except:
                    pass
        
        return jsonify({
            'success': True,
            'message': f'{len(files_deleted)} anexos removidos',
            'files_deleted': files_deleted
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# ============================================
# ROTAS DE DOWNLOAD (existentes - MANTIDAS)
# ============================================

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

@app.route('/api/download/image/<filename>')
def download_image(filename):
    """Baixa arquivo de imagem"""
    try:
        return send_file(os.path.join(IMAGE_FOLDER, filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/download/xlsx/<filename>')
def download_xlsx(filename):
    """Baixa arquivo XLSX"""
    try:
        return send_file(os.path.join(XLSX_FOLDER, filename), as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 404

@app.route('/api/files')
def list_files():
    """Lista arquivos CSV, PDF, imagens e XLSX"""
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
        
        # Image files
        for file in os.listdir(IMAGE_FOLDER):
            if file.endswith(('.jpg', '.jpeg', '.png')):
                filepath = os.path.join(IMAGE_FOLDER, file)
                files.append({
                    'name': file,
                    'type': 'image',
                    'size': os.path.getsize(filepath),
                    'url': f'/api/download/image/{file}'
                })
        
        # XLSX files
        for file in os.listdir(XLSX_FOLDER):
            if file.endswith('.xlsx'):
                filepath = os.path.join(XLSX_FOLDER, file)
                files.append({
                    'name': file,
                    'type': 'xlsx',
                    'size': os.path.getsize(filepath),
                    'url': f'/api/download/xlsx/{file}'
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
        timestamp = datetime.now().strftime('%Y-%m-d %H:%M:%S')
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
        image_files = [f for f in os.listdir(IMAGE_FOLDER) if f.endswith(('.jpg', '.jpeg', '.png'))]
        xlsx_files = [f for f in os.listdir(XLSX_FOLDER) if f.endswith('.xlsx')]
        
        # Contar arquivos de email avançado
        email_templates = []
        email_attachments = []
        email_logs = []
        
        if os.path.exists(EMAIL_TEMPLATES_FOLDER):
            email_templates = [f for f in os.listdir(EMAIL_TEMPLATES_FOLDER) if f.endswith(('.html', '.txt'))]
        
        if os.path.exists(EMAIL_ATTACHMENTS_FOLDER):
            email_attachments = [f for f in os.listdir(EMAIL_ATTACHMENTS_FOLDER) if os.path.isfile(os.path.join(EMAIL_ATTACHMENTS_FOLDER, f))]
        
        if os.path.exists(EMAIL_LOGS_FOLDER):
            email_logs = [f for f in os.listdir(EMAIL_LOGS_FOLDER) if f.endswith('.json')]
        
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
            'image_files_count': len(image_files),
            'xlsx_files_count': len(xlsx_files),
            'email_templates_count': len(email_templates),
            'email_attachments_count': len(email_attachments),
            'email_logs_count': len(email_logs),
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
    os.makedirs('images', exist_ok=True)
    os.makedirs('xlsx', exist_ok=True)
    os.makedirs(EMAIL_TEMPLATES_FOLDER, exist_ok=True)
    os.makedirs(EMAIL_ATTACHMENTS_FOLDER, exist_ok=True)
    os.makedirs(EMAIL_LOGS_FOLDER, exist_ok=True)
    
    # Criar arquivos padrão se não existirem
    if not os.path.exists('contatos.txt'):
        with open('contatos.txt', 'w', encoding='utf-8') as f:
            f.write('hello@tiagoabreu.dev;tecnolocia.adm@promodatextil.ind.br')
    
    if not os.path.exists('mensagem_email.txt'):
        with open('mensagem_email.txt', 'w', encoding='utf-8') as f:
            f.write("""Prezado(a),

Segue em anexo o relatório consolidado de estoque DGB.

Este relatório foi gerado automaticamente pelo sistema DGB Scraper.

Atenciosamente,
Sistema DGB Scraper""")
    
    # Criar arquivo de contatos avançado com exemplo
    if not os.path.exists('contatos_avancado.txt'):
        with open('contatos_avancado.txt', 'w', encoding='utf-8') as f:
            f.write("""exemplo1@dominio.com;João Silva
exemplo2@dominio.com;Maria Santos
exemplo3@dominio.com;Carlos Oliveira""")
    
    # Criar template de exemplo
    if not os.path.exists(EMAIL_TEMPLATES_FOLDER):
        os.makedirs(EMAIL_TEMPLATES_FOLDER, exist_ok=True)
    
    exemplo_template = os.path.join(EMAIL_TEMPLATES_FOLDER, 'exemplo_boas_vindas.html')
    if not os.path.exists(exemplo_template):
        with open(exemplo_template, 'w', encoding='utf-8') as f:
            f.write("""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
        .header { background: #007bff; color: white; padding: 20px; text-align: center; }
        .content { padding: 20px; background: #f8f9fa; }
        .footer { text-align: center; padding: 20px; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Olá {{nome}}!</h1>
        </div>
        <div class="content">
            <p>Seja muito bem-vindo(a) ao nosso sistema!</p>
            <p>Seu email cadastrado é: {{email}}</p>
            <p>Estamos muito felizes em tê-lo(a) conosco.</p>
            <p>Qualquer dúvida, não hesite em nos contatar.</p>
        </div>
        <div class="footer">
            <p>Este é um email automático enviado pelo Sistema DGB Scraper</p>
            <p>© 2024 DGB COMEX. Todos os direitos reservados.</p>
        </div>
    </div>
</body>
</html>""")
    
    logger.info("✅ Sistema iniciado com sucesso!")
    logger.info("📧 Configuração de email: Gmail (dgbcomex@gmail.com)")
    logger.info(f"👤 Usuário: {os.getenv('DGB_USUARIO')}")
    logger.info(f"📁 Pasta CSV: {os.path.abspath('csv')}")
    logger.info(f"📊 Pasta XLSX: {os.path.abspath('xlsx')}")
    logger.info(f"🐛 Pasta Debug: {os.path.abspath('debug')}")
    logger.info(f"📄 Pasta PDFs: {os.path.abspath('pdfs')}")
    logger.info(f"🖼️  Pasta Images: {os.path.abspath('images')}")
    logger.info(f"📧 Pasta Templates Email: {os.path.abspath(EMAIL_TEMPLATES_FOLDER)}")
    logger.info(f"📎 Pasta Anexos Email: {os.path.abspath(EMAIL_ATTACHMENTS_FOLDER)}")
    logger.info(f"📋 Pasta Logs Email: {os.path.abspath(EMAIL_LOGS_FOLDER)}")
    
    app.run(host='0.0.0.0', port=5000, debug=True)