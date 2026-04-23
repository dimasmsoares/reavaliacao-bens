'use strict';

(function () {
  // ── State ────────────────────────────────────────────────────────────────
  let prices      = [];   // float[]
  let screenshots = [];   // {id, type:'existing'|'new', path?:string, dataUrl?:string}
  let ssIdx       = 0;

  // ── Elementos ────────────────────────────────────────────────────────────
  const form        = document.getElementById('form-avaliar');
  if (!form) return;

  const priceInput  = document.getElementById('price-input');
  const btnAddPrice = document.getElementById('btn-add-price');
  const pricesList  = document.getElementById('prices-list');
  const avgDisplay  = document.getElementById('avg-display');
  const pricesJson  = document.getElementById('prices_json');
  const existingJson= document.getElementById('existing_screenshots');
  const dropZone    = document.getElementById('drop-zone');
  const fileInput   = document.getElementById('file-input');
  const ssGrid      = document.getElementById('screenshots-grid');

  // ── Utilidades ───────────────────────────────────────────────────────────
  function parseBRL(s) {
    return parseFloat(s.replace(/\./g, '').replace(',', '.'));
  }

  function formatBRL(n) {
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // ── Preços ───────────────────────────────────────────────────────────────
  function renderPrices() {
    pricesJson.value = JSON.stringify(prices);

    pricesList.innerHTML = prices.map((p, i) =>
      `<span class="badge bg-primary d-inline-flex align-items-center gap-1 px-2 py-1 fs-6">
        R$ ${formatBRL(p)}
        <button type="button" class="btn-close btn-close-white ms-1"
                style="font-size:.6em" data-rm-price="${i}" aria-label="Remover"></button>
      </span>`
    ).join('');

    const avg = prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;
    avgDisplay.textContent = avg !== null ? 'R$ ' + formatBRL(avg) : '—';
  }

  pricesList.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-rm-price]');
    if (!btn) return;
    prices.splice(parseInt(btn.dataset.rmPrice), 1);
    renderPrices();
  });

  function addPrice() {
    const raw = priceInput.value.trim();
    if (!raw) return;
    const n = parseBRL(raw);
    if (isNaN(n) || n < 0) { priceInput.classList.add('is-invalid'); return; }
    priceInput.classList.remove('is-invalid');
    prices.push(n);
    renderPrices();
    priceInput.value = '';
    priceInput.focus();
  }

  btnAddPrice.addEventListener('click', addPrice);
  priceInput.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); addPrice(); } });
  priceInput.addEventListener('blur', function () {
    const n = parseBRL(this.value.trim());
    if (!isNaN(n) && this.value.trim()) this.value = formatBRL(n);
  });

  // ── Screenshots ──────────────────────────────────────────────────────────
  function renderScreenshots() {
    ssGrid.innerHTML = screenshots.map(s => {
      const src = s.type === 'existing' ? `/screenshots/${s.path}` : s.dataUrl;
      return `<div class="position-relative" data-ss="${s.id}">
        <img src="${src}" class="rounded border"
             style="width:130px;height:95px;object-fit:cover;cursor:zoom-in"
             onclick="window.open('${src}','_blank')" title="Clique para ampliar">
        <button type="button" class="btn btn-danger position-absolute top-0 end-0
                d-flex align-items-center justify-content-center p-0 lh-1"
                style="width:22px;height:22px;font-size:.75rem;border-radius:0 4px 0 4px"
                data-rm-ss="${s.id}" aria-label="Remover print">
          <i class="bi bi-x"></i>
        </button>
      </div>`;
    }).join('');

    existingJson.value = JSON.stringify(
      screenshots.filter(s => s.type === 'existing').map(s => s.path)
    );

    form.querySelectorAll('[name^="screenshot_data_"]').forEach(el => el.remove());
    screenshots.filter(s => s.type === 'new').forEach((s, i) => {
      const inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = `screenshot_data_${i}`;
      inp.value = s.dataUrl;
      form.appendChild(inp);
    });
  }

  ssGrid.addEventListener('click', function (e) {
    const btn = e.target.closest('[data-rm-ss]');
    if (!btn) return;
    screenshots = screenshots.filter(s => s.id !== parseInt(btn.dataset.rmSs));
    renderScreenshots();
  });

  function compressAndAdd(file) {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = function (e) {
      const img = new Image();
      img.onload = function () {
        const MAX_W = 1280;
        let w = img.width, h = img.height;
        if (w > MAX_W) { h = Math.round(h * MAX_W / w); w = MAX_W; }
        const canvas = document.createElement('canvas');
        canvas.width = w; canvas.height = h;
        canvas.getContext('2d').drawImage(img, 0, 0, w, h);
        screenshots.push({ id: ++ssIdx, type: 'new', dataUrl: canvas.toDataURL('image/jpeg', 0.85) });
        renderScreenshots();
      };
      img.src = e.target.result;
    };
    reader.readAsDataURL(file);
  }

  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', function (e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    compressAndAdd(e.dataTransfer.files[0]);
  });
  dropZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', function () { compressAndAdd(this.files[0]); this.value = ''; });

  document.addEventListener('paste', function (e) {
    for (const item of (e.clipboardData ? e.clipboardData.items : [])) {
      if (item.type.startsWith('image/')) { compressAndAdd(item.getAsFile()); break; }
    }
  });

  // ── Validação no submit ──────────────────────────────────────────────────
  form.addEventListener('submit', function (e) {
    if (prices.length === 0) {
      e.preventDefault();
      priceInput.classList.add('is-invalid');
      priceInput.focus();
      return;
    }
    if (screenshots.length === 0) {
      if (!confirm('Nenhum print de comprovante foi anexado.\nDeseja salvar assim mesmo?')) {
        e.preventDefault();
      }
    }
  });

  // ── Filtro da sidebar ────────────────────────────────────────────────────
  const sidebarSearch      = document.getElementById('sidebar-search');
  const sidebarOnlyPending = document.getElementById('sidebar-only-pending');

  function filterSidebar() {
    const q       = sidebarSearch ? sidebarSearch.value.trim().toLowerCase() : '';
    const pending = sidebarOnlyPending ? sidebarOnlyPending.checked : false;
    document.querySelectorAll('.sidebar-item').forEach(function (el) {
      const text     = el.textContent.toLowerCase();
      const isDone   = el.classList.contains('sidebar-done');
      const matchQ   = !q || text.includes(q);
      const matchP   = !pending || !isDone;
      el.style.display = (matchQ && matchP) ? '' : 'none';
    });
  }

  if (sidebarSearch)      sidebarSearch.addEventListener('input', filterSidebar);
  if (sidebarOnlyPending) sidebarOnlyPending.addEventListener('change', filterSidebar);

  // ── Inicialização com dados do servidor ─────────────────────────────────
  window.initAvaliar = function (existingPrices, existingPaths) {
    prices = (existingPrices || []).map(Number).filter(n => !isNaN(n));
    renderPrices();
    (existingPaths || []).forEach(path => {
      screenshots.push({ id: ++ssIdx, type: 'existing', path });
    });
    renderScreenshots();
  };
})();
