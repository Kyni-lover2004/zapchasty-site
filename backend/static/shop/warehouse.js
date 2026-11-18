const printButton = document.querySelector('[data-print-label]');
printButton?.addEventListener('click', async () => {
  const error = document.querySelector('[data-print-error]');
  error.hidden = true;
  try {
    const codes = document.querySelectorAll('.warehouse-label img');
    await Promise.all(Array.from(codes, (code) => code.decode()));
  } catch {
    error.hidden = false;
    return;
  }
  window.print();
});

const search = document.getElementById('warehouse-search');
const part = document.getElementById('warehouse-part');
const suggestions = document.getElementById('warehouse-suggestions');

if (search && part && suggestions) {
  let timer;
  let controller;

  search.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      suggestions.querySelector('button')?.focus();
    }
  });

  search.addEventListener('input', () => {
    clearTimeout(timer);
    controller?.abort();
    suggestions.replaceChildren();
    const query = search.value.trim();
    if (!query) return;

    controller = new AbortController();
    const { signal } = controller;
    timer = setTimeout(async () => {
      const url = new URL(search.dataset.url, window.location.origin);
      url.searchParams.set('q', query);
      try {
        const response = await fetch(url, { signal, headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Поиск недоступен');
        const { products } = await response.json();
        if (signal.aborted) return;
        if (!products.length) suggestions.textContent = 'Совпадений нет.';
        for (const product of products) {
          const choice = document.createElement('button');
          choice.type = 'button';
          choice.textContent = [product.name, product.subtitle, product.part].filter(Boolean).join(' · ');
          choice.addEventListener('click', () => {
            search.value = product.name;
            part.value = product.part;
            suggestions.replaceChildren();
            part.form.elements.quantity.focus();
            part.form.elements.quantity.select();
          });
          suggestions.append(choice);
        }
      } catch (error) {
        if (!signal.aborted) suggestions.textContent = 'Поиск недоступен. Введите артикул вручную.';
      }
    }, 180);
  });
}
