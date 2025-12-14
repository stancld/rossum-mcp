/**
 * Rossum Agent Test Client
 * Matches the Streamlit app workflow with markdown rendering
 */

const API = '/api/v1';
let chatId = null;
let sending = false;

// Agent response state (mirrors ChatResponse from Streamlit)
let completedStepsMarkdown = [];
let currentStepMarkdown = '';
let currentStepNum = 0;
let finalAnswerText = null;

// DOM
const $ = (sel) => document.querySelector(sel);
const apiUrl = $('#api-url');
const apiToken = $('#api-token');
const credStatus = $('#credentials-status');
const chatList = $('#chat-list');
const fileList = $('#file-list');
const messages = $('#messages');
const input = $('#input');
const send = $('#send');
const modeIndicator = $('#mode-indicator');
const currentMode = $('#current-mode');

// Init
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    setupEvents();
    if (hasCredentials()) {
        updateCredStatus(true);
        loadChats();
        enableInput();
    }
    updateModeIndicator();
});

function setupEvents() {
    $('#save-credentials').onclick = saveSettings;
    $('#reset-chat').onclick = resetConversation;
    $('#get-link').onclick = getShareableLink;
    $('#chat-form').onsubmit = handleSubmit;
    $('#toggle-token').onclick = toggleTokenVisibility;

    document.querySelectorAll('input[name="mode"]').forEach(radio => {
        radio.onchange = updateModeIndicator;
    });

    input.onkeydown = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit(e);
        }
    };
}

// Token visibility toggle
function toggleTokenVisibility() {
    const isPassword = apiToken.type === 'password';
    apiToken.type = isPassword ? 'text' : 'password';
    $('#toggle-token .eye-icon').textContent = isPassword ? '🙈' : '👁';
}

// Mode indicator
function updateModeIndicator() {
    const mode = document.querySelector('input[name="mode"]:checked').value;
    const isReadOnly = mode === 'read-only';
    currentMode.textContent = isReadOnly ? 'Read-Only' : 'Read-Write';
    modeIndicator.querySelector('.mode-lock').textContent = isReadOnly ? '🔒' : '✏️';
}

// Settings
function loadSettings() {
    apiUrl.value = localStorage.getItem('rossum_url') || '';
    apiToken.value = localStorage.getItem('rossum_token') || '';

    const savedMode = localStorage.getItem('rossum_mode') || 'read-only';
    const modeRadio = document.querySelector(`input[name="mode"][value="${savedMode}"]`);
    if (modeRadio) modeRadio.checked = true;
}

function saveSettings() {
    localStorage.setItem('rossum_url', apiUrl.value);
    localStorage.setItem('rossum_token', apiToken.value);
    localStorage.setItem('rossum_mode', document.querySelector('input[name="mode"]:checked').value);

    updateCredStatus(hasCredentials());
    if (hasCredentials()) {
        loadChats();
        enableInput();
        showToast('Credentials saved successfully', 'success');
    }
}

function hasCredentials() {
    return apiUrl.value && apiToken.value;
}

function updateCredStatus(ok) {
    if (ok) {
        credStatus.innerHTML = '<span class="banner-icon">✓</span> Credentials configured';
        credStatus.className = 'credentials-banner success';
    } else {
        credStatus.innerHTML = '<span class="banner-icon">⚠</span> Please enter your Rossum API credentials';
        credStatus.className = 'credentials-banner warning';
    }
}

function enableInput() {
    input.disabled = false;
    input.placeholder = 'Enter your instruction...';
    send.disabled = false;
}

function headers() {
    return {
        'Content-Type': 'application/json',
        'X-Rossum-Token': apiToken.value,
        'X-Rossum-Api-Url': apiUrl.value,
        'X-User-Id': 'test-user',
    };
}

// Quick Actions
async function resetConversation() {
    if (!chatId) {
        await newChat();
        return;
    }

    if (!confirm('Reset this conversation? All messages will be deleted.')) return;

    try {
        await fetch(`${API}/chats/${chatId}`, { method: 'DELETE', headers: headers() });
        chatId = null;
        messages.innerHTML = '';
        renderFiles([]);
        await loadChats();
        showToast('Conversation reset', 'success');
    } catch (e) {
        console.error('Reset failed:', e);
        showToast('Failed to reset conversation', 'error');
    }
}

