/* ─── Global JS – Lost & Found ─────────────────────────── */

document.addEventListener('DOMContentLoaded', () => {

  // ── Hamburger ──────────────────────────────────────────
  const hamburger  = document.getElementById('hamburger');
  const mobileMenu = document.getElementById('mobileMenu');
  if (hamburger) {
    hamburger.addEventListener('click', () => {
      mobileMenu.classList.toggle('active');
    });
  }

  // ── Toast container ────────────────────────────────────
  if (!document.getElementById('toast-container')) {
    const tc = document.createElement('div');
    tc.id = 'toast-container';
    document.body.appendChild(tc);
  }

  // ── Dashboard Search ───────────────────────────────────
  const searchInput    = document.getElementById('searchInput');
  const categoryFilter = document.getElementById('categoryFilter');
  const tabBtns        = document.querySelectorAll('.tab-btn');
  const dualFeed       = document.getElementById('dualFeed');
  const searchResults  = document.getElementById('searchResults');
  const resultsGrid    = document.getElementById('resultsGrid');

  let searchTimeout = null;
  let activeStatus  = '';

  function triggerSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(doSearch, 320);
  }

  async function doSearch() {
    const q   = searchInput ? searchInput.value.trim() : '';
    const cat = categoryFilter ? categoryFilter.value : '';

    if (!q && !cat && !activeStatus) {
      if (dualFeed)      dualFeed.style.display      = 'grid';
      if (searchResults) searchResults.style.display = 'none';
      return;
    }

    const params = new URLSearchParams({ q, category: cat, status: activeStatus });
    try {
      const res   = await fetch(`/api/search?${params}`);
      const items = await res.json();
      renderResults(items);
    } catch (e) {
      showToast('Search failed. Please try again.', 'error');
    }
  }

  function renderResults(items) {
    if (!resultsGrid || !dualFeed || !searchResults) return;
    dualFeed.style.display      = 'none';
    searchResults.style.display = 'block';
    resultsGrid.innerHTML       = '';

    if (items.length === 0) {
      resultsGrid.innerHTML = `<div class="empty-state"><span>🔍</span><p>No items found matching your search.</p></div>`;
      return;
    }

    items.forEach(item => {
      const card = buildCard(item);
      resultsGrid.appendChild(card);
    });
  }

  function buildCard(item) {
    const div = document.createElement('div');
    div.className = 'item-card';

    const claimBtn = (item.claim_status === 'Available' && item.status === 'Found')
      ? `<div class="card-action">
           <button class="btn btn-success btn-sm btn-full"
                   onclick="claimItem(${item.id}, this)">🤝 Claim This Item</button>
         </div>` : '';

    const imgHtml = item.image_path
      ? `<img src="/uploads/${item.image_path}" alt="${esc(item.title)}" class="card-img" loading="lazy"/>`
      : `<div class="card-img-placeholder"><span>📷</span></div>`;

    const claimBadge = item.claim_status !== 'Available'
      ? `<span class="badge badge-${item.claim_status.toLowerCase()}">${item.claim_status}</span>` : '';

    div.innerHTML = `
      <a href="/item/${item.id}" class="card-link">
        <div class="card-img-wrap">
          ${imgHtml}
          <span class="badge badge-${item.status.toLowerCase()}">${item.status}</span>
          ${claimBadge}
        </div>
        <div class="card-body">
          <div class="card-meta">
            <span class="card-category">${esc(item.category)}</span>
            <span class="card-date">${(item.created_at || '').slice(0,10)}</span>
          </div>
          <h3 class="card-title">${esc(item.title)}</h3>
          <p class="card-location">📍 ${esc(item.location)}</p>
          <p class="card-desc">${esc(item.description).slice(0,90)}${item.description.length > 90 ? '…' : ''}</p>
          <p class="card-reporter">By <strong>${esc(item.username || '')}</strong></p>
        </div>
      </a>
      ${claimBtn}
    `;
    return div;
  }

  if (searchInput)    searchInput.addEventListener('input', triggerSearch);
  if (categoryFilter) categoryFilter.addEventListener('change', triggerSearch);

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeStatus = btn.dataset.status;
      triggerSearch();
    });
  });

  setTimeout(() => {
    document.querySelectorAll('.flash').forEach(f => {
      f.style.opacity = '0';
      f.style.transition = 'opacity 0.5s';
      setTimeout(() => f.remove(), 500);
    });
  }, 6000);

});

/* ── Claim Item Modal Logic ────────────────────────────── */
let activeClaimBtn = null;

function closeClaimModal() {
  document.getElementById('claimModal').classList.remove('active');
  document.getElementById('claimForm').reset();
  activeClaimBtn = null;
}

async function claimItem(itemId, btn) {
  activeClaimBtn = btn;
  document.getElementById('claimItemId').value = itemId;
  document.getElementById('claimModal').classList.add('active');
}

// Handle Modal Submission
document.addEventListener('DOMContentLoaded', () => {
  const claimForm = document.getElementById('claimForm');
  if (claimForm) {
    claimForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const itemId  = document.getElementById('claimItemId').value;
      const details = document.getElementById('claimDetails').value;
      const submitBtn = document.getElementById('claimSubmitBtn');

      submitBtn.disabled = true;
      submitBtn.textContent = 'Sending...';

      try {
        const res = await fetch(`/claim/${itemId}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ claim_details: details })
        });
        const data = await res.json();

        if (data.ok) {
          showToast(data.message, 'success');
          closeClaimModal();
          
          // Animate and remove the card associated with activeClaimBtn
          if (activeClaimBtn) {
            const card = activeClaimBtn.closest('.item-card');
            if (card) {
              card.classList.add('fade-out-tear');
              setTimeout(() => {
                card.remove();
                // Simple feed check
                document.querySelectorAll('.item-grid').forEach(grid => {
                  if (grid.querySelectorAll('.item-card').length === 0) {
                    grid.innerHTML = '<div class="empty-state"><span>😌</span><p>No more items here.</p></div>';
                  }
                });
              }, 800);
            }
          } else {
            // If we're on the detail page, just reload or redirect
            setTimeout(() => location.href = '/', 1500);
          }
        } else {
          showToast(data.error || 'Claim failed.', 'error');
          submitBtn.disabled = false;
          submitBtn.textContent = 'Send Claim';
        }
      } catch (err) {
        showToast('Network error.', 'error');
        submitBtn.disabled = false;
        submitBtn.textContent = 'Send Claim';
      }
    });
  }
});

/* ── Toast Utility ──────────────────────────────────────── */
function showToast(msg, type = 'info', duration = 4000) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `<span>${msg}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity    = '0';
    toast.style.transition = 'opacity 0.4s';
    setTimeout(() => toast.remove(), 400);
  }, duration);
}

/* ── HTML Escape Utility ────────────────────────────────── */
function esc(str) {
  const d = document.createElement('div');
  d.textContent = str || '';
  return d.innerHTML;
}
