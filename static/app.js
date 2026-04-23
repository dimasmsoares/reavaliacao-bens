'use strict';

(function () {
  // ── State ────────────────────────────────────────────────────────────────
  let prices            = [];   // float[]
  let screenshots       = [];   // {id, type:'existing'|'new', path?:string, dataUrl?:string}
  let ssIdx             = 0;
  let currentMetodologia = 'M1';

  // ── Elementos ────────────────────────────────────────────────────────────
  const form        = document.getElementById('form-avaliar');
  if (!form) return;

  const priceInput    = document.getElementById('price-input');
  const btnAddPrice   = document.getElementById('btn-add-price');
  const pricesList    = document.getElementById('prices-list');
  const avgInput      = document.getElementById('avg-input');
  const avgDiffWarn   = document.getElementById('avg-diff-warn');
  const btnResetAvg   = document.getElementById('btn-reset-avg');
  const pricesJson    = document.getElementById('prices_json');
  const existingJson  = document.getElementById('existing_screenshots');
  const dropZone      = document.getElementById('drop-zone');
  const fileInput     = document.getElementById('file-input');
  const ssGrid        = document.getElementById('screenshots-grid');
  const sectionPrices      = document.getElementById('section-prices');
  const sectionIpca        = document.getElementById('section-ipca');
  const sectionSearch      = document.getElementById('section-search-links');
  const sectionScreenshots = document.getElementById('section-screenshots');
  const labelPrices        = document.getElementById('label-prices');
  const labelAvgCtx        = document.getElementById('label-avg-context');
  const ipcaInput          = document.getElementById('ipca-input');
  const ipcaStatus         = document.getElementById('ipca-status');
  const btnFetchIpca       = document.getElementById('btn-fetch-ipca');

  // ── Utilidades ───────────────────────────────────────────────────────────
  function parseBRL(s) {
    return parseFloat(s.replace(/\./g, '').replace(',', '.'));
  }

  function formatBRL(n) {
    return n.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  // ── Metodologia ──────────────────────────────────────────────────────────

  function switchMetodologia(m) {
    currentMetodologia = m;
    const isM3 = m === 'M3';
    const isM2 = m === 'M2';

    if (sectionPrices)      sectionPrices.classList.toggle('d-none', isM3);
    if (sectionIpca)        sectionIpca.classList.toggle('d-none', !isM3);
    if (sectionSearch)      sectionSearch.classList.toggle('d-none', isM3 || isM2);
    if (sectionScreenshots) sectionScreenshots.classList.toggle('d-none', isM3);

    if (labelPrices) labelPrices.textContent = isM2 ? 'Preços no acervo' : 'Preços encontrados';
    if (labelAvgCtx) labelAvgCtx.textContent = isM3
      ? '(corrigido pelo IPCA; somente leitura)'
      : '(média calculada; editável)';

    if (avgInput) {
      avgInput.readOnly = isM3;
      avgInput.classList.toggle('text-info',    isM3);
      avgInput.classList.toggle('text-success', !isM3);
    }
    if (btnResetAvg) btnResetAvg.classList.toggle('d-none', isM3);
    if (avgDiffWarn && isM3) avgDiffWarn.classList.add('d-none');

    if (isM3) updateIPCAValor();
  }

  function updateIPCAValor() {
    if (!ipcaInput || !avgInput || !sectionIpca) return;
    const ipca  = parseBRL(ipcaInput.value.trim());
    const vcStr = sectionIpca.dataset.vc;
    const vc    = vcStr ? parseFloat(vcStr) : null;
    if (isNaN(ipca) || !vc) { avgInput.value = ''; return; }
    avgInput.value = formatBRL(vc * (1 + ipca / 100));
  }

  async function fetchIPCA() {
    if (!sectionIpca || !ipcaStatus) return;
    const tomb = sectionIpca.dataset.tombamento || '';
    if (!tomb) return;
    ipcaStatus.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status"></span>Buscando…';
    ipcaStatus.className = 'form-text text-muted';
    try {
      const resp = await fetch('/api/ipca?data_inicio=' + encodeURIComponent(tomb));
      const data = await resp.json();
      if (data.error) throw new Error(data.error);
      if (ipcaInput) ipcaInput.value = formatBRL(data.acumulado);
      updateIPCAValor();
      ipcaStatus.textContent = `IPCA acumulado de ${tomb} até hoje: ${formatBRL(data.acumulado)}%`;
      ipcaStatus.className = 'form-text text-success';
    } catch (err) {
      ipcaStatus.textContent = 'Erro ao buscar IPCA: ' + err.message;
      ipcaStatus.className = 'form-text text-danger';
    }
  }

  // Listeners de metodologia
  document.querySelectorAll('input[name="metodologia"]').forEach(function (radio) {
    radio.addEventListener('change', function () { switchMetodologia(this.value); });
  });

  if (ipcaInput) {
    ipcaInput.addEventListener('input', updateIPCAValor);
    ipcaInput.addEventListener('blur', function () {
      const n = parseBRL(this.value.trim());
      if (!isNaN(n) && this.value.trim()) this.value = formatBRL(n);
      updateIPCAValor();
    });
  }
  if (btnFetchIpca) btnFetchIpca.addEventListener('click', fetchIPCA);

  // ── Valor de mercado (editável) ──────────────────────────────────────────
  let calcAvg = null;  // média calculada pelos preços

  function calcAvgFromPrices() {
    return prices.length ? prices.reduce((a, b) => a + b, 0) / prices.length : null;
  }

  function updateAvgInput(forceCalc) {
    calcAvg = calcAvgFromPrices();
    if (forceCalc || avgInput.dataset.manual !== '1') {
      avgInput.value = calcAvg !== null ? formatBRL(calcAvg) : '';
      avgInput.dataset.manual = '0';
    }
    checkAvgDiff();
  }

  function checkAvgDiff() {
    if (!avgDiffWarn) return;
    if (calcAvg === null || avgInput.dataset.manual !== '1') {
      avgDiffWarn.classList.add('d-none');
      return;
    }
    const cur = parseBRL(avgInput.value);
    const differs = !isNaN(cur) && Math.abs(cur - calcAvg) > 0.01;
    avgDiffWarn.classList.toggle('d-none', !differs);
  }

  if (avgInput) {
    avgInput.addEventListener('input', function () {
      this.dataset.manual = '1';
      checkAvgDiff();
    });
    avgInput.addEventListener('blur', function () {
      const n = parseBRL(this.value.trim());
      if (!isNaN(n) && n > 0) this.value = formatBRL(n);
    });
  }

  if (btnResetAvg) {
    btnResetAvg.addEventListener('click', function () {
      if (avgInput) {
        avgInput.dataset.manual = '0';
        updateAvgInput(true);
      }
    });
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

    updateAvgInput(false);
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
    if (currentMetodologia !== 'M3') {
      if (prices.length === 0) {
        e.preventDefault();
        if (priceInput) { priceInput.classList.add('is-invalid'); priceInput.focus(); }
        return;
      }
    } else {
      const ipcaVal = ipcaInput ? parseBRL(ipcaInput.value.trim()) : NaN;
      if (isNaN(ipcaVal) || ipcaVal < 0) {
        e.preventDefault();
        if (ipcaInput) { ipcaInput.classList.add('is-invalid'); ipcaInput.focus(); }
        return;
      }
      if (ipcaInput) ipcaInput.classList.remove('is-invalid');
    }
    const valStr = avgInput ? avgInput.value.trim() : '';
    const valNum = parseBRL(valStr);
    if (!valStr || isNaN(valNum) || valNum <= 0) {
      e.preventDefault();
      if (avgInput) { avgInput.classList.add('is-invalid'); avgInput.focus(); }
      return;
    }
    if (avgInput) avgInput.classList.remove('is-invalid');
    if (currentMetodologia !== 'M3' && screenshots.length === 0) {
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
  window.initAvaliar = function (existingPrices, existingPaths, existingValorMercado,
                                  existingMetodologia, existingIpcaPercentual) {
    prices = (existingPrices || []).map(Number).filter(n => !isNaN(n));
    renderPrices();  // calcula média e preenche avg-input

    // Se o valor salvo difere da média calculada, é uma edição manual anterior (M1/M2)
    if (existingValorMercado !== null && existingValorMercado !== undefined && avgInput) {
      const calculado = calcAvgFromPrices();
      if (calculado === null || Math.abs(existingValorMercado - calculado) > 0.01) {
        avgInput.value = formatBRL(existingValorMercado);
        avgInput.dataset.manual = '1';
        checkAvgDiff();
      }
    }

    (existingPaths || []).forEach(path => {
      screenshots.push({ id: ++ssIdx, type: 'existing', path });
    });
    renderScreenshots();

    // Restaurar metodologia
    const met = existingMetodologia || 'M1';
    const radio = document.querySelector(`input[name="metodologia"][value="${met}"]`);
    if (radio) radio.checked = true;
    switchMetodologia(met);

    // Restaurar IPCA
    if (met === 'M3' && existingIpcaPercentual !== null && existingIpcaPercentual !== undefined) {
      if (ipcaInput) {
        ipcaInput.value = formatBRL(existingIpcaPercentual);
        updateIPCAValor();
      }
    }
  };
})();