function getShareableLink() {
    if (!chatId) {
        showToast('No active chat to share', 'error');
        return;
    }

    const url = `${window.location.origin}${window.location.pathname}?chat=${chatId}`;
    navigator.clipboard.writeText(url).then(() => {
        showToast('Link copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy link', 'error');
    });
}

function showToast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
}

// Chats
async function loadChats() {
    try {
        const res = await fetch(`${API}/chats`, { headers: headers() });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        renderChats(data.chats || []);

        // Auto-select first chat or create new one
        if (data.chats && data.chats.length > 0 && !chatId) {
            // Check URL for chat param
            const urlParams = new URLSearchParams(window.location.search);
            const urlChatId = urlParams.get('chat');
            if (urlChatId && data.chats.some(c => c.chat_id === urlChatId)) {
                selectChat(urlChatId);
            } else {
                selectChat(data.chats[0].chat_id);
            }
        } else if (!data.chats || data.chats.length === 0) {
            // No chats, create one automatically
            await newChat();
        }
    } catch (e) {
        console.error('Load chats failed:', e);
    }
}

function renderChats(chats) {
    chatList.innerHTML = '';

    chats.forEach(c => {
        const li = document.createElement('li');
        li.dataset.id = c.chat_id;
        if (c.chat_id === chatId) li.classList.add('active');

        const preview = (c.first_message || 'New chat').slice(0, 22);
        li.innerHTML = `
            <span>${escapeHtml(preview)}${c.first_message?.length > 22 ? '...' : ''}</span>
            <button class="delete" title="Delete">×</button>
        `;

        li.querySelector('span').onclick = () => selectChat(c.chat_id);
        li.querySelector('.delete').onclick = (e) => { e.stopPropagation(); deleteChat(c.chat_id); };
        chatList.appendChild(li);
    });
}

async function newChat() {
    try {
        const mode = document.querySelector('input[name="mode"]:checked').value;
        const res = await fetch(`${API}/chats`, {
            method: 'POST',
            headers: headers(),
            body: JSON.stringify({ mcp_mode: mode }),
        });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        await loadChats();
        selectChat(data.chat_id);
    } catch (e) {
        console.error('Create chat failed:', e);
    }
}

async function selectChat(id) {
    chatId = id;
    document.querySelectorAll('#chat-list li').forEach(li => {
        li.classList.toggle('active', li.dataset.id === id);
    });

    if (hasCredentials()) {
        enableInput();
    }

    try {
        const res = await fetch(`${API}/chats/${id}`, { headers: headers() });
        if (!res.ok) throw new Error(res.status);
        const data = await res.json();
        renderMessages(data.messages || []);
        renderFiles(data.files || []);
    } catch (e) {
        console.error('Load chat failed:', e);
    }
}

async function deleteChat(id) {
    if (!confirm('Delete this chat?')) return;
    try {
        await fetch(`${API}/chats/${id}`, { method: 'DELETE', headers: headers() });
        if (chatId === id) {
            chatId = null;
            messages.innerHTML = '';
            renderFiles([]);
        }
        loadChats();
    } catch (e) {
        console.error('Delete failed:', e);
    }
}

// Messages
function renderMessages(msgs) {
    messages.innerHTML = '';
    msgs.forEach(m => addMessage(m.role, m.content));
    scrollBottom();
}

function addMessage(role, content) {
    const div = document.createElement('div');
    div.className = `message ${role}`;

    if (role === 'assistant') {
        div.innerHTML = renderMarkdown(content);
    } else {
        div.textContent = content;
    }

    messages.appendChild(div);
}

function renderMarkdown(text) {
    if (typeof marked !== 'undefined') {
        marked.setOptions({
            breaks: true,
            gfm: true,
        });
        const html = marked.parse(text);
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(html);
        }
        return html;
    }
    return escapeHtml(text).replace(/\n/g, '<br>');
}

// Reset agent response state for new message
function resetAgentState() {
    completedStepsMarkdown = [];
    currentStepMarkdown = '';
    currentStepNum = 0;
    finalAnswerText = null;
}

// Create or get the agent response container
function getAgentResponseContainer() {
    let container = messages.querySelector('.agent-response:last-child');
    if (!container) {
        container = document.createElement('div');
        container.className = 'agent-response';
        messages.appendChild(container);
    }
    return container;
}

