(() => {
  'use strict';

  const WA_NUMBER = '5585992333378';
  const PLACEHOLDER = 'assets/helmet-placeholder.svg';
  const img = (path) => `https://aeropartz.com.br/storage/product-media/${path}`;

  const PRODUCTS = [
    {
      id: 'atomic-elite', filterName: 'Atomic Elite', name: 'Pro Tork New Atomic Elite', price: 159.99,
      url: 'https://aeropartz.com.br/loja/produtos/14/new-atomic-elite', kind: 'open',
      glb: 'assets/3d/atomic-elite.glb', note: '',
      gallery: [
        img('catalog-audit-20261016/atomic-elite-azul-lado-lateral-01.jpg'),
        img('carousel-review-20261016/atomic-elite-azul-03.jpg'),
        img('carousel-review-20261016/atomic-elite-azul-02.jpg'),
        img('carousel-review-20261016/atomic-elite-azul-04.jpg'),
        img('carousel-review-20261016/atomic-elite-azul-05.jpg'),
        img('carousel-review-20261016/atomic-elite-azul-06.jpg')
      ],
      variants: [
        { name: 'Azul Celeste', hex: '#169fe3', sizes: [56, 58, 60], image: img('catalog-audit-20261016/atomic-elite-azul-lado-lateral-01.jpg'), gallery: null },
        { name: 'Verde Militar', hex: '#657a50', sizes: [58, 60], image: img('catalog-audit-20261016/atomic-elite-verde-01.jpg'), gallery: null },
        { name: 'Laranja Fosco', hex: '#ed7c20', sizes: [58, 60], image: img('catalog-audit-20261016/atomic-elite-laranja-01.jpg'), gallery: null },
        { name: 'Vinho', hex: '#702b3b', sizes: [58], image: img('catalog-audit-20261016/atomic-elite-vinho-01.jpg'), gallery: null }
      ]
    },
    {
      id: 'atomic-solid', filterName: 'Atomic Solid', name: 'Pro Tork New Atomic Solid', price: 159.99,
      url: 'https://aeropartz.com.br/loja/produtos/7/new-atomic-solid', kind: 'closed', galleryColor: 'Branco',
      glb: 'assets/3d/atomic-solid.glb', note: '',
      gallery: [
        img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-01.jpg'),
        img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-03.jpg'),
        img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-02.jpg'),
        img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-04.jpg'),
        img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-05.jpg'),
        img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-06.jpg')
      ],
      variants: [
        { name: 'Preto Fosco', hex: '#17191d', sizes: [58, 60], image: img('helmet-catalog-20261011/atomic-solid-current--preto-fosco-01.jpg'), gallery: null },
        { name: 'Branco', hex: '#f2f3f4', sizes: [58], image: img('helmet-catalog-20261011/atomic-solid-current--branco-fosco-01.jpg'), gallery: null }
      ]
    },
    {
      id: 'r8', filterName: 'R8', name: 'Pro Tork R8', price: 159.99,
      url: 'https://aeropartz.com.br/loja/produtos/6/r8', kind: 'closed',
      glb: 'assets/3d/r8.glb', note: 'Sem viseira interna',
      gallery: [
        img('catalog-audit-20261016/r8-preto-vermelho-01.webp'),
        img('carousel-review-20261016/r8-preto-vermelho-03.jpg'),
        img('carousel-review-20261016/r8-preto-vermelho-02.jpg'),
        img('carousel-review-20261016/r8-preto-vermelho-04.jpg'),
        img('carousel-review-20261016/r8-preto-vermelho-05.jpg'),
        img('carousel-review-20261016/r8-preto-vermelho-06.jpg')
      ],
      variants: [
        { name: 'Preto/Vermelho', hex: '#c52d38', sizes: [58, 60], image: img('catalog-audit-20261016/r8-preto-vermelho-01.webp'), gallery: null },
        { name: 'Preto/Prata', hex: '#a5a9ae', sizes: [60], image: img('helmet-catalog-20261011/r8-current--prata-01.webp'), gallery: null },
        { name: 'Rosa', hex: '#e89bb0', sizes: [56, 58], image: img('helmet-catalog-20261011/r8-current--rosa-01.webp'), gallery: null }
      ]
    },
    {
      id: 'liberty-3-elite', filterName: 'Liberty 3 Elite', name: 'Pro Tork New Liberty 3 Elite', price: 99.99,
      url: 'https://aeropartz.com.br/loja/produtos/4/new-liberty-3-elite', kind: 'open',
      glb: 'assets/3d/liberty-3-elite.glb', note: '',
      gallery: [
        img('helmet-catalog-20261011/elite-current--branco-01.jpg'),
        img('helmet-catalog-20261011/elite-current--branco-02.jpg'),
        img('helmet-catalog-20261011/elite-current--branco-03.jpg'),
        img('helmet-catalog-20261011/elite-current--branco-04.jpg'),
        img('helmet-catalog-20261011/elite-current--branco-05.jpg'),
        img('helmet-catalog-20261011/elite-current--branco-06.jpg')
      ],
      variants: [
        { name: 'Azul Bic', hex: '#145dd1', sizes: [56], image: img('elite-photo-review-20261016/elite-azul-bic-sportbay-original.jpg'), gallery: null },
        { name: 'Azul Marinho', hex: '#142d62', sizes: [56], image: img('helmet-catalog-20261011/elite-current--azul-escuro-01.jpg'), gallery: null },
        { name: 'Branco', hex: '#f4f4f1', sizes: [56], image: img('helmet-catalog-20261011/elite-current--branco-01.jpg'), gallery: null },
        { name: 'Preto', hex: '#191a1d', sizes: [56], image: img('owner-20261030/elite-preto-39eda759e498.webp'), gallery: null },
        { name: 'Verde Militar', hex: '#697d50', sizes: [56], image: img('helmet-catalog-20261011/elite-current--verde-militar-01.jpg'), gallery: null },
        { name: 'Vermelho Pimenta', hex: '#d52d3d', sizes: [56], image: img('helmet-catalog-20261011/elite-current--vermelho-pimenta-01.jpg'), gallery: null },
        { name: 'Vinho', hex: '#702d3b', sizes: [56], image: img('helmet-catalog-20261011/elite-current--vermelho-01.jpg'), gallery: null },
        { name: 'Rosa Fosco', hex: '#eaa9b8', sizes: [60], image: img('helmet-catalog-20261011/elite-current--rosa-bebe-01.jpg'), gallery: null }
      ]
    },
    {
      id: 'liberty-4', filterName: 'Liberty 4', name: 'Pro Tork New Liberty 4', price: 129.99,
      url: 'https://aeropartz.com.br/loja/produtos/10/new-liberty-4', kind: 'open',
      glb: 'assets/3d/liberty-4.glb', note: '',
      gallery: [
        img('helmet-catalog-20261011/liberty4--preto-fosco-01.jpg'),
        img('helmet-catalog-20261011/liberty4--preto-fosco-03.jpg'),
        img('helmet-catalog-20261011/liberty4--preto-fosco-02.jpg'),
        img('helmet-catalog-20261011/liberty4--preto-fosco-04.jpg'),
        img('helmet-catalog-20261011/liberty4--preto-fosco-05.jpg'),
        img('helmet-catalog-20261011/liberty4--preto-fosco-06.jpg')
      ],
      variants: [
        { name: 'Preto Fosco', hex: '#1b1c1f', sizes: [56, 58, 60], image: img('helmet-catalog-20261011/liberty4--preto-fosco-01.jpg'), gallery: null }
      ]
    },
    {
      id: '788', filterName: '788', name: 'Pro Tork Sport Moto 788', price: 99.99,
      url: 'https://aeropartz.com.br/loja/produtos/5/sport-moto-788', kind: 'closed',
      glb: 'assets/3d/sport-moto-788.glb', note: '',
      gallery: [
        img('helmet-catalog-20261011/sport788-classic--preto-azul-01.jpeg'),
        img('helmet-catalog-20261011/sport788-classic--preto-azul-03.jpeg'),
        img('helmet-catalog-20261011/sport788-classic--preto-azul-04.jpeg'),
        img('helmet-catalog-20261011/sport788-classic--preto-azul-02.jpeg'),
        img('helmet-catalog-20261011/sport788-classic--preto-azul-05.jpeg'),
        img('helmet-catalog-20261011/sport788-classic--preto-azul-06.jpeg')
      ],
      variants: [
        { name: 'Azul', hex: '#174ed4', sizes: [56], image: img('helmet-catalog-20261011/sport788-classic--preto-azul-01.jpeg'), gallery: null },
        { name: 'Vermelho/Preto', hex: '#c72d35', sizes: [62], image: img('helmet-catalog-20261011/sport788--preto-vermelho-01.jpg'), gallery: null },
        { name: 'Preto/Prata', hex: '#a8adb3', sizes: [60], image: img('helmet-catalog-20261011/sport788-classic--preto-branco-01.jpeg'), gallery: null },
        { name: 'Cinza', hex: '#777e87', sizes: [60], image: img('JgiXZBHNnjtOyXYHj7097uK7QFMi1EoOpJkjETLp.jpg'), gallery: null }
      ]
    }
  ];

  const state = {
    sizeFilter: null,
    modelFilter: 'all',
    selectedVariant: Object.fromEntries(PRODUCTS.map(p => [p.id, 0])),
    selectedSize: Object.fromEntries(PRODUCTS.map(p => [p.id, null]))
  };

  const productGrid = document.getElementById('productGrid');
  const resultCount = document.getElementById('resultCount');
  const emptyState = document.getElementById('emptyState');
  const sizeFilters = document.getElementById('sizeFilters');
  const modelFilters = document.getElementById('modelFilters');
  const viewerModal = document.getElementById('viewerModal');
  const viewerHost = document.getElementById('viewerCanvasHost');
  let threeState = null;
  let resizeHandler = null;
  let activeProduct = null;
  let viewerPhotos = [];
  let viewerPhotoIndex = 0;

  const money = value => new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(value);
  const getVariant = product => product.variants[state.selectedVariant[product.id] || 0];
  const escapeHtml = value => String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char]));

  function visibleProducts() {
    return PRODUCTS.filter(product => {
      if (state.modelFilter !== 'all' && product.id !== state.modelFilter) return false;
      if (state.sizeFilter && !product.variants.some(variant => variant.sizes.includes(state.sizeFilter))) return false;
      return true;
    });
  }

  function renderFilters() {
    document.querySelectorAll('[data-size]').forEach(button => {
      const active = Number(button.dataset.size) === state.sizeFilter;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
    document.getElementById('clearSize').hidden = !state.sizeFilter;
    document.querySelectorAll('[data-model]').forEach(button => {
      const active = button.dataset.model === state.modelFilter;
      button.classList.toggle('is-active', active);
      button.setAttribute('aria-pressed', String(active));
    });
  }

  function renderSwatches(product, selectedIndex) {
    return product.variants.map((variant, index) => {
      const active = index === selectedIndex;
      return `<button class="swatch ${active ? 'is-active' : ''}" type="button" data-action="variant" data-product="${product.id}" data-variant="${index}" data-color="${escapeHtml(variant.name)}" title="${escapeHtml(variant.name)}" aria-label="Selecionar cor ${escapeHtml(variant.name)}" aria-pressed="${active}" style="background:${variant.hex}"></button>`;
    }).join('');
  }

  function renderCard(product) {
    const variantIndex = state.selectedVariant[product.id] || 0;
    const variant = product.variants[variantIndex];
    const sizes = variant.sizes.map(size => `<span class="stock-size">${size}</span>`).join('');
    const note = product.note ? `<p class="product-note">${escapeHtml(product.note)}</p>` : '';
    const photo = variant.image || product.gallery?.[0] || PLACEHOLDER;
    return `
      <article class="product-card" data-card="${product.id}">
        <button class="product-photo-button" type="button" data-action="open-3d" data-product="${product.id}" aria-label="Abrir ${escapeHtml(product.name)} no visualizador 3D">
          <img src="${photo}" alt="${escapeHtml(product.name)} — ${escapeHtml(variant.name)}" loading="lazy" onerror="this.onerror=null;this.src='${PLACEHOLDER}'">
          <span class="photo-hint"><span aria-hidden="true">↻</span> Explorar em 3D</span>
        </button>
        <div class="product-body">
          <div class="product-brand">Pro Tork</div>
          <div class="product-title-row">
            <button class="product-title-button" type="button" data-action="open-3d" data-product="${product.id}">${escapeHtml(product.name)}</button>
            <strong class="product-price">${money(product.price)}</strong>
          </div>
          ${note}
          <div class="product-color-line">
            <span class="product-color-name">${escapeHtml(variant.name)}</span>
            <div class="swatches" aria-label="Cores disponíveis">${renderSwatches(product, variantIndex)}</div>
          </div>
          <div class="stock-row">
            <span class="stock-label">Tamanhos em estoque</span>
            <div class="stock-sizes">${sizes}</div>
          </div>
          <button class="product-3d-cta" type="button" data-action="open-3d" data-product="${product.id}">Abrir visualizador 3D <span aria-hidden="true">↗</span></button>
        </div>
      </article>`;
  }

  function renderProducts() {
    const products = visibleProducts();
    resultCount.textContent = `${products.length} ${products.length === 1 ? 'modelo' : 'modelos'}`;
    emptyState.hidden = products.length > 0;
    productGrid.hidden = products.length === 0;
    productGrid.innerHTML = products.map(renderCard).join('');
    renderFilters();
  }

  function selectVariant(productId, index) {
    const product = PRODUCTS.find(item => item.id === productId);
    if (!product || !product.variants[index]) return;
    state.selectedVariant[productId] = index;
    const variant = product.variants[index];
    if (!variant.sizes.includes(state.selectedSize[productId])) state.selectedSize[productId] = null;
    renderProducts();
    if (activeProduct && activeProduct.id === productId) {
      updateViewerOptions(product);
      renderViewerPhotos(product);
      if (threeState) recolorHelmet(threeState.model, variant.hex);
    }
  }

  function selectSize(productId, size) {
    const product = PRODUCTS.find(item => item.id === productId);
    if (!product) return;
    const variant = getVariant(product);
    if (!variant.sizes.includes(size)) return;
    state.selectedSize[productId] = state.selectedSize[productId] === size ? null : size;
    updateViewerOptions(product);
  }

  function makeWhatsAppUrl(product) {
    const variant = getVariant(product);
    const size = state.selectedSize[product.id];
    const message = `Olá! Tenho interesse no ${product.name}, cor ${variant.name}, tamanho ${size || 'a confirmar'}. Poderia confirmar a disponibilidade?`;
    return `https://wa.me/${WA_NUMBER}?text=${encodeURIComponent(message)}`;
  }

  function updateViewerOptions(product) {
    const variantIndex = state.selectedVariant[product.id] || 0;
    const variant = getVariant(product);
    const colorContainer = document.getElementById('viewerColorOptions');
    const sizeContainer = document.getElementById('viewerSizeOptions');
    colorContainer.innerHTML = product.variants.map((item, index) => `
      <button class="viewer-color ${index === variantIndex ? 'is-active' : ''}" type="button" data-viewer-variant="${index}" aria-pressed="${index === variantIndex}">
        <span class="viewer-color-dot" style="background:${item.hex}"></span><span>${escapeHtml(item.name)}</span>
      </button>`).join('');
    sizeContainer.innerHTML = variant.sizes.map(size => `
      <button class="viewer-size ${state.selectedSize[product.id] === size ? 'is-active' : ''}" type="button" data-viewer-size="${size}" aria-pressed="${state.selectedSize[product.id] === size}">${size}</button>`).join('');
    document.getElementById('viewerColorName').textContent = variant.name;
    document.getElementById('viewerPrice').textContent = money(product.price);
    document.getElementById('viewerSizeHint').textContent = state.selectedSize[product.id]
      ? `Tamanho ${state.selectedSize[product.id]} selecionado.`
      : 'Selecione o tamanho para liberar o WhatsApp.';
    const whatsapp = document.getElementById('viewerWhatsapp');
    const selectedSize = state.selectedSize[product.id];
    if (selectedSize && variant.sizes.includes(selectedSize)) {
      whatsapp.href = makeWhatsAppUrl(product);
      whatsapp.classList.remove('is-disabled');
      whatsapp.removeAttribute('aria-disabled');
      whatsapp.target = '_blank';
      whatsapp.rel = 'noopener';
    } else {
      whatsapp.href = '#viewerSizeOptions';
      whatsapp.classList.add('is-disabled');
      whatsapp.setAttribute('aria-disabled', 'true');
      whatsapp.removeAttribute('target');
    }
  }

  // Carrossel de fotos do site dentro do visualizador (correção Luna, 13/11/2026).
  // A foto da cor selecionada abre o carrossel; as demais são as fotos do modelo no site.
  function viewerPhotoList(product) {
    const variant = getVariant(product);
    const photos = [];
    if (variant.image) photos.push(variant.image);
    (product.gallery || []).forEach(src => { if (!photos.includes(src)) photos.push(src); });
    return photos.length ? photos : [PLACEHOLDER];
  }

  function renderViewerPhotos(product) {
    const track = document.getElementById('viewerGalleryTrack');
    const dots = document.getElementById('viewerGalleryDots');
    if (!track || !dots) return;
    viewerPhotos = viewerPhotoList(product);
    viewerPhotoIndex = 0;
    track.innerHTML = viewerPhotos.map((src, index) => `
      <div class="gallery-slide"><img src="${src}" alt="${escapeHtml(product.name)} — foto ${index + 1}" loading="lazy" onerror="this.onerror=null;this.src='${PLACEHOLDER}'"></div>`).join('');
    dots.innerHTML = viewerPhotos.map((_, index) => `
      <button class="gallery-dot ${index === 0 ? 'is-active' : ''}" type="button" data-photo-dot="${index}" aria-label="Ver foto ${index + 1}"></button>`).join('');
    track.scrollLeft = 0;
  }

  function setViewerPhoto(index) {
    const track = document.getElementById('viewerGalleryTrack');
    if (!track || !viewerPhotos.length) return;
    viewerPhotoIndex = (index + viewerPhotos.length) % viewerPhotos.length;
    track.scrollTo({ left: viewerPhotoIndex * track.clientWidth, behavior: 'smooth' });
    document.querySelectorAll('[data-photo-dot]').forEach(dot => {
      dot.classList.toggle('is-active', Number(dot.dataset.photoDot) === viewerPhotoIndex);
    });
  }

  function openViewer(productId) {
    const product = PRODUCTS.find(item => item.id === productId);
    if (!product) return;
    activeProduct = product;
    document.getElementById('viewerTitle').textContent = product.name;
    document.getElementById('viewerNote').textContent = product.note || 'Gire o capacete e explore todos os ângulos.';
    document.getElementById('viewerSiteLink').href = product.url;
    updateViewerOptions(product);
    renderViewerPhotos(product);
    viewerModal.classList.add('is-open');
    viewerModal.setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.getElementById('viewerLoading').hidden = false;
    document.getElementById('viewerDemoNote').hidden = true;
    requestAnimationFrame(() => initThreeViewer(product, getVariant(product)));
  }

  function closeViewer() {
    viewerModal.classList.remove('is-open');
    viewerModal.setAttribute('aria-hidden', 'true');
    document.body.style.overflow = '';
    destroyThreeViewer();
    activeProduct = null;
  }

  function destroyThreeViewer() {
    if (resizeHandler) window.removeEventListener('resize', resizeHandler);
    resizeHandler = null;
    if (threeState) {
      if (threeState.frame) cancelAnimationFrame(threeState.frame);
      if (threeState.controls) threeState.controls.dispose();
      if (threeState.renderer) {
        threeState.renderer.dispose();
        threeState.renderer.forceContextLoss?.();
      }
    }
    viewerHost.innerHTML = '';
    threeState = null;
  }

  function makeDemoHelmet(product, variant) {
    const group = new THREE.Group();
    const shellMaterial = new THREE.MeshPhysicalMaterial({
      name: 'CASCO', color: variant.hex, roughness: 0.34, metalness: 0.12,
      clearcoat: 0.55, clearcoatRoughness: 0.28, side: THREE.DoubleSide
    });
    const innerMaterial = new THREE.MeshStandardMaterial({ name: 'FORRO_INTERNO', color: 0x20242a, roughness: 0.92, side: THREE.DoubleSide });
    const paddingMaterial = new THREE.MeshStandardMaterial({ name: 'ESPUMA', color: 0x353b43, roughness: 1 });
    const trimMaterial = new THREE.MeshStandardMaterial({ name: 'ACABAMENTO', color: 0x11151a, roughness: 0.72 });
    const visorMaterial = new THREE.MeshPhysicalMaterial({ name: 'VISEIRA', color: 0xa8d9ef, transparent: true, opacity: 0.28, roughness: 0.08, metalness: 0.05, side: THREE.DoubleSide, depthWrite: false });
    const metalMaterial = new THREE.MeshStandardMaterial({ name: 'METAL', color: 0x9ba4ad, metalness: 0.72, roughness: 0.28 });

    // Cúpula externa e superfície interna: o fundo aberto permite observar o forro por baixo.
    const shell = new THREE.Mesh(new THREE.SphereGeometry(1, 72, 48, 0, Math.PI * 2, 0, Math.PI * 0.69), shellMaterial);
    shell.name = 'CASCO';
    shell.scale.set(1.08, 0.92, 1.27);
    shell.position.y = 0.08;
    group.add(shell);

    const innerShell = new THREE.Mesh(new THREE.SphereGeometry(0.94, 64, 40, 0, Math.PI * 2, 0.08, Math.PI * 0.61), innerMaterial);
    innerShell.name = 'FORRO_INTERNO';
    innerShell.scale.set(1.08, 0.9, 1.25);
    innerShell.position.y = 0.04;
    group.add(innerShell);

    const rim = new THREE.Mesh(new THREE.TorusGeometry(0.91, 0.055, 14, 80), trimMaterial);
    rim.name = 'BORDA';
    rim.rotation.x = Math.PI / 2;
    rim.scale.set(1.18, 1.36, 1);
    rim.position.y = -0.43;
    group.add(rim);

    // Viseira frontal curva, montada em uma seção esférica.
    const visor = new THREE.Mesh(new THREE.SphereGeometry(1.015, 56, 28, 0.72, 1.72, 0.72, 0.68), visorMaterial);
    visor.name = 'VISEIRA';
    visor.scale.set(1.09, 0.95, 1.28);
    visor.position.set(0, -0.01, 0.05);
    group.add(visor);

    // Forração lateral e almofadas internas visíveis quando a câmera olha por baixo.
    [-1, 1].forEach(side => {
      const cheek = new THREE.Mesh(new THREE.SphereGeometry(0.34, 32, 24), paddingMaterial);
      cheek.name = 'ALMOFADA_INTERNA';
      cheek.scale.set(0.52, 1.22, 1.08);
      cheek.position.set(side * 0.62, -0.34, 0.08);
      group.add(cheek);

      const hinge = new THREE.Mesh(new THREE.CylinderGeometry(0.145, 0.145, 0.085, 40), metalMaterial);
      hinge.name = 'FIXACAO_VISEIRA';
      hinge.rotation.z = Math.PI / 2;
      hinge.position.set(side * 1.02, -0.02, 0.5);
      group.add(hinge);

      const strap = new THREE.Mesh(new THREE.BoxGeometry(0.105, 0.62, 0.12), trimMaterial);
      strap.name = 'CINTA';
      strap.position.set(side * 0.57, -0.72, 0.4);
      strap.rotation.z = side * -0.12;
      group.add(strap);

      const buckle = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.12, 0.08), metalMaterial);
      buckle.name = 'FIVELA';
      buckle.position.set(side * 0.57, -1.02, 0.43);
      group.add(buckle);
    });

    const crownPad = new THREE.Mesh(new THREE.SphereGeometry(0.56, 40, 24), paddingMaterial);
    crownPad.name = 'FORRO_SUPERIOR';
    crownPad.scale.set(0.9, 0.24, 1.12);
    crownPad.position.set(0, -0.31, -0.02);
    group.add(crownPad);

    if (product.kind === 'closed') {
      const chin = new THREE.Mesh(new THREE.SphereGeometry(0.78, 56, 36, 0, Math.PI * 2, 0.78, 0.95), shellMaterial.clone());
      chin.name = 'CASCO_QUEIXEIRA';
      chin.scale.set(1.03, 0.66, 0.74);
      chin.position.set(0, -0.39, 0.78);
      group.add(chin);
      const vent = new THREE.Mesh(new THREE.BoxGeometry(0.38, 0.075, 0.035), trimMaterial);
      vent.name = 'ENTRADA_AR';
      vent.position.set(0, -0.27, 1.26);
      group.add(vent);
    } else {
      const brow = new THREE.Mesh(new THREE.BoxGeometry(1.22, 0.07, 0.09), trimMaterial);
      brow.name = 'MOLDURA_VISEIRA';
      brow.position.set(0, 0.16, 1.08);
      group.add(brow);
    }

    // Pequenos grafismos demonstrativos; o acabamento final virá do GLB oficial.
    const accentMaterial = new THREE.MeshStandardMaterial({ name: 'GRAFISMO', color: 0x171b22, roughness: 0.5 });
    [-1, 1].forEach(side => {
      const accent = new THREE.Mesh(new THREE.BoxGeometry(0.035, 0.24, 0.36), accentMaterial);
      accent.name = 'GRAFISMO';
      accent.position.set(side * 0.91, 0.23, -0.08);
      accent.rotation.y = side * -0.2;
      group.add(accent);
    });

    group.rotation.y = -0.34;
    return group;
  }

  function recolorHelmet(root, hex) {
    if (!root) return;
    const meshes = [];
    root.traverse(object => { if (object.isMesh) meshes.push(object); });
    const named = meshes.filter(mesh => /casco|shell|paint|carcaca|carcaça|body/i.test(mesh.name || '') || /casco|shell|paint|carcaca|carcaça/i.test((Array.isArray(mesh.material) ? mesh.material : [mesh.material]).map(m => m?.name || '').join(' ')));
    const excluded = /(visor|lente|interior|forro|liner|foam|espuma|pad|almofada|strap|cinta|fivela|metal|vent|grafismo|borda)/i;
    const targets = named.length ? named : meshes.filter(mesh => !excluded.test(mesh.name || '')).slice(0, 1);
    targets.forEach(mesh => {
      const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
      materials.forEach(material => {
        if (material && material.color) { material.color.set(hex); material.needsUpdate = true; }
      });
    });
  }

  function fitModel(model) {
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const scale = 2.55 / maxDim;
    model.scale.setScalar(scale);
    const center = bounds.getCenter(new THREE.Vector3());
    model.position.set(-center.x * scale, -center.y * scale, -center.z * scale);
  }

  function initThreeViewer(product, variant) {
    if (!window.THREE || !THREE.WebGLRenderer) {
      document.getElementById('viewerLoading').textContent = 'Este aparelho ou navegador não liberou o visualizador 3D. Tente abrir no Chrome atualizado.';
      return;
    }
    destroyThreeViewer();
    const width = Math.max(280, viewerHost.clientWidth);
    const height = Math.max(320, viewerHost.clientHeight);
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf3f6fa);
    const camera = new THREE.PerspectiveCamera(34, width / height, 0.1, 100);
    camera.position.set(3.5, 1.8, 4.6);
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, powerPreference: 'high-performance' });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.8));
    renderer.setSize(width, height);
    renderer.outputEncoding = THREE.sRGBEncoding;
    viewerHost.appendChild(renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x667487, 1.65));
    const key = new THREE.DirectionalLight(0xffffff, 2.0);
    key.position.set(4, 6, 5);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xd7e8ff, 1.0);
    fill.position.set(-4, 2, -4);
    scene.add(fill);
    const rimLight = new THREE.DirectionalLight(0xffffff, 0.75);
    rimLight.position.set(0, 3, -5);
    scene.add(rimLight);

    const floor = new THREE.Mesh(new THREE.CircleGeometry(2.5, 64), new THREE.MeshStandardMaterial({ color: 0xe6edf5, roughness: 0.95 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.y = -1.42;
    scene.add(floor);

    const controls = THREE.OrbitControls ? new THREE.OrbitControls(camera, renderer.domElement) : null;
    if (controls) {
      controls.enableDamping = true;
      controls.dampingFactor = 0.065;
      controls.enablePan = true;
      controls.enableZoom = true;
      controls.minDistance = 2.25;
      controls.maxDistance = 7.5;
      controls.minPolarAngle = 0.015;
      controls.maxPolarAngle = Math.PI - 0.015;
      controls.target.set(0, -0.02, 0);
      controls.update();
    }

    const demo = makeDemoHelmet(product, variant);
    scene.add(demo);
    document.getElementById('viewerLoading').hidden = true;
    document.getElementById('viewerDemoNote').hidden = false;
    threeState = { product, variant, scene, camera, renderer, controls, model: demo, frame: null };

    const loader = THREE.GLTFLoader ? new THREE.GLTFLoader() : null;
    if (loader && product.glb) {
      loader.load(product.glb, gltf => {
        if (!threeState || threeState.product.id !== product.id) return;
        scene.remove(demo);
        const model = gltf.scene;
        fitModel(model);
        recolorHelmet(model, variant.hex);
        scene.add(model);
        threeState.model = model;
        document.getElementById('viewerDemoNote').hidden = true;
      }, undefined, () => {
        // Até o GLB oficial chegar, mantém o modelo demonstrativo com rotação livre.
        document.getElementById('viewerDemoNote').hidden = false;
      });
    }

    const animate = () => {
      if (!threeState || !threeState.renderer) return;
      threeState.frame = requestAnimationFrame(animate);
      if (threeState.controls) threeState.controls.update();
      renderer.render(scene, camera);
    };
    animate();

    resizeHandler = () => {
      if (!threeState) return;
      const w = Math.max(280, viewerHost.clientWidth);
      const h = Math.max(320, viewerHost.clientHeight);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    window.addEventListener('resize', resizeHandler);
  }

  function setCameraView(view) {
    if (!threeState) return;
    const { camera, controls } = threeState;
    const presets = {
      frente: { p: [0, 0.1, 4.8], up: [0, 1, 0] },
      traseira: { p: [0, 0.1, -4.8], up: [0, 1, 0] },
      lateral: { p: [4.8, 0.2, 0], up: [0, 1, 0] },
      cima: { p: [0, 4.8, 0.1], up: [0, 0, -1] },
      baixo: { p: [0, -4.8, 0.1], up: [0, 0, 1] },
      interior: { p: [0, -2.15, 3.4], up: [0, 1, 0] }
    };
    const preset = presets[view] || presets.frente;
    camera.up.set(...preset.up);
    camera.position.set(...preset.p);
    if (controls) {
      controls.target.set(0, view === 'interior' ? -0.25 : -0.02, 0);
      controls.update();
    } else {
      camera.lookAt(0, 0, 0);
    }
    document.querySelectorAll('[data-camera-view]').forEach(button => {
      button.classList.toggle('is-active', button.dataset.cameraView === view);
      button.setAttribute('aria-pressed', String(button.dataset.cameraView === view));
    });
  }

  sizeFilters.addEventListener('click', event => {
    const button = event.target.closest('[data-size]');
    if (!button) return;
    const size = Number(button.dataset.size);
    state.sizeFilter = state.sizeFilter === size ? null : size;
    renderProducts();
  });

  modelFilters.addEventListener('click', event => {
    const button = event.target.closest('[data-model]');
    if (!button) return;
    state.modelFilter = button.dataset.model;
    renderProducts();
  });

  document.getElementById('clearSize').addEventListener('click', () => {
    state.sizeFilter = null;
    renderProducts();
  });
  document.getElementById('resetFilters').addEventListener('click', () => {
    state.sizeFilter = null;
    state.modelFilter = 'all';
    renderProducts();
  });

  productGrid.addEventListener('click', event => {
    const target = event.target.closest('[data-action]');
    if (!target) return;
    if (target.dataset.action === 'open-3d') openViewer(target.dataset.product);
    if (target.dataset.action === 'variant') selectVariant(target.dataset.product, Number(target.dataset.variant));
  });

  document.getElementById('closeViewer').addEventListener('click', closeViewer);
  document.getElementById('viewerCloseBottom').addEventListener('click', closeViewer);
  document.getElementById('viewerColorOptions').addEventListener('click', event => {
    const button = event.target.closest('[data-viewer-variant]');
    if (!button || !activeProduct) return;
    selectVariant(activeProduct.id, Number(button.dataset.viewerVariant));
  });
  document.getElementById('viewerSizeOptions').addEventListener('click', event => {
    const button = event.target.closest('[data-viewer-size]');
    if (!button || !activeProduct) return;
    selectSize(activeProduct.id, Number(button.dataset.viewerSize));
  });
  document.getElementById('viewerViews').addEventListener('click', event => {
    const button = event.target.closest('[data-camera-view]');
    if (button) setCameraView(button.dataset.cameraView);
  });
  document.getElementById('viewerPhotoPrev').addEventListener('click', () => setViewerPhoto(viewerPhotoIndex - 1));
  document.getElementById('viewerPhotoNext').addEventListener('click', () => setViewerPhoto(viewerPhotoIndex + 1));
  document.getElementById('viewerGalleryDots').addEventListener('click', event => {
    const dot = event.target.closest('[data-photo-dot]');
    if (dot) setViewerPhoto(Number(dot.dataset.photoDot));
  });
  document.getElementById('viewerGalleryTrack').addEventListener('click', event => {
    const image = event.target.closest('img');
    if (image) image.classList.toggle('is-zoomed');
  });
  document.getElementById('viewerGalleryTrack').addEventListener('scroll', event => {
    const track = event.currentTarget;
    if (!track.clientWidth) return;
    const index = Math.round(track.scrollLeft / track.clientWidth);
    if (index !== viewerPhotoIndex && index >= 0 && index < viewerPhotos.length) {
      viewerPhotoIndex = index;
      document.querySelectorAll('[data-photo-dot]').forEach(dot => {
        dot.classList.toggle('is-active', Number(dot.dataset.photoDot) === index);
      });
    }
  }, { passive: true });
  document.getElementById('viewerWhatsapp').addEventListener('click', event => {
    if (event.currentTarget.getAttribute('aria-disabled') === 'true') {
      event.preventDefault();
      document.getElementById('viewerSizeHint').textContent = 'Escolha uma numeração disponível para continuar.';
      document.getElementById('viewerSizeOptions').scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
  viewerModal.addEventListener('click', event => {
    if (event.target === viewerModal) closeViewer();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && viewerModal.classList.contains('is-open')) closeViewer();
  });

  renderProducts();
})();
