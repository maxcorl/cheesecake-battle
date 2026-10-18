let currentSecret = localStorage.getItem('cheesecake_admin_secret') || '';
let currentFilter = 'pending';
let allOrders = [];
let allColocs = [];

document.addEventListener('DOMContentLoaded', () => {
  if (currentSecret) {
    document.getElementById('secretInput').value = currentSecret;
    loadDashboard();
  }

  document.getElementById('authForm').addEventListener('submit', (e) => {
    e.preventDefault();
    currentSecret = document.getElementById('secretInput').value.trim();
    localStorage.setItem('cheesecake_admin_secret', currentSecret);
    loadDashboard();
  });
});

function logoutAdmin() {
  localStorage.removeItem('cheesecake_admin_secret');
  currentSecret = '';
  document.getElementById('authSection').style.display = 'block';
  document.getElementById('dashboardSection').style.display = 'none';
}

async function loadDashboard() {
  if (!currentSecret) return;

  try {
    const res = await fetch(`/api/admin/orders?secret=${encodeURIComponent(currentSecret)}`);
    if (res.status === 403) {
      showToast("Code secret incorrect !", "error");
      localStorage.removeItem('cheesecake_admin_secret');
      return;
    }
    if (!res.ok) throw new Error("Erreur serveur");

    const data = await res.json();
    allOrders = data.orders;
    allColocs = data.colocations;

    // Update stats
    document.getElementById('statPending').textContent = data.stats.pending_orders;
    document.getElementById('statSlices').textContent = data.stats.validated_slices;
    document.getElementById('statRevenue').textContent = `${data.stats.validated_revenue.toFixed(2)} €`;

    // Show dashboard
    document.getElementById('authSection').style.display = 'none';
    document.getElementById('dashboardSection').style.display = 'block';

    renderOrders();
    renderColocs();

  } catch (err) {
    showToast(err.message, "error");
  }
}

function setFilter(filter) {
  currentFilter = filter;
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.filter === filter);
  });
  renderOrders();
}

function renderOrders() {
  const tbody = document.getElementById('ordersTableBody');
  tbody.innerHTML = '';

  const filtered = allOrders.filter(o => {
    if (currentFilter === 'all') return true;
    return o.status === currentFilter;
  });

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted); padding: 30px;">Aucune commande dans cette catégorie.</td></tr>`;
    return;
  }

  filtered.forEach(o => {
    let itemsObj = {};
    try {
      itemsObj = JSON.parse(o.items_json);
    } catch(e) {}

    const itemsSummary = Object.entries(itemsObj)
      .map(([name, qty]) => `<strong>${qty}x</strong> ${name}`)
      .join('<br>');

    let statusBadge = '';
    if (o.status === 'pending') statusBadge = `<span class="status-badge status-pending">En attente</span>`;
    else if (o.status === 'approved') statusBadge = `<span class="status-badge status-approved">Validée</span>`;
    else statusBadge = `<span class="status-badge status-rejected">Refusée</span>`;

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>#${o.id}</td>
      <td><strong style="font-size: 1.05rem; color: #fff;">${o.coloc_name}</strong></td>
      <td><strong>📍 ${o.room_or_address || 'Non précisé'}</strong></td>
      <td><span style="color: var(--accent-gold); font-weight: 700;">🕒 ${o.notes || 'Dès que possible'}</span></td>
      <td>${itemsSummary}</td>
      <td><strong>${o.total_price.toFixed(2)} €</strong><br><small>(${o.total_slices} parts)</small></td>
      <td>${statusBadge}</td>
      <td>
        <div class="action-group">
          ${o.status !== 'approved' ? `
            <button class="btn-action btn-validate" onclick="validateOrder(${o.id})">✅ Valider</button>
          ` : ''}
          ${o.status !== 'rejected' ? `
            <button class="btn-action btn-reject" onclick="rejectOrder(${o.id})">❌ Refuser</button>
          ` : ''}
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function validateOrder(orderId) {
  const formData = new FormData();
  formData.append('secret', currentSecret);

  try {
    const res = await fetch(`/api/admin/orders/${orderId}/validate`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur de validation");

    showToast(data.message, "success");
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function rejectOrder(orderId) {
  if (!confirm("Voulez-vous vraiment refuser / annuler cette commande ?")) return;

  const formData = new FormData();
  formData.append('secret', currentSecret);

  try {
    const res = await fetch(`/api/admin/orders/${orderId}/reject`, {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");

    showToast(data.message, "success");
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderColocs() {
  const tbody = document.getElementById('colocsTableBody');
  tbody.innerHTML = '';

  allColocs.forEach(coloc => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${coloc.name}</strong></td>
      <td><span style="font-size: 1.1rem; font-weight: 800; color: var(--accent-gold);">${coloc.score}</span> parts</td>
      <td>
        <div style="display: flex; gap: 8px; align-items: center;">
          <input type="number" id="colocScore_${coloc.id}" value="${coloc.score}" min="0" class="form-control" style="width: 80px; padding: 6px 10px;">
          <button class="btn btn-outline" style="padding: 6px 12px; font-size: 0.8rem;" onclick="saveColocScore(${coloc.id})">Enregistrer</button>
        </div>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function saveColocScore(colocId) {
  const newScore = document.getElementById(`colocScore_${colocId}`).value;
  const formData = new FormData();
  formData.append('coloc_id', colocId);
  formData.append('new_score', newScore);
  formData.append('secret', currentSecret);

  try {
    const res = await fetch('/api/admin/colocations/score', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Erreur");

    showToast("Score mis à jour !", "success");
    loadDashboard();
  } catch (err) {
    showToast(err.message, "error");
  }
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
