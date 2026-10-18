// State
const cart = {};
let flavors = [];

// Initialize
document.addEventListener('DOMContentLoaded', () => {
  initQuantities();
  initForm();
  initSearchColoc();
});

function initQuantities() {
  document.querySelectorAll('.flavor-card').forEach(card => {
    const name = card.dataset.name;
    const price = parseFloat(card.dataset.price);
    flavors.push({ name, price });

    const minusBtn = card.querySelector('.qty-minus');
    const plusBtn = card.querySelector('.qty-plus');
    const valDisplay = card.querySelector('.qty-val');

    minusBtn.addEventListener('click', () => {
      let current = cart[name] || 0;
      if (current > 0) {
        cart[name] = current - 1;
        valDisplay.textContent = cart[name];
        updateCartUI();
      }
    });

    plusBtn.addEventListener('click', () => {
      let current = cart[name] || 0;
      cart[name] = current + 1;
      valDisplay.textContent = cart[name];
      updateCartUI();
    });
  });
}

function updateCartUI() {
  let totalCount = 0;
  let totalPrice = 0;

  for (const f of flavors) {
    const qty = cart[f.name] || 0;
    totalCount += qty;
    totalPrice += qty * f.price;
  }

  const floatingBar = document.getElementById('floatingBar');
  const barCount = document.getElementById('barCount');
  const barTotal = document.getElementById('barTotal');

  if (totalCount > 0) {
    barCount.textContent = `${totalCount} part${totalCount > 1 ? 's' : ''}`;
    barTotal.textContent = `${totalPrice.toFixed(2)} €`;
    floatingBar.classList.add('active');
  } else {
    floatingBar.classList.remove('active');
  }
}

function openOrderModal() {
  let totalCount = 0;
  for (const f of flavors) {
    totalCount += (cart[f.name] || 0);
  }

  if (totalCount === 0) {
    showToast("Veuillez choisir au moins 1 part de cheesecake d'abord !", "error");
    return;
  }

  // Populate Recap
  const recapItems = document.getElementById('recapItems');
  recapItems.innerHTML = '';
  let totalPrice = 0;

  for (const f of flavors) {
    const qty = cart[f.name] || 0;
    if (qty > 0) {
      const linePrice = qty * f.price;
      totalPrice += linePrice;

      const row = document.createElement('div');
      row.className = 'order-recap-row';
      row.innerHTML = `
        <span>${qty}x ${f.name}</span>
        <span>${linePrice.toFixed(2)} €</span>
      `;
      recapItems.appendChild(row);
    }
  }

  const totalRow = document.createElement('div');
  totalRow.className = 'order-recap-row';
  totalRow.innerHTML = `
    <span>Total (${totalCount} part${totalCount > 1 ? 's' : ''})</span>
    <span>${totalPrice.toFixed(2)} €</span>
  `;
  recapItems.appendChild(totalRow);

  document.getElementById('orderModal').classList.add('active');
}

function closeOrderModal() {
  document.getElementById('orderModal').classList.remove('active');
}

function initForm() {
  const form = document.getElementById('orderForm');
  if (!form) return;

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const coloc_name = document.getElementById('colocNameInput').value.trim();
    const phone = document.getElementById('phoneInput').value.trim();
    const delivery_location = document.getElementById('locationInput').value.trim();
    const delivery_time = document.getElementById('timeInput').value.trim();

    if (!coloc_name || !phone || !delivery_location || !delivery_time) {
      showToast("Veuillez renseigner le nom de la coloc, votre téléphone, le lieu et l'horaire de livraison.", "error");
      return;
    }

    const submitBtn = document.getElementById('submitOrderBtn');
    submitBtn.disabled = true;
    submitBtn.textContent = "Validation en cours...";

    try {
      const res = await fetch('/api/orders', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          coloc_name,
          phone,
          delivery_location,
          delivery_time,
          items: cart
        })
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || "Erreur lors de la commande.");
      }

      // Success
      closeOrderModal();
      showToast("🎉 Commande enregistrée ! L'équipe va la valider pour votre classement !", "success");
      launchConfetti();

      // Reset cart
      for (const f of flavors) {
        cart[f.name] = 0;
      }
      document.querySelectorAll('.qty-val').forEach(el => el.textContent = '0');
      updateCartUI();
      form.reset();

      // Refresh leaderboard after 1s
      setTimeout(refreshLeaderboard, 1200);

    } catch (err) {
      showToast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Confirmer la commande 🏁";
    }
  });
}

async function refreshLeaderboard() {
  try {
    const res = await fetch('/api/leaderboard');
    if (!res.ok) return;
    const colocs = await res.json();
    renderLeaderboard(colocs);
  } catch (err) {
    console.error("Leaderboard refresh error", err);
  }
}

function renderLeaderboard(colocs) {
  const container = document.getElementById('leaderboardRows');
  if (!container) return;

  if (!colocs || colocs.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px 20px; color: var(--text-muted); background: rgba(255, 255, 255, 0.02); border-radius: var(--radius-md); border: 1px dashed var(--border-glass);">
        <div style="font-size: 2.2rem; margin-bottom: 8px;">🏁</div>
        <div style="font-size: 1.15rem; font-weight: 700; color: #fff; margin-bottom: 6px;">La course n'a pas encore commencé !</div>
        <div style="font-size: 0.9rem;">Commandez vos parts pour inscrire votre colocation au sommet du classement.</div>
      </div>
    `;
    return;
  }

  // Render rows from 4th onwards (or full list)
  let html = '';
  colocs.forEach((coloc, index) => {
    const rank = index + 1;
    let rankEmoji = `#${rank}`;
    if (rank === 1) rankEmoji = '🥇 1er';
    else if (rank === 2) rankEmoji = '🥈 2e';
    else if (rank === 3) rankEmoji = '🥉 3e';

    html += `
      <div class="coloc-row">
        <div class="coloc-left">
          <span class="coloc-rank">${rankEmoji}</span>
          <div>
            <div class="coloc-info-name">${coloc.name}</div>
            ${coloc.address ? `<div class="coloc-info-address">${coloc.address}</div>` : ''}
          </div>
        </div>
        <div class="coloc-right">
          <div class="coloc-score-pill">🍰 ${coloc.score} part${coloc.score > 1 ? 's' : ''}</div>
        </div>
      </div>
    `;
  });
  container.innerHTML = html;
}

function initSearchColoc() {
  const searchInput = document.getElementById('searchColoc');
  if (!searchInput) return;

  searchInput.addEventListener('input', (e) => {
    const val = e.target.value.toLowerCase();
    document.querySelectorAll('.coloc-row').forEach(row => {
      const name = row.querySelector('.coloc-info-name').textContent.toLowerCase();
      if (name.includes(val)) {
        row.style.display = 'flex';
      } else {
        row.style.display = 'none';
      }
    });
  });
}

function showToast(msg, type = "success") {
  const toast = document.getElementById('toast');
  if (!toast) return;

  toast.textContent = msg;
  toast.style.background = type === "error" ? "#ef4444" : "#10b981";
  toast.classList.add('show');

  setTimeout(() => {
    toast.classList.remove('show');
  }, 4000);
}

// Celebration Confetti
function launchConfetti() {
  if (window.confetti) {
    window.confetti({
      particleCount: 120,
      spread: 70,
      origin: { y: 0.6 }
    });
  }
}
