// Funciones JavaScript comunes para el Grabador de Tareas

// Variables globales
let notificationTimeout;

// Inicialización cuando el DOM está listo
document.addEventListener('DOMContentLoaded', function() {
    // Inicializar tooltips de Bootstrap
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Inicializar popovers de Bootstrap
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Auto-hide alerts después de 5 segundos
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);

    // Actualizar indicadores de estado
    updateStatusIndicators();
    setInterval(updateStatusIndicators, 2000);
});

// Funciones de utilidad
function showNotification(message, type = 'info', duration = 5000) {
    // Crear elemento de notificación
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    notification.style.cssText = `
        top: 20px;
        right: 20px;
        z-index: 1060;
        min-width: 300px;
        max-width: 500px;
        box-shadow: 0 0.5rem 1rem rgba(0, 0, 0, 0.15);
    `;

    notification.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="fas fa-${getIconForType(type)} me-2"></i>
            <div class="flex-grow-1">${message}</div>
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>
    `;

    // Agregar al DOM
    document.body.appendChild(notification);

    // Auto-remove después del tiempo especificado
    setTimeout(() => {
        if (notification.parentNode) {
            const bsAlert = new bootstrap.Alert(notification);
            bsAlert.close();
        }
    }, duration);

    return notification;
}

function getIconForType(type) {
    const icons = {
        'success': 'check-circle',
        'danger': 'exclamation-triangle',
        'warning': 'exclamation-circle',
        'info': 'info-circle',
        'primary': 'info-circle',
        'secondary': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

function showConfirmDialog(title, message, onConfirm, onCancel = null) {
    // Crear modal de confirmación dinámicamente
    const modalId = 'confirmModal_' + Date.now();
    const modalHtml = `
        <div class="modal fade" id="${modalId}" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">
                            <i class="fas fa-question-circle me-2 text-warning"></i>
                            ${title}
                        </h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        ${message}
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cancelar</button>
                        <button type="button" class="btn btn-primary" id="${modalId}_confirm">Confirmar</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Agregar al DOM
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    const modalElement = document.getElementById(modalId);
    const modal = new bootstrap.Modal(modalElement);

    // Event listeners
    document.getElementById(modalId + '_confirm').addEventListener('click', function() {
        modal.hide();
        if (onConfirm) onConfirm();
    });

    modalElement.addEventListener('hidden.bs.modal', function() {
        modalElement.remove();
        if (onCancel) onCancel();
    });

    modal.show();
    return modal;
}

function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('es-ES', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function formatDuration(seconds) {
    if (seconds < 60) {
        return `${Math.round(seconds)}s`;
    } else if (seconds < 3600) {
        return `${Math.round(seconds / 60)}m`;
    } else {
        return `${Math.round(seconds / 3600)}h`;
    }
}

function copyTextToClipboard(text) {
    return navigator.clipboard.writeText(text).then(() => {
        showNotification('Texto copiado al portapapeles', 'success', 2000);
        return true;
    }).catch(err => {
        console.error('Error al copiar al portapapeles:', err);
        showNotification('Error al copiar al portapapeles', 'danger');
        return false;
    });
}

function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
        const context = this;
        const args = arguments;
        const later = function() {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
}

function throttle(func, limit) {
    let inThrottle;
    return function() {
        const args = arguments;
        const context = this;
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Funciones de API
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
        },
    };

    const finalOptions = { ...defaultOptions, ...options };

    try {
        const response = await fetch(url, finalOptions);
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.message || `HTTP error! status: ${response.status}`);
        }

        return { success: true, data };
    } catch (error) {
        console.error('API Request Error:', error);
        return { success: false, error: error.message };
    }
}

// Funciones de estado
function updateStatusIndicators() {
    // Actualizar indicadores de estado en la navbar
    const statusIndicator = document.getElementById('status-indicator');
    if (statusIndicator) {
        // Esta función se puede expandir para mostrar estado real del sistema
        updateServerStatus();
    }
}

async function updateServerStatus() {
    try {
        const result = await apiRequest('/api/recording/status');
        if (result.success) {
            const statusIndicator = document.getElementById('status-indicator');
            const uiState = window.webRecordingUiState || {};
            if (!uiState.isRecording && !uiState.isStopping) {
                statusIndicator.classList.add('d-none');
            } else if (uiState.isStopping || result.data.is_stopping) {
                statusIndicator.classList.remove('d-none');
                statusIndicator.className = 'badge bg-warning text-dark';
                statusIndicator.innerHTML = '<i class="fas fa-circle me-1"></i>Deteniendo';
            } else if (result.data.recording_error) {
                statusIndicator.classList.remove('d-none');
                statusIndicator.className = 'badge bg-danger recording';
                statusIndicator.innerHTML = '<i class="fas fa-circle me-1"></i>Error grabando';
            } else if (result.data.is_recording && !result.data.listeners_ready) {
                statusIndicator.classList.remove('d-none');
                statusIndicator.className = 'badge bg-warning text-dark';
                statusIndicator.innerHTML = '<i class="fas fa-circle me-1"></i>Inicializando';
            } else if (result.data.is_recording) {
                statusIndicator.classList.remove('d-none');
                statusIndicator.className = 'badge bg-danger recording';
                statusIndicator.innerHTML = '<i class="fas fa-circle me-1"></i>Grabando';
            }
        }
    } catch (error) {
        console.error('Error updating server status:', error);
    }
}

