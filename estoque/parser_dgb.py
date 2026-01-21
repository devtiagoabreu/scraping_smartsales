# parser_dgb.py - Parser específico para HTML do DGB
import os
import re
import csv
from datetime import datetime
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)

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

def parse_html_dgb_simples(html_content, produto_codigo):
    """Parser SIMPLES e DIRETO para HTML do DGB"""
    registros = []
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    artigo = str(produto_codigo).lstrip('0')
    
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remover scripts e styles
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Pegar TODO o texto
        texto_completo = soup.get_text(separator='\n')
        
        # Salvar texto para debug
        debug_dir = os.path.join('data', 'debug_parser')
        os.makedirs(debug_dir, exist_ok=True)
        debug_file = os.path.join(debug_dir, f"parser_{produto_codigo}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(debug_file, 'w', encoding='utf-8') as f:
            f.write(texto_completo)
        
        logger.info(f"📄 Texto extraído salvo em: {debug_file}")
        
        # Dividir em linhas
        lines = texto_completo.split('\n')
        lines = [line.strip() for line in lines if line.strip()]
        
        # Procurar pelo produto
        produto_encontrado = False
        descricao = f"Produto {produto_codigo}"
        
        for i, line in enumerate(lines):
            # Verificar se a linha contém o produto
            if str(produto_codigo) in line:
                produto_encontrado = True
                descricao = line
                logger.info(f"✅ Produto encontrado na linha {i}: {line[:100]}")
                
                # Procurar por linhas de dados nas próximas 20 linhas
                for j in range(i, min(i + 20, len(lines))):
                    data_line = lines[j]
                    
                    # Verificar se é uma linha de dados
                    if (re.match(r'^\d{2}/\d{2}/\d{4}$', data_line) or 
                        data_line.lower() == 'pronta entrega'):
                        
                        previsao = data_line
                        logger.info(f"📅 Previsão encontrada: {previsao}")
                        
                        # Procurar por 3 números nas próximas linhas
                        valores_encontrados = []
                        for k in range(j + 1, min(j + 10, len(lines))):
                            num_line = lines[k]
                            
                            # Extrair números desta linha
                            numeros = re.findall(r'[\d.,]+', num_line)
                            if numeros:
                                valores_encontrados.extend(numeros)
                                logger.info(f"🔢 Números encontrados: {numeros}")
                            
                            # Se já temos 3 números, para
                            if len(valores_encontrados) >= 3:
                                break
                        
                        # Se encontrou 3 valores, criar registro
                        if len(valores_encontrados) >= 3:
                            registro = [
                                artigo,
                                timestamp,
                                descricao,
                                previsao,
                                formatar_valor_csv(valores_encontrados[0]),
                                formatar_valor_csv(valores_encontrados[1]),
                                formatar_valor_csv(valores_encontrados[2])
                            ]
                            registros.append(registro)
                            logger.info(f"✅ Registro criado: {previsao} | {valores_encontrados[0]}, {valores_encontrados[1]}, {valores_encontrados[2]}")
        
        if not produto_encontrado:
            logger.warning(f"⚠️ Produto {produto_codigo} não encontrado no texto")
        
        logger.info(f"📊 Total de registros extraídos: {len(registros)}")
        
    except Exception as e:
        logger.error(f"❌ Erro no parser simples: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    return registros

def criar_csv_direto(html_path, produto_codigo, output_dir='data/csv'):
    """Cria CSV diretamente de um arquivo HTML"""
    try:
        # Ler HTML
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            html_content = f.read()
        
        # Usar parser simples
        registros = parse_html_dgb_simples(html_content, produto_codigo)
        
        if not registros:
            logger.warning(f"⚠️ Nenhum registro extraído para {produto_codigo}")
            return None
        
        # Criar CSV
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"produto_{produto_codigo}_TINTO_{timestamp}.csv"
        filepath = os.path.join(output_dir, filename)
        
        # Cabeçalho
        cabecalho = ['artigo', 'datahora', 'Produto / Situação / Cor / Desenho / Variante', 
                    'Previsão', 'Estoque', 'Pedidos', 'Disponível']
        
        with open(filepath, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(cabecalho)
            
            for registro in registros:
                writer.writerow(registro)
        
        logger.info(f"✅ CSV criado: {filename} ({len(registros)} registros)")
        return filename
        
    except Exception as e:
        logger.error(f"❌ Erro ao criar CSV direto: {e}")
        return None

# Teste direto
if __name__ == "__main__":
    # Testar com um arquivo específico
    import sys
    
    if len(sys.argv) > 1:
        produto = sys.argv[1]
        html_file = f"data/debug/debug_html_{produto}_*.html"
        
        import glob
        files = glob.glob(html_file)
        
        if files:
            criar_csv_direto(files[0], produto)
        else:
            print(f"❌ Arquivo não encontrado: {html_file}")
    else:
        print("Uso: python parser_dgb.py <código_produto>")