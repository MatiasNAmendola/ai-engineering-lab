/**
 * Curriculum Textbook Engine - SPA Application Client
 */

class EduTextApp {
    constructor() {
        this.apiBase = '/api';
        this.activeView = 'dashboard-view';
        this.books = [];
        this.pendingReviews = [];
        this.activeBook = null;
        this.activeSeq = null;
        this.activeReviewSeq = null;
        this.pollInterval = null;

        // Bind DOM elements
        this.initDOMElements();
        // Register Event Listeners
        this.registerEvents();
        // Initialize State
        this.init();
    }

    initDOMElements() {
        this.navLinks = document.querySelectorAll('.nav-link');
        this.views = document.querySelectorAll('.view-section');
        this.booksTable = document.querySelector('#books-table tbody');
        this.requirementsPreview = document.getElementById('requirements-preview-list');
        this.createBookForm = document.getElementById('create-book-form');
        this.apiStatusIndicator = document.getElementById('api-status-indicator');
        this.apiStatusText = document.getElementById('api-status-text');
        
        // Library Reader Elements
        this.bookSelector = document.getElementById('reader-book-selector');
        this.readerBookTitle = document.getElementById('reader-book-title');
        this.readerBookStatus = document.getElementById('reader-book-status');
        this.trimestreTabsNav = document.getElementById('trimestre-tabs-nav');
        this.secuenciasSidebarList = document.getElementById('secuencias-sidebar-list');
        this.sequencesNavList = document.getElementById('sequences-nav-list');
        this.readerEmptyState = document.getElementById('reader-empty-state');
        this.readerContentPane = document.getElementById('reader-content-pane');
        
        // Active Sequence elements
        this.activeSeqNum = document.getElementById('active-seq-num');
        this.activeSeqStatus = document.getElementById('active-seq-status');
        this.activeSeqTitle = document.getElementById('active-seq-title');
        this.activeSeqObjectives = document.getElementById('active-seq-objectives');
        this.activeScoreAlignment = document.getElementById('active-score-alignment');
        this.activeScoreAge = document.getElementById('active-score-age');
        this.activeLessonsList = document.getElementById('active-lessons-list');
        this.activeSeqFeedbackPanel = document.getElementById('active-seq-feedback-panel');
        this.activeSeqFeedbackText = document.getElementById('active-seq-feedback-text');
        this.activeSeqRegenerateBtn = document.getElementById('active-seq-regenerate-btn');

        // Review Console Elements
        this.reviewEmptyState = document.getElementById('review-empty-state');
        this.reviewContentPane = document.getElementById('review-content-pane');
        this.reviewQueueList = document.getElementById('review-queue-list');
        this.consoleSeqTitle = document.getElementById('console-seq-title');
        this.consoleBookInfo = document.getElementById('console-book-info');
        this.consoleScoreAlignment = document.getElementById('console-score-alignment');
        this.consoleScoreAge = document.getElementById('console-score-age');
        this.consoleJustification = document.getElementById('console-justification');
        this.consoleLessonsPreview = document.getElementById('console-lessons-preview-container');
        this.reviewFeedbackInput = document.getElementById('review-feedback-input');
        
        // Buttons
        this.btnApproveSeq = document.getElementById('btn-approve-seq');
        this.btnRejectSeq = document.getElementById('btn-reject-seq');
        this.btnSeedDb = document.getElementById('seed-db-btn');
    }

