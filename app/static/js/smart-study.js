(function () {
    'use strict';

    function initSidebar() {
        const sidebar = document.getElementById('appSidebar');
        const overlay = document.getElementById('sidebarOverlay');
        const toggle = document.getElementById('sidebarToggle');
        if (!sidebar || !toggle) return;

        function openSidebar() {
            sidebar.classList.add('open');
            overlay?.classList.add('show');
            document.body.style.overflow = 'hidden';
        }

        function closeSidebar() {
            sidebar.classList.remove('open');
            overlay?.classList.remove('show');
            document.body.style.overflow = '';
        }

        toggle.addEventListener('click', () => {
            sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
        });
        overlay?.addEventListener('click', closeSidebar);
    }

    function initHoursSlider() {
        const slider = document.getElementById('totalHoursSlider');
        const display = document.getElementById('totalHoursDisplay');
        const hidden = document.getElementById('totalHoursInput');
        if (!slider || !display) return;

        function sync() {
            const val = slider.value;
            display.textContent = val;
            if (hidden) hidden.value = val;
        }
        slider.addEventListener('input', sync);
        sync();
    }

    function initSubjectRows() {
        const container = document.getElementById('subjects-container');
        const addBtn = document.getElementById('add-subject-btn');
        if (!container || !addBtn) return;

        const template = document.getElementById('subject-row-template');
        if (!template) return;

        addBtn.addEventListener('click', () => {
            const clone = template.content.cloneNode(true);
            container.appendChild(clone);
            const rows = container.querySelectorAll('.subject-row');
            const lastRow = rows[rows.length - 1];
            const removeBtn = lastRow.querySelector('.remove-btn');
            if (removeBtn) {
                removeBtn.addEventListener('click', () => lastRow.remove());
            }
        });

        container.querySelectorAll('.remove-btn').forEach((btn) => {
            btn.addEventListener('click', function () {
                this.closest('.subject-row')?.remove();
            });
        });
    }

    function initPlannerForm() {
        const form = document.getElementById('planner-form');
        const loading = document.getElementById('plannerLoading');
        if (!form) return;

        form.addEventListener('submit', () => {
            if (loading) loading.classList.add('show');
            const btn = form.querySelector('[type="submit"]');
            if (btn) {
                btn.disabled = true;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Generating...';
            }
        });
    }

    function initAutoDismissAlerts() {
        document.querySelectorAll('.alert-dismissible').forEach((alert) => {
            setTimeout(() => {
                if (alert.parentNode) {
                    alert.classList.remove('show');
                    setTimeout(() => alert.remove(), 300);
                }
            }, 6000);
        });
    }

    function initUploadDropzone() {
        const zone = document.getElementById('uploadDropzone');
        const input = document.getElementById('documentFileInput');
        const label = document.getElementById('uploadFileName');
        if (!zone || !input) return;

        zone.addEventListener('click', () => input.click());
        zone.addEventListener('dragover', (e) => {
            e.preventDefault();
            zone.classList.add('dragover');
        });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                if (label) label.textContent = e.dataTransfer.files[0].name;
            }
        });
        input.addEventListener('change', () => {
            if (label && input.files[0]) label.textContent = input.files[0].name;
        });

        const form = zone.closest('form');
        if (form) {
            form.addEventListener('submit', () => {
                const btn = document.getElementById('uploadBtn');
                const loading = document.getElementById('uploadLoading');
                if (btn) btn.classList.add('d-none');
                if (loading) loading.classList.remove('d-none');
            });
        }
    }

    function initSubjectSelectAll() {
        const selectAll = document.getElementById('selectAllSubjects');
        const boxes = document.querySelectorAll('input[name="subjects"]');
        if (!selectAll || !boxes.length) return;
        selectAll.addEventListener('change', () => {
            boxes.forEach((cb) => { cb.checked = selectAll.checked; });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        initSidebar();
        initHoursSlider();
        initSubjectRows();
        initPlannerForm();
        initAutoDismissAlerts();
        initUploadDropzone();
        initSubjectSelectAll();
    });
})();
