// static/js/email_editor.js
// Todas as funções JavaScript relacionadas ao editor de email avançado

let quillEditor = null;
let currentAttachments = [];
let currentContacts = [];

// ============================================
// FUNÇÕES DO EDITOR QUILL
// ============================================

function initQuillEditor() {
    const editorElement = document.getElementById('editor');
    if (!editorElement) return;
    
    // Configuração do Quill
    quillEditor = new Quill('#editor', {
        theme: 'snow',
        modules: {
            toolbar: [
                [{ 'header': [1, 2, 3, false] }],
                ['bold', 'italic', 'underline', 'strike'],
                [{ 'color': [] }, { 'background': [] }],
                [{ 'align': [] }],
                ['link', 'image'],
                ['clean']
            ]
        },
        placeholder: 'Digite o conteúdo do email aqui...'
    });
    
    // Sincronizar com HTML raw
    quillEditor.on('text-change', function() {
        const htmlRaw = document.getElementById('htmlRaw');
        if (htmlRaw) {
            htmlRaw.value = quillEditor.root.innerHTML;
        }
    });
    
    // Sincronizar HTML raw com editor
    const htmlRawElement = document.getElementById('htmlRaw');
    if (htmlRawElement) {
        htmlRawElement.addEventListener('input', function() {
            quillEditor.root.innerHTML = this.value;
        });
    }
}

function formatText(command) {
    if (!quillEditor) return;
    
    if (command === 'bold') {
        quillEditor.format('bold', !quillEditor.getFormat().bold);
    } else if (command === 'italic') {
        quillEditor.format('italic', !quillEditor.getFormat().italic);
    } else if (command === 'underline') {
        quillEditor.format('underline', !quillEditor.getFormat().underline);
    } else if (command === 'left') {
        quillEditor.format('align', 'left');
    } else if (command === 'center') {
        quillEditor.format('align', 'center');
    } else if (command === 'right') {
        quillEditor.format('align', 'right');
    }
}

function changeTextColor(color) {
    if (quillEditor) {
        quillEditor.format('color', color);
    }
}

function insertVariable(variable) {
    if (quillEditor) {
        const range = quillEditor.getSelection();
        if (range) {
            quillEditor.insertText(range.index, '{{' + variable + '}}');
        } else {
            quillEditor.insertText(quillEditor.getLength(), '{{' + variable + '}}');
        }
    }
}

// ============================================
// FUNÇÕES PARA GERENCIAMENTO DE CONTATOS
// ============================================

async function loadAdvancedContacts() {
    try {
        const response = await fetch('/api/email-avancado/contatos');
        const data = await response.json();
        
        if (data.success) {
            currentContacts = data.contacts || [];
            displayContacts(currentContacts);
            const contactsRaw = document.getElementById('contactsRaw');
            if (contactsRaw) {
                contactsRaw.value = data.raw_content || '';
            }
            
            console.log('Contatos avançados carregados');
        } else {
            console.error('Erro ao carregar contatos:', data.error);
        }
    } catch (error) {
        console.error('Erro ao carregar contatos:', error);
    }
}

