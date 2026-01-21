# No terminal (Prompt de Comando ou PowerShell), vá até a pasta do projeto:
cd caminho\do\seu\projeto

# Crie o ambiente virtual  venv: 
python -m venv venv

# Ativar o ambiente virtual
# Prompt de Comando (cmd)
venv\Scripts\activate

# PowerShell
venv\Scripts\Activate.ps1

# Se aparecer erro de política de execução no PowerShell, execute uma vez:
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned

# Instalar dependências dentro do venv
pip install -r requirements.txt