    registerEvents() {
        // Navigation clicks
        this.navLinks.forEach(link => {
            link.addEventListener('click', (e) => {
                e.preventDefault();
                const target = link.getAttribute('data-target');
                this.switchView(target);
            });
        });

        // Form Submit
        this.createBookForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleCreateBook();
        });

        // Library Book Selector
        this.bookSelector.addEventListener('change', () => {
            const bookId = this.bookSelector.value;
            if (bookId) {
                this.loadBookDetails(bookId);
            } else {
                this.resetReaderPane();
            }
        });

        // Trimester Tabs clicks
        document.querySelectorAll('.t-tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.t-tab-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.renderSequencesList(parseInt(btn.getAttribute('data-t')));
            });
        });

        // Actions
        this.btnApproveSeq.addEventListener('click', () => this.handleReviewSubmit(true));
        this.btnRejectSeq.addEventListener('click', () => this.handleReviewSubmit(false));
        this.btnSeedDb.addEventListener('click', () => this.handleSeedDB());
        
        this.activeSeqRegenerateBtn.addEventListener('click', () => {
            if (this.activeSeq) {
                this.handleRegenerateSequence(this.activeSeq.id);
            }
        });
    }

    async init() {
        await this.checkAPIStatus();
        this.loadDashboardData();
        this.loadRequirementsPreview();
        
        // Start background polling for updating generating state
        this.startPolling();
    }

    // --- Core UI & Navigation Methods ---

    switchView(viewId) {
        this.activeView = viewId;
        this.views.forEach(view => {
            if (view.id === viewId) {
                view.classList.add('active');
            } else {
                view.classList.remove('active');
            }
        });

        this.navLinks.forEach(link => {
            if (link.getAttribute('data-target') === viewId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        // Set top header view titles
        const titles = {
            'dashboard-view': ['Dashboard del Sistema', 'Monitoreo de generación y gobernanza de libros de texto'],
            'creator-view': ['Diseño de Libros de Texto', 'Inicia un nuevo proyecto escolar guiado por agentes cognitivos'],
            'reader-view': ['Biblioteca de Libros Generados', 'Explora las lecciones didácticas con estructura Inicio-Desarrollo-Cierre'],
            'review-view': ['Consola de Human-in-the-Loop', 'Revisión y autorización de secuencias pedagógicas de primer grado']
        };

        if (titles[viewId]) {
            document.getElementById('view-title').innerText = titles[viewId][0];
            document.getElementById('view-subtitle').innerText = titles[viewId][1];
        }

        // Trigger context reloads on view entry
        if (viewId === 'dashboard-view') {
            this.loadDashboardData();
        } else if (viewId === 'reader-view') {
            this.populateLibrarySelector();
        } else if (viewId === 'review-view') {
            this.loadReviewQueue();
        }
    }

    showToast(message, type = 'info') {
        const toast = document.getElementById('toast');
        const icon = document.getElementById('toast-icon');
        const text = document.getElementById('toast-message');

        toast.className = 'toast'; // Reset
        toast.classList.add(`toast-${type}`);
        
        // Set icon
        const iconMap = {
            'info': 'fa-info-circle',
            'success': 'fa-circle-check',
            'warning': 'fa-triangle-exclamation',
            'error': 'fa-circle-xmark'
        };
        icon.className = `fa-solid ${iconMap[type] || 'fa-info-circle'}`;
        text.innerText = message;

        toast.classList.remove('hidden');
        setTimeout(() => {
            toast.classList.add('hidden');
        }, 4000);
    }

    // --- API Interactions ---

    async checkAPIStatus() {
        try {
            const res = await fetch(`${this.apiBase}/books`);
            if (res.ok) {
                this.apiStatusIndicator.className = 'status-indicator live';
                this.apiStatusText.innerText = 'Servicios Conectados';
            } else {
                throw new Error();
            }
        } catch {
            this.apiStatusIndicator.className = 'status-indicator error';
            this.apiStatusText.innerText = 'Servidor Desconectado';
            this.showToast('Error de conexión con el backend.', 'error');
        }
    }

    async loadDashboardData() {
        try {
            const res = await fetch(`${this.apiBase}/books`);
            if (!res.ok) return;
            this.books = await res.json();
            this.renderDashboardTable();
            this.updateDashboardMetrics();
        } catch (e) {
            console.error('Failed to load dashboard books', e);
        }
    }

    async loadRequirementsPreview() {
        try {
            const res = await fetch(`${this.apiBase}/books`); // Quick check
            if (!res.ok) return;
            
            // Render basic view of español requirements
            const mockReqs = [
                { code: "REQ-ESP-1.1", desc: "Reconoce y escribe su propio nombre para registrar asistencia." },
                { code: "REQ-ESP-1.2", desc: "Identifica la direccionalidad de la lectura (izquierda a derecha)." },
                { code: "REQ-ESP-1.3", desc: "Escribe palabras sencillas identificando sonido-letra." },
                { code: "REQ-ESP-1.4", desc: "Escucha cuentos y opina sobre personajes y trama." },
                { code: "REQ-ESP-1.5", desc: "Utiliza fórmulas de cortesía sencillas (por favor, gracias)." }
            ];
            
            this.requirementsPreview.innerHTML = mockReqs.map(r => `
                <div class="requirement-item">
                    <span class="req-code">${r.code}</span>
                    <p>${r.desc}</p>
                </div>
            `).join('');
        } catch (e) {
            console.error('Failed to load guidelines preview', e);
        }
    }

    updateDashboardMetrics() {
        document.getElementById('metric-total-books').innerText = this.books.length;
        
        const generating = this.books.filter(b => b.status === 'GENERATING').length;
        document.getElementById('metric-generating-books').innerText = generating;

        // Fetch review queue size
        fetch(`${this.apiBase}/reviews`)
            .then(res => res.json())
            .then(reviews => {
                this.pendingReviews = reviews;
                document.querySelectorAll('.review-count-badge').forEach(el => {
                    el.innerText = reviews.length;
                    if (reviews.length > 0) {
                        el.style.display = 'inline-block';
                    } else {
                        el.style.display = 'none';
                    }
                });
            });

        // Compute average alignment score across all approved/review sequences in books
        let totalScore = 0;
        let count = 0;
        this.books.forEach(b => {
            if (b.trimestres) {
                b.trimestres.forEach(t => {
                    t.secuencias.forEach(s => {
                        if (s.curricular_alignment_score) {
                            totalScore += s.curricular_alignment_score;
                            count++;
                        }
                    });
                });
            }
        });

        const avgText = count > 0 ? `${Math.round((totalScore / count) * 100)}%` : '---';
        document.getElementById('metric-avg-alignment').innerText = avgText;
    }

    renderDashboardTable() {
        if (this.books.length === 0) {
            this.booksTable.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-muted">No hay proyectos de libros creados. Haz clic en 'Nuevo Libro' para empezar.</td>
                </tr>
            `;
            return;
        }

        this.booksTable.innerHTML = this.books.map(book => {
            const date = new Date(book.created_at).toLocaleDateString('es-MX', {
                year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
            });
            return `
                <tr>
                    <td><strong>${book.title}</strong></td>
                    <td>${book.subject}</td>
                    <td>${book.grade}° Primaria</td>
                    <td><span class="status-badge ${book.status.toLowerCase()}">${book.status.replace('_', ' ')}</span></td>
                    <td>${date}</td>
                    <td>
                        <button class="btn btn-outline-warning btn-sm" onclick="app.viewBookInLibrary(${book.id})">
                            <i class="fa-solid fa-folder-open"></i> Abrir
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    viewBookInLibrary(bookId) {
        this.switchView('reader-view');
        // Let selector update first
        setTimeout(() => {
            this.bookSelector.value = bookId;
            this.loadBookDetails(bookId);
        }, 100);
    }

    async handleCreateBook() {
        const title = document.getElementById('book-title').value;
        const subject = document.getElementById('book-subject').value;
        const grade = parseInt(document.getElementById('book-grade').value);

        try {
            const res = await fetch(`${this.apiBase}/books`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ title, subject, grade })
            });

            if (res.ok) {
                const book = await res.json();
                this.showToast(`Proyecto '${book.title}' creado. Iniciando agentes didácticos...`, 'success');
                this.createBookForm.reset();
                this.viewBookInLibrary(book.id);
            } else {
                const err = await res.json();
                this.showToast(`Error: ${err.detail || 'No se pudo iniciar el proyecto'}`, 'error');
            }
        } catch (e) {
            this.showToast('Error al enviar la petición.', 'error');
        }
    }

    // --- Library / Reader Room ---

    async populateLibrarySelector() {
        const currentVal = this.bookSelector.value;
        try {
            const res = await fetch(`${this.apiBase}/books`);
            if (!res.ok) return;
            this.books = await res.json();
            
            this.bookSelector.innerHTML = '<option value="">-- Elige un proyecto --</option>' + 
                this.books.map(b => `<option value="${b.id}">${b.title} (${b.status.replace('_', ' ')})</option>`).join('');
            
            if (currentVal && this.books.some(b => b.id == currentVal)) {
                this.bookSelector.value = currentVal;
            }
        } catch (e) {
            console.error('Failed to populate selector', e);
        }
    }

    async loadBookDetails(bookId) {
        try {
            const res = await fetch(`${this.apiBase}/books/${bookId}`);
            if (!res.ok) return;
            this.activeBook = await res.json();

            this.readerBookTitle.innerText = this.activeBook.title;
            this.readerBookStatus.className = `status-badge ${this.activeBook.status.toLowerCase()}`;
            this.readerBookStatus.innerText = this.activeBook.status.replace('_', ' ');

            this.trimestreTabsNav.classList.remove('hidden');
            this.secuenciasSidebarList.classList.remove('hidden');

            // Default to Trimble 1 active tab
            const activeTab = document.querySelector('.t-tab-btn.active');
            const tNum = activeTab ? parseInt(activeTab.getAttribute('data-t')) : 1;
            this.renderSequencesList(tNum);
        } catch (e) {
            this.showToast('Error al cargar la información del libro.', 'error');
        }
    }

    renderSequencesList(trimesterNum) {
        if (!this.activeBook || !this.activeBook.trimestres) return;
        
        const trimestre = this.activeBook.trimestres.find(t => t.number === trimesterNum);
        if (!trimestre || !trimestre.secuencias || trimestre.secuencias.length === 0) {
            this.sequencesNavList.innerHTML = '<p class="text-muted text-center py-4">Generando estructura...</p>';
            return;
        }

        this.sequencesNavList.innerHTML = trimestre.secuencias.map(seq => {
            const isActive = this.activeSeq && this.activeSeq.id === seq.id ? 'active' : '';
            return `
                <div class="seq-item ${isActive}" onclick="app.showSequenceDetails(${seq.id})">
                    <h5>Secuencia ${seq.number}: ${seq.title}</h5>
                    <span class="status-badge ${seq.status.toLowerCase()}">${seq.status.replace('_', ' ')}</span>
                </div>
            `;
        }).join('');
    }

    showSequenceDetails(seqId) {
        if (!this.activeBook) return;
        
        // Find sequence inside the book
        let seq = null;
        for (const t of this.activeBook.trimestres) {
            const found = t.secuencias.find(s => s.id === seqId);
            if (found) {
                seq = found;
                break;
            }
        }

        if (!seq) return;
        this.activeSeq = seq;

        // Visual active state update in lists
        document.querySelectorAll('.seq-item').forEach(el => el.classList.remove('active'));
        // We render it
        this.readerEmptyState.classList.add('hidden');
        this.readerContentPane.classList.remove('hidden');

        this.activeSeqNum.innerText = `Secuencia ${seq.number}`;
        this.activeSeqStatus.className = `status-badge ${seq.status.toLowerCase()}`;
        this.activeSeqStatus.innerText = seq.status.replace('_', ' ');
        this.activeSeqTitle.innerText = seq.title;
        this.activeSeqObjectives.innerText = seq.objectives;

        const alignScore = seq.curricular_alignment_score !== null ? `${Math.round(seq.curricular_alignment_score * 100)}%` : '---';
        const ageScore = seq.age_appropriateness_score !== null ? `${Math.round(seq.age_appropriateness_score * 100)}%` : '---';
        this.activeScoreAlignment.innerText = alignScore;
        this.activeScoreAge.innerText = ageScore;

        // Render review feedback or justification if any
        if (seq.review_feedback) {
            this.activeSeqFeedbackPanel.classList.remove('hidden');
            this.activeSeqFeedbackText.innerText = seq.review_feedback;
        } else {
            this.activeSeqFeedbackPanel.classList.add('hidden');
        }

        // Render lessons
        if (seq.status === 'GENERATING') {
            this.activeLessonsList.innerHTML = `
                <div class="text-center py-5">
                    <i class="fa-solid fa-arrows-spin fa-spin fa-3x text-muted mb-3"></i>
                    <h3>Generando Contenido con Agentes de IA...</h3>
                    <p class="text-muted">Creando estructura de lecciones Inicio, Desarrollo y Cierre.</p>
                </div>
            `;
        } else if (!seq.lessons || seq.lessons.length === 0) {
            this.activeLessonsList.innerHTML = `
                <div class="text-center py-5 text-muted">
                    <p>No se ha generado contenido o está en espera de procesamiento.</p>
                </div>
            `;
        } else {
            this.activeLessonsList.innerHTML = seq.lessons.map(lesson => `
                <div class="lesson-card">
                    <h3>Lección ${lesson.number}: ${lesson.title}</h3>
                    <div class="pedagogical-sections">
                        <div class="p-section inicio">
                            <h4><i class="fa-solid fa-hourglass-start"></i> Inicio (Apertura)</h4>
                            <p>${lesson.section_inicio}</p>
                        </div>
                        <div class="p-section desarrollo">
                            <h4><i class="fa-solid fa-book-reader"></i> Desarrollo (Actividades)</h4>
                            <p>${lesson.section_desarrollo}</p>
                        </div>
                        <div class="p-section cierre">
                            <h4><i class="fa-solid fa-hourglass-end"></i> Cierre (Evaluación)</h4>
                            <p>${lesson.section_cierre}</p>
                        </div>
                    </div>
                    
                    <div class="lesson-activities">
                        <h4><i class="fa-solid fa-list-ol"></i> Instrucciones de Actividad</h4>
                        <p>${lesson.activities.replace(/\n/g, '<br>')}</p>
                    </div>
                </div>
            `).join('');
        }

        // Re-render sidebar active item highlights
        const activeTab = document.querySelector('.t-tab-btn.active');
        this.renderSequencesList(parseInt(activeTab.getAttribute('data-t')));
    }

    resetReaderPane() {
        this.activeBook = null;
        this.activeSeq = null;
        this.trimestreTabsNav.classList.add('hidden');
        this.secuenciasSidebarList.classList.add('hidden');
        this.readerEmptyState.classList.remove('hidden');
        this.readerContentPane.classList.add('hidden');
    }

    // --- Educator Review Console (HITL Queue) ---

    async loadReviewQueue() {
        try {
            const res = await fetch(`${this.apiBase}/reviews`);
            if (!res.ok) return;
            this.pendingReviews = await res.json();
            this.updateDashboardMetrics(); // Sync badge counts

            if (this.pendingReviews.length === 0) {
                this.reviewEmptyState.classList.remove('hidden');
                this.reviewContentPane.classList.add('hidden');
                this.activeReviewSeq = null;
                return;
            }

            this.reviewEmptyState.classList.add('hidden');
            this.reviewContentPane.classList.remove('hidden');

            this.reviewQueueList.innerHTML = this.pendingReviews.map(seq => `
                <div class="seq-item ${this.activeReviewSeq && this.activeReviewSeq.id === seq.id ? 'active' : ''}" onclick="app.selectReviewSequence(${seq.id})">
                    <h5>${seq.title}</h5>
                    <span>Alineación: ${Math.round(seq.curricular_alignment_score * 100)}%</span>
                </div>
            `).join('');

            // Auto-select first in queue if none active or no longer in queue
            if (!this.activeReviewSeq || !this.pendingReviews.some(s => s.id === this.activeReviewSeq.id)) {
                this.selectReviewSequence(this.pendingReviews[0].id);
            }
        } catch (e) {
            console.error('Failed to load review queue', e);
        }
    }

    selectReviewSequence(seqId) {
        const seq = this.pendingReviews.find(s => s.id === seqId);
        if (!seq) return;

        this.activeReviewSeq = seq;
        document.querySelectorAll('#review-queue-list .seq-item').forEach(el => el.classList.remove('active'));
        
        this.consoleSeqTitle.innerText = seq.title;
        // Search book name from books local cache
        let bookTitle = "Proyecto Generado";
        for (const b of this.books) {
            if (b.trimestres) {
                const found = b.trimestres.some(t => t.secuencias.some(s => s.id === seqId));
                if (found) {
                    bookTitle = b.title;
                    break;
                }
            }
        }
        this.consoleBookInfo.innerText = `Libro: ${bookTitle} | Secuencia N° ${seq.number}`;
        
        // Render scores
        const alignmentPercent = Math.round(seq.curricular_alignment_score * 100);
        const agePercent = Math.round(seq.age_appropriateness_score * 100);
        
        this.consoleScoreAlignment.innerText = (seq.curricular_alignment_score).toFixed(2);
        this.consoleScoreAge.innerText = (seq.age_appropriateness_score).toFixed(2);
        
        // Color rings based on values
        this.updateRingColor(document.getElementById('console-score-alignment-circle'), seq.curricular_alignment_score);
        this.updateRingColor(document.getElementById('console-score-age-circle'), seq.age_appropriateness_score);

        // Render AI Auditor Justification
        this.consoleJustification.innerText = seq.review_feedback || "No audit justification provided.";

        // Clear feedback input
        this.reviewFeedbackInput.value = '';

        // Render lessons preview
        this.consoleLessonsPreview.innerHTML = seq.lessons.map(lesson => `
            <div class="lesson-card">
                <h3>Lección ${lesson.number}: ${lesson.title}</h3>
                <div class="pedagogical-sections">
                    <div class="p-section inicio">
                        <h4>Inicio</h4>
                        <p>${lesson.section_inicio}</p>
                    </div>
                    <div class="p-section desarrollo">
                        <h4>Desarrollo</h4>
                        <p>${lesson.section_desarrollo}</p>
                    </div>
                    <div class="p-section cierre">
                        <h4>Cierre</h4>
                        <p>${lesson.section_cierre}</p>
                    </div>
                </div>
                
                <div class="lesson-activities">
                    <h4>Actividades de Clase</h4>
                    <p>${lesson.activities.replace(/\n/g, '<br>')}</p>
                </div>
            </div>
        `).join('');

        // Reload queue list highlights
        this.loadReviewQueueHighlight();
    }

    loadReviewQueueHighlight() {
        const items = document.querySelectorAll('#review-queue-list .seq-item');
        this.pendingReviews.forEach((seq, idx) => {
            if (this.activeReviewSeq && seq.id === this.activeReviewSeq.id) {
                if (items[idx]) items[idx].classList.add('active');
            }
        });
    }

    updateRingColor(element, val) {
        element.className = 'score-circle'; // reset
        if (val >= 0.85) {
            element.classList.add('green');
        } else if (val >= 0.7) {
            element.classList.add('orange');
        } else {
            element.classList.add('red');
        }
    }

    async handleReviewSubmit(approve) {
        if (!this.activeReviewSeq) return;
        
        const feedback = this.reviewFeedbackInput.value.trim();
        if (!approve && !feedback) {
            this.showToast('La retroalimentación pedagógica es obligatoria para rechazar una secuencia.', 'warning');
            return;
        }

        try {
            const res = await fetch(`${this.apiBase}/reviews/${this.activeReviewSeq.id}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ approve, feedback })
            });

            if (res.ok) {
                const updatedSeq = await res.json();
                const msg = approve 
                    ? `Secuencia '${updatedSeq.title}' aprobada satisfactoriamente.` 
                    : `Secuencia '${updatedSeq.title}' rechazada y enviada al pipeline con observaciones.`;
                
                this.showToast(msg, approve ? 'success' : 'info');
                this.activeReviewSeq = null;
                
                // Reload data
                await this.loadReviewQueue();
                this.loadDashboardData();
            } else {
                this.showToast('Error al enviar la revisión.', 'error');
            }
        } catch (e) {
            this.showToast('Error al conectar con la API.', 'error');
        }
    }

    async handleRegenerateSequence(secuenciaId) {
        try {
            this.showToast('Iniciando regeneración asistida por IA...', 'info');
            const res = await fetch(`${this.apiBase}/secuencias/${secuenciaId}/regenerate`, {
                method: 'POST'
            });

            if (res.ok) {
                this.showToast('Regeneración en proceso. Espere un momento...', 'success');
                // Force reload book details after a short lag
                setTimeout(() => {
                    if (this.activeBook) {
                        this.loadBookDetails(this.activeBook.id);
                    }
                }, 1000);
            } else {
                this.showToast('Error al iniciar la regeneración.', 'error');
            }
        } catch (e) {
            this.showToast('Error de conexión API.', 'error');
        }
    }

    async handleSeedDB() {
        try {
            const res = await fetch(`${this.apiBase}/admin/requirements/populate`, {
                method: 'POST'
            });
            if (res.ok) {
                const data = await res.json();
                this.showToast(`BD de Requisitos Sembrada: se agregaron ${data.inserted} lineamientos.`, 'success');
                this.loadDashboardData();
            } else {
                this.showToast('Error al sembrar la base de datos.', 'error');
            }
        } catch (e) {
            this.showToast('Error al conectar con el servidor.', 'error');
        }
    }

    // --- Background Polling for Pipeline Status ---

    startPolling() {
        // Poll database every 5 seconds to track active generator tasks
        this.pollInterval = setInterval(() => {
            const hasGenerating = this.books.some(b => b.status === 'GENERATING');
            const isReaderGenerating = this.activeBook && this.activeBook.status === 'GENERATING';
            
            // If active view is dashboard, we reload list
            if (this.activeView === 'dashboard-view') {
                this.loadDashboardData();
            }
            
            // If active view is reader and selected book is generating, reload details
            if (this.activeView === 'reader-view' && isReaderGenerating) {
                this.loadBookDetails(this.activeBook.id);
            }
            
            // If reviews view is open, reload reviews list
            if (this.activeView === 'review-view') {
                this.loadReviewQueue();
            }
        }, 5000);
    }
}

// Instantiate App
let app;
document.addEventListener('DOMContentLoaded', () => {
    app = new EduTextApp();
    // Expose globally
    window.app = app;
});