function displayContacts(contacts) {
    const container = document.getElementById('contactsList');
    if (!container) return;
    
    if (contacts.length === 0) {
        container.innerHTML = '<p class="text-muted">Nenhum contato carregado</p>';
        return;
    }
    
    let html = '<div class="list-group">';
    contacts.forEach((contact, index) => {
        html += `
            <div class="list-group-item list-group-item-action d-flex justify-content-between align-items-center">
                <div>
                    <strong>${contact.nome || 'Sem nome'}</strong><br>
                    <small class="text-muted">${contact.email}</small>
                </div>
                <button class="btn btn-sm btn-outline-danger" onclick="removeContact(${index})">
                    <i class="bi bi-trash"></i>
                </button>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

function addContactManually() {
    const email = prompt("Digite o email:");
    if (!email || !email.includes('@')) {
        alert('Email inválido!');
        return;
    }
    
    const nome = prompt("Digite o nome (opcional):", "");
    
    currentContacts.push({
        email: email.trim(),
        nome: nome ? nome.trim() : ''
    });
    
    displayContacts(currentContacts);
    updateContactsRaw();
}

function removeContact(index) {
    if (confirm('Remover este contato?')) {
        currentContacts.splice(index, 1);
        displayContacts(currentContacts);
        updateContactsRaw();
    }
}

function updateContactsRaw() {
    const rawText = currentContacts.map(c => 
        `${c.email};${c.nome || ''}`
    ).join('\n');
    
    const contactsRaw = document.getElementById('contactsRaw');
    if (contactsRaw) {
        contactsRaw.value = rawText;
    }
}

async function saveAdvancedContacts() {
    const contactsRaw = document.getElementById('contactsRaw');
    if (!contactsRaw) return;
    
    const rawContent = contactsRaw.value.trim();
    
    try {
        const response = await fetch('/api/email-avancado/contatos', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ contacts: rawContent })
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Contatos salvos com sucesso');
            await loadAdvancedContacts();
        } else {
            console.error('Erro ao salvar contatos:', data.error);
        }
    } catch (error) {
        console.error('Erro ao salvar contatos:', error);
    }
}

// ============================================
// FUNÇÕES PARA GERENCIAMENTO DE TEMPLATES
// ============================================

async function loadEmailTemplates() {
    try {
        const response = await fetch('/api/email-avancado/templates');
        const data = await response.json();
        
        if (data.success) {
            const select = document.getElementById('templateSelect');
            if (!select) return;
            
            // Limpar opções exceto a primeira
            while (select.options.length > 1) {
                select.remove(1);
            }
            
            // Adicionar templates
            data.templates.forEach(template => {
                const option = document.createElement('option');
                option.value = template.name;
                option.textContent = template.name + ` (${template.type})`;
                select.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Erro ao carregar templates:', error);
    }
}

async function loadTemplate() {
    const select = document.getElementById('templateSelect');
    if (!select) return;
    
    const templateName = select.value;
    if (!templateName) return;
    
    try {
        const response = await fetch('/api/email-avancado/templates');
        const data = await response.json();
        
        if (data.success) {
            const template = data.templates.find(t => t.name === templateName);
            if (template) {
                if (quillEditor) {
                    quillEditor.root.innerHTML = template.content;
                }
                const htmlRaw = document.getElementById('htmlRaw');
                if (htmlRaw) {
                    htmlRaw.value = template.content;
                }
                console.log(`Template "${templateName}" carregado`);
            }
        }
    } catch (error) {
        console.error('Erro ao carregar template:', error);
    }
}

async function saveAsTemplate() {
    const templateName = prompt("Nome do template:");
    if (!templateName) return;
    
    const content = quillEditor ? quillEditor.root.innerHTML : '';
    
    try {
        const response = await fetch('/api/email-avancado/templates', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: templateName,
                content: content,
                type: 'html'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Template salvo com sucesso');
            await loadEmailTemplates();
        } else {
            console.error('Erro ao salvar template:', data.error);
        }
    } catch (error) {
        console.error('Erro ao salvar template:', error);
    }
}

async function deleteTemplate() {
    const select = document.getElementById('templateSelect');
    if (!select) return;
    
    const templateName = select.value;
    if (!templateName) {
        alert('Selecione um template para excluir!');
        return;
    }
    
    if (!confirm(`Excluir template "${templateName}"?`)) return;
    
    try {
        const response = await fetch('/api/email-avancado/templates', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: templateName })
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Template excluído com sucesso');
            await loadEmailTemplates();
            select.value = '';
        } else {
            console.error('Erro ao excluir template:', data.error);
        }
    } catch (error) {
        console.error('Erro ao excluir template:', error);
    }
}

// ============================================
// FUNÇÕES PARA GERENCIAMENTO DE ANEXOS
// ============================================

async function loadEmailAttachments() {
    try {
        const response = await fetch('/api/email-avancado/attachments');
        const data = await response.json();
        
        if (data.success) {
            currentAttachments = data.attachments || [];
            displayAttachments(currentAttachments);
        }
    } catch (error) {
        console.error('Erro ao carregar anexos:', error);
    }
}

function displayAttachments(attachments) {
    const container = document.getElementById('attachmentsList');
    if (!container) return;
    
    if (attachments.length === 0) {
        container.innerHTML = '<p class="text-muted">Nenhum anexo</p>';
        return;
    }
    
    let html = '<div class="list-group">';
    attachments.forEach((attachment, index) => {
        const sizeKB = (attachment.size / 1024).toFixed(1);
        html += `
            <div class="list-group-item d-flex justify-content-between align-items-center">
                <div style="max-width: 70%;">
                    <small>${attachment.original_name}</small><br>
                    <span class="badge bg-secondary">${sizeKB} KB</span>
                </div>
                <div>
                    <button class="btn btn-sm btn-outline-info me-1" onclick="downloadAttachment('${attachment.filename}')">
                        <i class="bi bi-download"></i>
                    </button>
                    <button class="btn btn-sm btn-outline-danger" onclick="removeAttachment('${attachment.filename}')">
                        <i class="bi bi-trash"></i>
                    </button>
                </div>
            </div>
        `;
    });
    html += '</div>';
    
    container.innerHTML = html;
}

async function uploadAttachments() {
    const fileInput = document.getElementById('fileUpload');
    if (!fileInput) return;
    
    const files = fileInput.files;
    
    if (files.length === 0) {
        alert('Selecione pelo menos um arquivo!');
        return;
    }
    
    // Verificar tamanho total
    let totalSize = 0;
    for (let file of files) {
        totalSize += file.size;
        if (file.size > 10 * 1024 * 1024) { // 10MB
            alert(`Arquivo "${file.name}" excede 10MB!`);
            return;
        }
    }
    
    if (totalSize > 50 * 1024 * 1024) { // 50MB total
        alert('Tamanho total dos arquivos excede 50MB!');
        return;
    }
    
    // Upload de cada arquivo
    for (let file of files) {
        const formData = new FormData();
        formData.append('file', file);
        
        try {
            const response = await fetch('/api/email-avancado/upload', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.success) {
                console.log(`Arquivo "${file.name}" enviado`);
            } else {
                console.error(`Erro ao enviar "${file.name}":`, data.error);
            }
        } catch (error) {
            console.error(`Erro ao enviar "${file.name}":`, error);
        }
    }
    
    // Limpar input e recarregar lista
    fileInput.value = '';
    await loadEmailAttachments();
}

function downloadAttachment(filename) {
    window.open(`/api/email-avancado/download/${filename}`, '_blank');
}

async function removeAttachment(filename) {
    if (!confirm('Remover este anexo?')) return;
    
    try {
        const response = await fetch('/api/email-avancado/attachments', {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ filename: filename })
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Anexo removido com sucesso');
            await loadEmailAttachments();
        } else {
            console.error('Erro ao remover anexo:', data.error);
        }
    } catch (error) {
        console.error('Erro ao remover anexo:', error);
    }
}

// ============================================
// FUNÇÕES PARA PRÉ-VISUALIZAÇÃO E ENVIO
// ============================================

function previewEmail() {
    const subjectInput = document.getElementById('emailSubject');
    const subject = subjectInput ? subjectInput.value : '(Sem assunto)';
    const htmlContent = quillEditor ? quillEditor.root.innerHTML : '';
    const textPlain = document.getElementById('textPlain');
    const textContent = textPlain ? textPlain.value : '';
    
    // Substituir variáveis com exemplo
    let previewHtml = htmlContent
        .replace(/{{nome}}/g, 'João Silva')
        .replace(/{{email}}/g, 'joao@exemplo.com');
    
    let previewText = textContent
        .replace(/{{nome}}/g, 'João Silva')
        .replace(/{{email}}/g, 'joao@exemplo.com');
    
    // Mostrar preview em modal (simplificado)
    const previewContent = `
        <div class="card">
            <div class="card-header bg-info text-white">
                <h5 class="mb-0">Pré-visualização do Email</h5>
            </div>
            <div class="card-body">
                <h6>Assunto: ${subject}</h6>
                <hr>
                <h6>Visualização HTML:</h6>
                <div class="email-preview mb-3">
                    ${previewHtml || '<p class="text-muted">(Sem conteúdo HTML)</p>'}
                </div>
                <h6>Texto Simples:</h6>
                <pre class="bg-light p-3">${previewText || '(Sem texto simples)'}</pre>
            </div>
        </div>
    `;
    
    // Usar alerta simplificado por enquanto
    const modal = document.createElement('div');
    modal.className = 'modal fade show d-block';
    modal.style.backgroundColor = 'rgba(0,0,0,0.5)';
    modal.innerHTML = `
        <div class="modal-dialog modal-lg">
            <div class="modal-content">
                <div class="modal-header">
                    <h5 class="modal-title">Pré-visualização</h5>
                    <button type="button" class="btn-close" onclick="this.closest('.modal').remove()"></button>
                </div>
                <div class="modal-body">
                    ${previewContent}
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="this.closest('.modal').remove()">Fechar</button>
                </div>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
}

function prepareMassSend() {
    // Validar dados
    const subjectInput = document.getElementById('emailSubject');
    if (!subjectInput) {
        alert('Elemento de assunto não encontrado!');
        return;
    }
    
    const subject = subjectInput.value.trim();
    if (!subject) {
        alert('Digite o assunto do email!');
        return;
    }
    
    const htmlContent = quillEditor ? quillEditor.root.innerHTML.trim() : '';
    const textPlain = document.getElementById('textPlain');
    const textContent = textPlain ? textPlain.value.trim() : '';
    
    if (!htmlContent && !textContent) {
        alert('Digite o conteúdo do email (HTML ou texto simples)!');
        return;
    }
    
    if (currentContacts.length === 0) {
        alert('Adicione pelo menos um contato!');
        return;
    }
    
    const sendTypeSelect = document.getElementById('emailSendType');
    const sendType = sendTypeSelect ? sendTypeSelect.value : 'individual';
    const attachmentNames = currentAttachments.map(a => a.filename);
    
    // Preparar detalhes para o modal de confirmação
    const details = `
        <p><strong>Assunto:</strong> ${subject}</p>
        <p><strong>Tipo de Envio:</strong> ${sendType === 'individual' ? 'Individual' : sendType === 'cc' ? 'Com Cópia (CC)' : 'Cópia Oculta (BCC)'}</p>
        <p><strong>Contatos:</strong> ${currentContacts.length} emails</p>
        <p><strong>Anexos:</strong> ${attachmentNames.length} arquivos</p>
        <p><strong>Conteúdo HTML:</strong> ${htmlContent.length} caracteres</p>
        <p><strong>Texto Simples:</strong> ${textContent.length} caracteres</p>
        <hr>
        <p class="text-danger">
            <i class="bi bi-exclamation-triangle"></i>
            <strong>Atenção:</strong> Esta ação enviará emails para todos os contatos listados.
        </p>
    `;
    
    const massSendDetails = document.getElementById('massSendDetails');
    if (massSendDetails) {
        massSendDetails.innerHTML = details;
    }
    
    // Armazenar dados para envio
    window.massSendData = {
        subject: subject,
        html_content: htmlContent,
        text_content: textContent,
        contacts: currentContacts,
        attachments: attachmentNames,
        send_type: sendType
    };
    
    // Mostrar modal de confirmação
    const massSendModal = new bootstrap.Modal(document.getElementById('massSendModal'));
    massSendModal.show();
}

async function confirmMassSend() {
    if (!window.massSendData) return;
    
    // Mostrar progresso
    const progressElement = document.getElementById('massSendProgress');
    const progressBar = document.getElementById('massSendProgressBar');
    const massSendLog = document.getElementById('massSendLog');
    
    if (progressElement) progressElement.style.display = 'block';
    if (progressBar) progressBar.style.width = '0%';
    if (massSendLog) massSendLog.innerHTML = '';
    
    try {
        const response = await fetch('/api/email-avancado/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(window.massSendData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Atualizar progresso
            if (progressBar) progressBar.style.width = '100%';
            
            // Mostrar resultado
            let logHtml = `
                <div class="alert alert-success">
                    <strong>✅ ${data.message}</strong>
                </div>
                <p><strong>Enviados:</strong> ${data.sent}</p>
                <p><strong>Falhas:</strong> ${data.failed}</p>
            `;
            
            if (massSendLog) {
                massSendLog.innerHTML = logHtml;
            }
            
            // Atualizar logs de email
            await loadEmailLogs();
            
        } else {
            if (massSendLog) {
                massSendLog.innerHTML = `
                    <div class="alert alert-danger">
                        <strong>❌ Erro:</strong> ${data.error}
                    </div>
                `;
            }
        }
        
    } catch (error) {
        if (massSendLog) {
            massSendLog.innerHTML = `
                <div class="alert alert-danger">
                    <strong>❌ Erro no envio:</strong> ${error}
                </div>
            `;
        }
    }
}

async function testSingleEmail() {
    const testEmail = prompt("Digite um email para teste:");
    if (!testEmail || !testEmail.includes('@')) {
        alert('Email inválido!');
        return;
    }
    
    const testName = prompt("Digite um nome para teste:", "Teste");
    
    const subjectInput = document.getElementById('emailSubject');
    const subject = subjectInput ? subjectInput.value : 'Teste de Email';
    
    // Criar dados de teste
    const testData = {
        subject: subject,
        html_content: quillEditor ? quillEditor.root.innerHTML : '',
        text_content: document.getElementById('textPlain') ? document.getElementById('textPlain').value : '',
        contacts: [{
            email: testEmail,
            nome: testName
        }],
        attachments: [],
        send_type: 'individual'
    };
    
    try {
        const response = await fetch('/api/email-avancado/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(testData)
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Email de teste enviado para: ${testEmail}`);
        } else {
            alert(`❌ Erro: ${data.error}`);
        }
    } catch (error) {
        alert(`❌ Erro: ${error}`);
    }
}

// ============================================
// FUNÇÕES PARA LOGS E LIMPEZA
// ============================================

async function loadEmailLogs() {
    try {
        const response = await fetch('/api/email-avancado/logs');
        const data = await response.json();
        
        if (data.success) {
            // Atualizar dashboard se houver elemento específico
            const logsBadge = document.getElementById('emailLogsBadge');
            if (logsBadge) {
                logsBadge.textContent = data.logs.length;
            }
        }
    } catch (error) {
        console.error('Erro ao carregar logs:', error);
    }
}

async function cleanEmailData() {
    if (!confirm('Limpar todos os anexos temporários de email?')) return;
    
    try {
        const response = await fetch('/api/email-avancado/clean-attachments', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (data.success) {
            console.log('Anexos limpos com sucesso');
            await loadEmailAttachments();
        } else {
            console.error('Erro ao limpar anexos:', data.error);
        }
    } catch (error) {
        console.error('Erro ao limpar anexos:', error);
    }
}

// ============================================
// INICIALIZAÇÃO DO EDITOR
// ============================================

function initEmailEditor() {
    // Inicializar editor Quill
    initQuillEditor();
    
    // Carregar dados iniciais
    loadAdvancedContacts();
    loadEmailTemplates();
    loadEmailAttachments();
    loadEmailLogs();
    
    console.log('Editor de email inicializado');
}

// Torna as funções disponíveis globalmente
window.initQuillEditor = initQuillEditor;
window.formatText = formatText;
window.changeTextColor = changeTextColor;
window.insertVariable = insertVariable;
window.loadAdvancedContacts = loadAdvancedContacts;
window.addContactManually = addContactManually;
window.removeContact = removeContact;
window.saveAdvancedContacts = saveAdvancedContacts;
window.loadTemplate = loadTemplate;
window.saveAsTemplate = saveAsTemplate;
window.deleteTemplate = deleteTemplate;
window.uploadAttachments = uploadAttachments;
window.downloadAttachment = downloadAttachment;
window.removeAttachment = removeAttachment;
window.previewEmail = previewEmail;
window.prepareMassSend = prepareMassSend;
window.confirmMassSend = confirmMassSend;
window.testSingleEmail = testSingleEmail;
window.cleanEmailData = cleanEmailData;
window.initEmailEditor = initEmailEditor;