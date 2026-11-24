import {query} from './api.js';
import {el, table} from './table.js';

const byId = id => document.getElementById(id);
const settings = JSON.parse(byId('settings').textContent);
const settlePanel = byId('settle-panel');
const mainGrid = document.querySelector('.stove .grid');
const notice = byId('settle-notice');
let current = null;

function flash(message, error = false) {
  notice.value = message;
  notice.classList.toggle('problem', error);
}

function statusTag(status) {
  const label = status === 'confirmed' ? '已确认' : status === 'reversed' ? '已冲销' : status;
  return el('span', label, status === 'confirmed' ? 'state' : 'state problem');
}

function kpi(label, value, suffix = '份') {
  const item = el('div');
  item.className = 'kpi';
  item.append(el('small', label), el('strong', String(value)), el('span', suffix));
  return item;
}

function render(report) {
  current = report;
  byId('settle-receipt-id').textContent = report.receipt_id;
  const box = byId('settle-kpis');
  box.replaceChildren(
    kpi('回执总额', report.total_portions),
    kpi('已占用(已结)', report.occupied_portions),
    kpi('可用余额', report.remaining_portions),
    kpi('已冲销', report.reversed_portions),
  );
  if (report.closed_at) {
    const unclaimed = el('div');
    unclaimed.className = `kpi ${report.unclaimed_portions ? 'kpi--warn' : ''}`;
    unclaimed.append(el('small', report.fully_settled ? '关账：全部已结' : '关账：未结份数'),
      el('strong', String(report.unsettled_portions ?? report.unclaimed_portions ?? 0)), el('span', '份'));
    box.append(unclaimed);
  }
  const target = byId('settle-claims');
  if (!report.claims.length) {
    target.replaceChildren(el('p', '当前没有认领记录', 'empty'));
  } else {
    table(target, [
      ['编号', 'claim_no', 'num'], ['档口', 'stall'], ['份数', 'portions', 'num'],
      ['状态', row => statusTag(row.status)], ['登记 UTC', 'changed'],
      ['操作', row => {
        if (row.status !== 'confirmed' || report.closed_at) return el('span', '—');
        const button = el('button', '冲销', 'btn');
        button.type = 'button';
        button.addEventListener('click', async () => {
          button.disabled = true;
          try {
            await query(`/api/settle/receipts/${report.receipt_id}/claims/${row.claim_no}/reverse`, {});
            flash(`已冲销认领 #${row.claim_no}，退回 ${row.portions} 份`);
            await load(report.receipt_id);
          } catch (error) { flash(error.message, true); }
          finally { button.disabled = false; }
        });
        return button;
      }],
    ], report.claims);
  }
  const readOnly = Boolean(report.closed_at);
  for (const control of byId('claim-form').querySelectorAll('input,button')) control.disabled = readOnly;
  byId('close-receipt').disabled = readOnly;
}

async function load(receiptId) {
  render(await query(`/api/settle/receipts/${encodeURIComponent(receiptId)}`));
}

function selectedTab() {
  return Object.hasOwn(settings.tabs, location.hash.slice(1)) ? location.hash.slice(1) : 'domain';
}

function toggle() {
  const isSettle = selectedTab() === 'settle';
  settlePanel.hidden = !isSettle;
  mainGrid.hidden = isSettle;
}

byId('receipt-form').addEventListener('submit', async event => {
  event.preventDefault();
  try {
    const report = await query('/api/settle/receipts', {
      receipt_id: byId('receipt-id').value.trim(),
      stall: byId('receipt-stall').value.trim(),
      total_portions: Number(byId('receipt-total').value),
    });
    byId('lookup-id').value = report.receipt_id;
    flash('回执已登记');
    render(report);
  } catch (error) { flash(error.message, true); }
});

byId('lookup-form').addEventListener('submit', async event => {
  event.preventDefault();
  try { await load(byId('lookup-id').value.trim()); flash(''); }
  catch (error) { flash(error.message, true); }
});

byId('claim-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (!current) { flash('请先载入回执', true); return; }
  try {
    const result = await query(`/api/settle/receipts/${current.receipt_id}/claims`, {
      stall: byId('claim-stall').value.trim(),
      portions: Number(byId('claim-portions').value),
    });
    flash(`认领 #${result.claim_no} 已确认，回执剩余 ${result.remaining_portions} 份`);
    await load(current.receipt_id);
  } catch (error) { flash(error.message, true); }
});

byId('close-receipt').addEventListener('click', async () => {
  if (!current) { flash('请先载入回执', true); return; }
  try {
    const report = await query(`/api/settle/receipts/${current.receipt_id}/close`, {});
    flash(report.fully_settled
      ? '关账完成：回执份数全部已结'
      : `关账完成：未认领 ${report.unclaimed_portions} 份，未结 ${report.unsettled_portions} 份`, true);
    render(report);
  } catch (error) { flash(error.message, true); }
});

window.addEventListener('hashchange', toggle);
toggle();