// Funciones de validación
function validateTaskName(name) {
    if (!name || name.trim().length === 0) {
        return { valid: false, message: 'El nombre de la tarea es requerido' };
    }

    if (name.trim().length < 3) {
        return { valid: false, message: 'El nombre debe tener al menos 3 caracteres' };
    }

    if (name.trim().length > 100) {
        return { valid: false, message: 'El nombre no puede exceder 100 caracteres' };
    }

    // Caracteres no permitidos
    const invalidChars = /[<>:"/\\|?*]/;
    if (invalidChars.test(name)) {
        return { valid: false, message: 'El nombre contiene caracteres no permitidos' };
    }

    return { valid: true };
}

function validatePromptTemplate(template) {
    if (!template || template.trim().length === 0) {
        return { valid: true }; // Prompt template es opcional
    }

    if (template.trim().length > 10000) {
        return { valid: false, message: 'La plantilla de prompt es demasiado larga' };
    }

    return { valid: true };
}

// Funciones de formato
function highlightPlaceholders(text) {
    return text.replace(/{CONTENIDO_DINAMICO}/g,
        '<span class="badge bg-warning text-dark">{CONTENIDO_DINAMICO}</span>');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function unescapeHtml(html) {
    const div = document.createElement('div');
    div.innerHTML = html;
    return div.textContent || div.innerText || '';
}

// Funciones de animación
function fadeIn(element, duration = 300) {
    element.style.opacity = '0';
    element.style.display = 'block';

    let start = null;
    function animate(timestamp) {
        if (!start) start = timestamp;
        const progress = timestamp - start;
        const opacity = Math.min(progress / duration, 1);

        element.style.opacity = opacity;

        if (progress < duration) {
            requestAnimationFrame(animate);
        }
    }

    requestAnimationFrame(animate);
}

function fadeOut(element, duration = 300) {
    let start = null;
    const initialOpacity = parseFloat(getComputedStyle(element).opacity);

    function animate(timestamp) {
        if (!start) start = timestamp;
        const progress = timestamp - start;
        const opacity = Math.max(initialOpacity - (progress / duration), 0);

        element.style.opacity = opacity;

        if (progress < duration) {
            requestAnimationFrame(animate);
        } else {
            element.style.display = 'none';
        }
    }

    requestAnimationFrame(animate);
}

function slideDown(element, duration = 300) {
    element.style.height = '0px';
    element.style.overflow = 'hidden';
    element.style.display = 'block';

    const targetHeight = element.scrollHeight + 'px';

    let start = null;
    function animate(timestamp) {
        if (!start) start = timestamp;
        const progress = timestamp - start;
        const height = Math.min((progress / duration) * parseInt(targetHeight), parseInt(targetHeight));

        element.style.height = height + 'px';

        if (progress < duration) {
            requestAnimationFrame(animate);
        } else {
            element.style.height = '';
            element.style.overflow = '';
        }
    }

    requestAnimationFrame(animate);
}

// Funciones de localStorage
function saveToLocalStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
        return true;
    } catch (error) {
        console.error('Error saving to localStorage:', error);
        return false;
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
        console.error('Error loading from localStorage:', error);
        return defaultValue;
    }
}

function removeFromLocalStorage(key) {
    try {
        localStorage.removeItem(key);
        return true;
    } catch (error) {
        console.error('Error removing from localStorage:', error);
        return false;
    }
}

// Funciones de configuración de usuario
function getUserPreferences() {
    return loadFromLocalStorage('userPreferences', {
        theme: 'light',
        autoSave: true,
        notifications: true,
        animationsEnabled: true
    });
}

function saveUserPreferences(preferences) {
    return saveToLocalStorage('userPreferences', preferences);
}

// Inicializar preferencias de usuario
function initializeUserPreferences() {
    const preferences = getUserPreferences();

    // Aplicar tema
    if (preferences.theme === 'dark') {
        document.body.classList.add('dark-theme');
    }

    // Configurar animaciones
    if (!preferences.animationsEnabled) {
        document.body.classList.add('no-animations');
    }
}

// Funciones de manejo de errores
function handleApiError(error, context = '') {
    console.error(`API Error ${context}:`, error);

    let message = 'Ha ocurrido un error inesperado';

    if (error.message) {
        if (error.message.includes('fetch')) {
            message = 'Error de conexión con el servidor';
        } else if (error.message.includes('JSON')) {
            message = 'Error en la respuesta del servidor';
        } else {
            message = error.message;
        }
    }

    showNotification(message, 'danger');
    return message;
}

// Exportar funciones para uso global
window.TaskRecorderUtils = {
    showNotification,
    showConfirmDialog,
    formatDateTime,
    formatDuration,
    copyTextToClipboard,
    debounce,
    throttle,
    apiRequest,
    validateTaskName,
    validatePromptTemplate,
    highlightPlaceholders,
    escapeHtml,
    unescapeHtml,
    fadeIn,
    fadeOut,
    slideDown,
    saveToLocalStorage,
    loadFromLocalStorage,
    removeFromLocalStorage,
    getUserPreferences,
    saveUserPreferences,
    handleApiError
};

// Actualizar estado cada 30 segundos
setInterval(updateStatusIndicators, 30000);