// Render the current agent state (mirrors _render_display from Streamlit)
function renderAgentDisplay(isStreaming = false, error = null) {
    const container = getAgentResponseContainer();

    let allSteps = [...completedStepsMarkdown];
    if (currentStepMarkdown) {
        allSteps.push(currentStepMarkdown);
    }

    let displayMd = allSteps.join('\n\n');

    if (isStreaming) {
        displayMd += '\n\n⏳ _Thinking..._';
    } else if (finalAnswerText === null && !error) {
        displayMd += '\n\n⏳ _Processing..._';
    } else if (finalAnswerText !== null) {
        displayMd += `\n\n---\n\n### ✅ Final Answer\n\n${finalAnswerText}`;
    } else if (error) {
        displayMd += `\n\n---\n\n### ❌ Error\n\n${error}`;
    }

    container.innerHTML = renderMarkdown(displayMd);
    scrollBottom();
}

async function handleSubmit(e) {
    e.preventDefault();
    const text = input.value.trim();
    if (!text || !chatId || sending) return;

    sending = true;
    input.disabled = true;
    send.disabled = true;

    addMessage('user', text);
    input.value = '';
    resetAgentState();
    scrollBottom();

    try {
        await sendMessage(text);
    } catch (e) {
        renderAgentDisplay(false, e.message);
    } finally {
        sending = false;
        input.disabled = false;
        send.disabled = false;
        input.focus();
        loadFiles();
        loadChats();
    }
}

