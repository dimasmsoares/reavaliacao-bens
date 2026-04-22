'use strict';

(function () {
  const dropZone    = document.getElementById('drop-zone');
  const fileInput   = document.getElementById('file-input');
  const previewImg  = document.getElementById('screenshot-preview');
  const hiddenInput = document.getElementById('screenshot_data');
  const placeholder = document.getElementById('drop-placeholder');
  const btnClear    = document.getElementById('btn-clear-img');

  if (!dropZone) return; // Página sem formulário de avaliação

  // ── Mostra a imagem no preview e atualiza o campo hidden ──────────
  function setImage(dataUrl) {
    hiddenInput.value = dataUrl;
    previewImg.src = dataUrl;
    previewImg.classList.remove('d-none');
    if (placeholder) placeholder.classList.add('d-none');
    dropZone.classList.add('drop-zone-filled');
    dropZone.classList.remove('drop-zone-empty');
  }

  function readFileAsDataURL(file) {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => setImage(e.target.result);
    reader.readAsDataURL(file);
  }

  // ── Colar da área de transferência (Ctrl+V) ───────────────────────
  document.addEventListener('paste', function (e) {
    const items = e.clipboardData ? e.clipboardData.items : [];
    for (const item of items) {
      if (item.type.startsWith('image/')) {
        readFileAsDataURL(item.getAsFile());
        break;
      }
    }
  });

  // ── Drag & Drop ───────────────────────────────────────────────────
  dropZone.addEventListener('dragover', function (e) {
    e.preventDefault();
    this.classList.add('drag-over');
  });

  dropZone.addEventListener('dragleave', function () {
    this.classList.remove('drag-over');
  });

  dropZone.addEventListener('drop', function (e) {
    e.preventDefault();
    this.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    readFileAsDataURL(file);
  });

  // ── Clique para abrir seletor de arquivo ──────────────────────────
  dropZone.addEventListener('click', function (e) {
    if (e.target === btnClear || (btnClear && btnClear.contains(e.target))) return;
    fileInput.click();
  });

  fileInput.addEventListener('change', function () {
    readFileAsDataURL(this.files[0]);
    this.value = ''; // Reset para permitir selecionar o mesmo arquivo novamente
  });

  // ── Botão "Trocar imagem" ─────────────────────────────────────────
  if (btnClear) {
    btnClear.addEventListener('click', function (e) {
      e.stopPropagation();
      hiddenInput.value = '';
      previewImg.src = '';
      previewImg.classList.add('d-none');
      if (placeholder) placeholder.classList.remove('d-none');
      dropZone.classList.remove('drop-zone-filled');
    });
  }

  // ── Validação: avisa se não há imagem ao submeter ─────────────────
  const form = document.getElementById('form-avaliar');
  if (form) {
    form.addEventListener('submit', function (e) {
      const hasNewImage  = hiddenInput.value !== '';
      const hasOldImage  = previewImg.src && !previewImg.classList.contains('d-none') && !previewImg.src.endsWith('#');
      if (!hasNewImage && !hasOldImage) {
        if (!confirm('Nenhuma imagem de comprovante foi anexada.\nDeseja salvar assim mesmo?')) {
          e.preventDefault();
        }
      }
    });
  }

  // ── Formatação automática do campo de valor ───────────────────────
  const valorInput = document.getElementById('valor_mercado');
  if (valorInput) {
    valorInput.addEventListener('blur', function () {
      const raw = this.value.replace(/\./g, '').replace(',', '.');
      const num = parseFloat(raw);
      if (!isNaN(num)) {
        this.value = num.toLocaleString('pt-BR', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2
        });
      }
    });
  }
})();
