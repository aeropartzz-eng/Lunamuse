# Catálogo interativo 3D — AeroPartz Auto e Motos

Página estática em HTML, CSS e JavaScript, com prioridade para celular.

## Como abrir

1. Extraia o ZIP.
2. Abra `index.html` no Chrome, Edge ou Firefox, com internet ativa.
3. Toque na foto, no nome ou em **Abrir visualizador 3D** para abrir a experiência 3D.
4. Arraste com o dedo para girar; use dois dedos para aproximar/afastar. Os botões Frente, Trás, Lado, Cima, Baixo e Interior levam a ângulos predefinidos.
5. Escolha a cor e a numeração no visualizador. O WhatsApp só é liberado depois da seleção do tamanho.

Para carregar os arquivos GLB locais com mais segurança, execute `iniciar-local.bat` no Windows e abra `http://localhost:8000`.

## Arquivos

- `index.html` — estrutura e visualizador.
- `styles.css` — identidade visual responsiva.
- `app.js` — dados dos produtos, filtros, cores, tamanhos, WhatsApp e Three.js.
- A logo horizontal oficial é carregada diretamente do site AeroPartz.
- `assets/3d/` — pasta para os seis arquivos GLB oficiais.

## Modelos 3D definitivos

O projeto tem um visualizador Three.js com um modelo demonstrativo procedural para testar a interação. Ele NÃO é uma reprodução técnica fiel dos capacetes.

Para exibir os capacetes reais, adicione um arquivo GLB para cada modelo:

- `assets/3d/atomic-elite.glb`
- `assets/3d/atomic-solid.glb`
- `assets/3d/r8.glb`
- `assets/3d/liberty-3-elite.glb`
- `assets/3d/liberty-4.glb`
- `assets/3d/sport-moto-788.glb`

**Importante para o efeito solicitado:** para o cliente conseguir olhar por dentro, por baixo e observar o forro, o GLB precisa conter a geometria interna real (forração, espuma, almofadas, cinta jugular, fecho e parte interna da viseira, quando houver). Uma malha externa fechada não revela esses detalhes só por girar a câmera.

Recomendação para exportação:
- Um GLB por modelo, não um GLB por cor.
- Casco com nome de mesh/material `CASCO` ou `SHELL` para permitir troca de cor.
- Viseira, forro, espuma, almofadas, cintas, fivelas e acabamentos em materiais separados.
- Origem centralizada no capacete, frente orientada para +Z, topo para +Y e escala aplicada antes da exportação.
- Geometria com faces internas modeladas, sem buracos ou normais invertidas.

A troca de cor do catálogo altera o material do casco. Grafismos específicos de cada cor precisam ser configurados como materiais/texturas próprios no GLB se a intenção for reproduzi-los exatamente.

## Identidade e imagens

A logomarca horizontal é chamada do endereço oficial `https://aeropartz.com.br/brand/aeropartz/logo-horizontal.webp`. As imagens de vitrine são carregadas do domínio oficial `aeropartz.com.br`.

## Dados comerciais

Os preços, cores e tamanhos foram mantidos conforme os dados fornecidos para o catálogo. Links de compra:
- Atomic Elite: `https://aeropartz.com.br/loja/produtos/14/new-atomic-elite`
- Atomic Solid: `https://aeropartz.com.br/loja/produtos/7/new-atomic-solid`
- R8: `https://aeropartz.com.br/loja/produtos/6/r8`
- Liberty 3: `https://aeropartz.com.br/loja/produtos/9/new-liberty-3`
- Liberty 4: `https://aeropartz.com.br/loja/produtos/10/new-liberty-4`
- Sport Moto 788: `https://aeropartz.com.br/loja/produtos/5/sport-moto-788`

WhatsApp: (85) 99233-3378. Retirada: Rua do Congresso, 371 — Aerolândia, Fortaleza/CE, combinando o horário. Entrega por Uber Flash, por conta do comprador.

Não há carrinho, checkout ou pagamento online.