async function sendMessage(content) {
    const res = await fetch(`${API}/chats/${chatId}/messages`, {
        method: 'POST',
        headers: { ...headers(), Accept: 'text/event-stream' },
        body: JSON.stringify({ content }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
            if (line.startsWith('data: ')) {
                try {
                    handleEvent(JSON.parse(line.slice(6)));
                } catch (e) {
                    console.error('Parse error:', line);
                }
            }
        }
    }
}

function handleEvent(e) {
    const stepNum = e.step_number || 1;

    switch (e.type) {
        case 'thinking':
            processStreamingStep(stepNum, e.content, e.is_streaming);
            break;
        case 'tool_start':
            processToolStart(stepNum, e.tool_name, e.tool_progress);
            break;
        case 'tool_result':
            processToolResult(stepNum, e.tool_name, e.result, e.is_error);
            break;
        case 'final_answer':
            processFinalAnswer(e.content, e.is_streaming);
            break;
        case 'error':
            renderAgentDisplay(false, e.content || e.message || 'Unknown error');
            break;
    }
}

function processStreamingStep(stepNum, thinking, isStreaming) {
    if (stepNum !== currentStepNum) {
        if (currentStepMarkdown) {
            completedStepsMarkdown.push(currentStepMarkdown);
        }
        currentStepNum = stepNum;
        currentStepMarkdown = `#### Step ${stepNum}\n`;
    }

    if (thinking) {
        currentStepMarkdown = `#### Step ${stepNum}\n\n💭 ${thinking}\n`;
    }

    renderAgentDisplay(isStreaming);
}

function processToolStart(stepNum, toolName, toolProgress) {
    if (stepNum !== currentStepNum) {
        if (currentStepMarkdown) {
            completedStepsMarkdown.push(currentStepMarkdown);
        }
        currentStepNum = stepNum;
        currentStepMarkdown = `#### Step ${stepNum}\n`;
    }

    let progressText = '';
    if (toolProgress && toolProgress.length === 2) {
        const [current, total] = toolProgress;
        progressText = `🔧 Running tool ${current}/${total}: **${toolName}**...`;
    } else {
        progressText = `🔧 Running tool: **${toolName}**...`;
    }

    // Preserve thinking if present
    const thinkingMatch = currentStepMarkdown.match(/💭 (.+)\n/);
    if (thinkingMatch) {
        currentStepMarkdown = `#### Step ${stepNum}\n\n💭 ${thinkingMatch[1]}\n\n${progressText}\n`;
    } else {
        currentStepMarkdown = `#### Step ${stepNum}\n\n${progressText}\n`;
    }

    renderAgentDisplay(true);
}

function processToolResult(stepNum, toolName, result, isError) {
    // Complete the current step with the tool result
    const stepMdParts = [`#### Step ${stepNum}\n`];

    const thinkingMatch = currentStepMarkdown.match(/💭 (.+)\n/);
    if (thinkingMatch) {
        stepMdParts.push(`💭 ${thinkingMatch[1]}\n`);
    }

    stepMdParts.push(`**Tools:** ${toolName}\n`);

    const content = result || '';
    if (isError) {
        stepMdParts.push(`**❌ ${toolName} Error:** ${content}\n`);
    } else if (content.length > 200) {
        stepMdParts.push(`<details><summary>📋 ${toolName} result</summary>\n\n\`\`\`\n${content}\n\`\`\`\n</details>\n`);
    } else {
        stepMdParts.push(`**Result (${toolName}):** ${content}\n`);
    }

    currentStepMarkdown = stepMdParts.join('\n');
    completedStepsMarkdown.push(currentStepMarkdown);
    currentStepMarkdown = '';

    renderAgentDisplay(false);
}

function processFinalAnswer(content, isStreaming) {
    if (isStreaming) {
        finalAnswerText = content;
        renderAgentDisplay(true);
    } else {
        finalAnswerText = parseAndFormatFinalAnswer(content || '');
        renderAgentDisplay(false);
    }
}

// Parse and format final answer (mirrors Python logic)
function parseAndFormatFinalAnswer(answer) {
    answer = answer.trim();

    try {
        const data = JSON.parse(answer);
        if (typeof data === 'object' && data !== null && !Array.isArray(data)) {
            return formatDictResponse(data);
        }
    } catch (e) {
        // Not JSON, return as-is
    }

    return answer;
}

function formatDictResponse(data) {
    const lines = [];
    const processedKeys = new Set();

    // Status
    if (data.status) {
        const statusEmoji = data.status === 'success' ? '✅' : '❌';
        lines.push(`### ${statusEmoji} Status: ${capitalize(data.status)}\n`);
        processedKeys.add('status');
    }

    // Summary
    if (data.summary) {
        lines.push('### 📝 Summary');
        lines.push(data.summary);
        lines.push('');
        processedKeys.add('summary');
    }

    // Generated files
    for (const key of Object.keys(data)) {
        if (!processedKeys.has(key) && Array.isArray(data[key]) &&
            (key.toLowerCase().includes('generated') || key.toLowerCase().includes('files'))) {
            lines.push(`### 📁 ${formatKey(key)}`);
            for (const item of data[key]) {
                if (typeof item === 'string') {
                    const fileName = item.includes('/') || item.includes('\\')
                        ? item.split(/[/\\]/).pop()
                        : item;
                    lines.push(`- \`${fileName}\``);
                } else {
                    lines.push(`- ${item}`);
                }
            }
            lines.push('');
            processedKeys.add(key);
        }
    }

    // Generic items
    for (const [key, value] of Object.entries(data)) {
        if (processedKeys.has(key)) continue;

        const formattedKey = formatKey(key);

        if (typeof value === 'object' && value !== null && !Array.isArray(value)) {
            lines.push(`### ${formattedKey}`);
            for (const [subKey, subValue] of Object.entries(value)) {
                lines.push(`- **${formatKey(subKey)}:** ${subValue}`);
            }
            lines.push('');
        } else if (Array.isArray(value)) {
            lines.push(`### ${formattedKey}`);
            for (const item of value) {
                lines.push(`- ${item}`);
            }
            lines.push('');
        } else {
            lines.push(`**${formattedKey}:** ${value}`);
        }
    }

    return lines.join('\n');
}

function formatKey(key) {
    return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
}

function capitalize(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Files
async function loadFiles() {
    if (!chatId) return;
    try {
        const res = await fetch(`${API}/chats/${chatId}/files`, { headers: headers() });
        if (!res.ok) return;
        const data = await res.json();
        renderFiles(data.files || []);
    } catch (e) {}
}

function renderFiles(files) {
    if (files.length === 0) {
        fileList.innerHTML = '<div class="empty-state warning">No files generated yet</div>';
        return;
    }

    fileList.innerHTML = '';
    files.forEach(f => {
        const a = document.createElement('a');
        a.href = `${API}/chats/${chatId}/files/${encodeURIComponent(f.filename)}`;
        a.download = f.filename;
        a.textContent = f.filename;
        fileList.appendChild(a);
    });
}

// Utils
function scrollBottom() {
    messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
