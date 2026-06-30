// product-config-modal.js - product classification settings modal
// ---------- Product Config System ----------
    function escapeHtml(value) {
      return String(value ?? '').replace(/[&<>"']/g, ch => ({
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }[ch]));
    }

    async function openProductConfigModal() {
      try {
        const resp = await fetchJson('/api/product-config');
        const products = unwrapApiResponse(resp) || [];
        const rows = products.map(p => `
          <tr data-code="${escapeHtml(p.product_code)}" data-business-type="${escapeHtml(p.business_type || '')}">
            <td>${escapeHtml(p.product_code)}</td>
            <td>${escapeHtml(p.product_name || '-')}</td>
            <td>${escapeHtml(p.business_type || '-')}</td>
            <td>
              <select data-field="is_annuity">
                <option value="N" ${p.is_annuity === 'N' ? 'selected' : ''}>N</option>
                <option value="Y" ${p.is_annuity === 'Y' ? 'selected' : ''}>Y</option>
              </select>
            </td>
            <td>
              <select data-field="is_protection">
                <option value="N" ${p.is_protection === 'N' ? 'selected' : ''}>N</option>
                <option value="Y" ${p.is_protection === 'Y' ? 'selected' : ''}>Y</option>
              </select>
            </td>
          </tr>
        `).join('');

        modalTitle.textContent = '参数设置 — 经代产品分类';
        modalBody.innerHTML = `
          <p style="color: var(--text-secondary); font-size: 13px; margin-bottom: 12px;">
            经代产品仍通过本模块手工维护分类；转型业务商保年金和社会保障类产品直接读取业绩基表标识。保存后系统会自动重算经代业绩并刷新看板。
          </p>
          <div style="overflow-y: auto; max-height: 55vh;">
            <table class="product-config-table">
              <thead>
                <tr>
                  <th>产品代码</th>
                  <th>产品名称</th>
                  <th>业务模式</th>
                  <th>商保年金</th>
                  <th>保障类产品</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          </div>
          <div class="product-config-actions">
            <button class="chart-btn" data-product-config-action="cancel">取消</button>
            <button class="chart-btn" style="background: var(--accent); color: #fff;" data-product-config-action="save">保存</button>
          </div>
        `;
        bindProductConfigActions();
        modalOverlay.classList.add('active', 'modal-product-config');
      } catch (e) {
        console.error('加载产品配置失败', e);
        alert('加载产品配置失败：' + e.message);
      }
    }

    function bindProductConfigActions() {
      modalBody.querySelector('[data-product-config-action="cancel"]')
        ?.addEventListener('click', () => closeModal());
      modalBody.querySelector('[data-product-config-action="save"]')
        ?.addEventListener('click', saveProductConfig);
    }

    async function saveProductConfig() {
      const rows = modalBody.querySelectorAll('.product-config-table tbody tr');
      const products = [];
      rows.forEach(row => {
        const code = row.getAttribute('data-code');
        const businessType = row.getAttribute('data-business-type') || '';
        const annuity = row.querySelector('[data-field="is_annuity"]').value;
        const protection = row.querySelector('[data-field="is_protection"]').value;
        products.push({ product_code: code, business_type: businessType, is_annuity: annuity, is_protection: protection });
      });
      try {
        const resp = await adminFetch(apiUrl('/api/product-config'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ products }),
        });
        if (!resp.ok) throw new Error('产品配置保存失败：' + resp.status);
        const result = unwrapApiResponse(await resp.json()) || {};
        if (result.recalculated > 0) {
          alert(`经代产品配置已保存，已重新计算 ${result.recalculated} 条经代业绩数据。看板即将刷新。`);
          closeModal();
          await recalculateDashboard();
        } else {
          alert('经代产品配置已保存。请重新导入经代数据或点击「重新计算」使配置生效。');
          closeModal();
        }
      } catch (e) {
        console.error('保存产品配置失败', e);
        alert('保存失败：' + e.message);
      }
    }
