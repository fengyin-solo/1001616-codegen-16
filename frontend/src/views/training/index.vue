<template>
  <section class="page" data-module="training">
    <header class="page-head">
      <div>
        <h2>资质培训管理</h2>
        <p class="page-desc">维护培训记录，围绕培训编号、培训主题、培训对象、授课人员做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记培训记录</button>
        <button class="btn" type="button" @click="exportRows">导出资质培训清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ displayCell(row, column) }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无资质培训数据，可先登记培训记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条资质培训记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <section class="ledger-panel">
      <header class="ledger-head">
        <div>
          <h3>成绩分档台账</h3>
          <p class="page-desc">
            分档口径：合格 {{ thresholds['合格'] }} 分，待补训 {{ thresholds['待补训'] }} 分，不合格 {{ thresholds['不合格'] }} 分；
            同一培训编号重复收尾以最后一次成绩为准，已取消的培训不计入。
          </p>
        </div>
        <button class="btn primary" type="button" :disabled="!ledger?.retraining_total" @click="saveRetrainingFile">
          另存补训名单（{{ ledger?.retraining_total ?? 0 }} 人）
        </button>
      </header>

      <div class="stat-row">
        <article class="stat-card">
          <span class="stat-label">有效结班培训</span>
          <strong class="stat-value">{{ ledger?.结班数 ?? 0 }}</strong>
        </article>
        <article v-for="tier in tiers" :key="tier" class="stat-card">
          <span class="stat-label">{{ tier }}人数</span>
          <strong class="stat-value" :class="`tier-text-${tier}`">{{ ledger?.totals[tier] ?? 0 }}</strong>
        </article>
        <article class="stat-card">
          <span class="stat-label">参训总人数</span>
          <strong class="stat-value">{{ ledger?.总人数 ?? 0 }}</strong>
        </article>
      </div>

      <!-- 图表视图：各档人数 -->
      <div class="chart-card">
        <h4>各档人数</h4>
        <div class="bar-chart">
          <div v-for="tier in tiers" :key="tier" class="bar-col">
            <span class="bar-count">{{ ledger?.totals[tier] ?? 0 }}</span>
            <div class="bar-track">
              <div class="bar-fill" :class="`tier-bg-${tier}`" :style="{ height: `${barHeight(ledger?.totals[tier] ?? 0)}%` }"></div>
            </div>
            <span class="bar-label">{{ tier }}</span>
          </div>
        </div>
      </div>

      <div class="ledger-grid">
        <div class="ledger-block">
          <h4>培训分档明细</h4>
          <table class="data-table ledger-table">
            <thead>
              <tr>
                <th>培训编号</th>
                <th>培训主题</th>
                <th>分档结果</th>
                <th>状态</th>
                <th>人员明细</th>
              </tr>
            </thead>
            <tbody>
              <template v-for="item in ledgerItems" :key="String(item.id)">
                <tr :class="{ 'row-muted': !item.有效 }">
                  <td>{{ item.培训编号 }}</td>
                  <td>{{ item.培训主题 }}</td>
                  <td>{{ item.分档结果 }}</td>
                  <td>
                    <span v-if="item.已取消" class="tag tag-cancel">已取消，不计入</span>
                    <span v-else-if="item.已覆盖" class="tag tag-superseded">已被新收尾覆盖</span>
                    <span v-else class="tag tag-ok">计入台账</span>
                  </td>
                  <td>
                    <button class="link" type="button" @click="toggleExpand(item.id)">
                      {{ expandedIds.has(item.id) ? '收起明细' : `查看 ${item.人员.length} 人` }}
                    </button>
                  </td>
                </tr>
                <tr v-if="expandedIds.has(item.id)">
                  <td colspan="5" class="detail-cell">
                    <span v-for="person in item.人员" :key="person.姓名" class="tier-chip" :class="`tier-bg-chip-${person.档位}`">
                      {{ person.姓名 }} {{ formatScore(person.成绩) }} 分 · {{ person.档位 }}
                    </span>
                  </td>
                </tr>
              </template>
              <tr v-if="!ledgerItems.length">
                <td colspan="5" class="empty-state">还没有已结班的培训，确认结班并录入成绩后这里生成台账</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div class="ledger-block">
          <h4>补训名单（按培训主题归拢）</h4>
          <div v-if="retrainingGroups.length" class="retrain-list">
            <section v-for="group in retrainingGroups" :key="group.培训主题" class="retrain-group">
              <header class="retrain-group-head">
                <strong>{{ group.培训主题 }}</strong>
                <span class="tag tag-retrain">{{ group.人数 }} 人</span>
              </header>
              <ul>
                <li v-for="person in group.人员" :key="`${person.培训编号}-${person.姓名}`">
                  <span>{{ person.姓名 }}</span>
                  <span class="muted">{{ person.培训编号 }} · {{ formatScore(person.成绩) }} 分</span>
                </li>
              </ul>
            </section>
          </div>
          <p v-else class="empty-state retrain-empty">当前没有待补训人员</p>
        </div>
      </div>
    </section>

    <!-- 确认结班：逐人录入考核成绩 -->
    <div v-if="closeTarget" class="modal-mask" @click.self="closeDialog">
      <div class="modal-card" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>确认结班 · 录入考核成绩</h3>
          <button class="link" type="button" @click="closeDialog">关闭</button>
        </header>
        <p class="page-desc">
          {{ closeTarget.培训编号 }}｜{{ closeTarget.培训主题 }}
          成绩须在 0 到 100 之间，缺填或越界本次收尾不予通过。
        </p>
        <table class="data-table roster-table">
          <thead>
            <tr><th style="width:40%">姓名</th><th style="width:40%">考核成绩</th><th style="width:20%">操作</th></tr>
          </thead>
          <tbody>
            <tr v-for="(entry, index) in rosterEntries" :key="index">
              <td><input v-model="entry.姓名" placeholder="人员姓名" /></td>
              <td><input v-model="entry.成绩" inputmode="decimal" placeholder="0-100" /></td>
              <td>
                <button class="link danger" type="button" :disabled="rosterEntries.length === 1" @click="rosterEntries.splice(index, 1)">
                  移除
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <div class="roster-toolbar">
          <button class="btn" type="button" @click="rosterEntries.push({ 姓名: '', 成绩: '' })">增加人员</button>
        </div>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <footer class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitClose">
            {{ submitting ? '提交中…' : '确认结班并分档' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>
type Tier = '合格' | '待补训' | '不合格'

interface RosterEntry {
  姓名: string
  成绩: string
  档位: Tier
}

interface LedgerItem {
  id: number
  seq: number
  培训编号: string
  培训主题: string
  培训日期: string | null
  状态: string
  汇总: Record<Tier, number>
  分档结果: string
  人员: Array<{ 姓名: string; 成绩: number; 档位: Tier }>
  有效: boolean
  已取消: boolean
  已覆盖: boolean
}

interface RetrainGroup {
  培训主题: string
  人数: number
  人员: Array<{ 培训编号: string; 姓名: string; 成绩: number }>
}

interface GradeLedger {
  thresholds: Record<Tier, string>
  totals: Record<Tier, number>
  总人数: number
  结班数: number
  items: LedgerItem[]
  retraining_groups: RetrainGroup[]
  retraining_total: number
}

const ENDPOINT = '/api/training'
const baseColumns = ['培训编号', '培训主题', '培训对象', '授课人员', '培训课时', '考核成绩', '培训日期', '培训状态']
const tierColumn = '分档结果'
const columns = [...baseColumns.slice(0, 6), tierColumn, ...baseColumns.slice(6)]
const actions = ['开班登记', '确认结班', '取消培训']
const tiers: Tier[] = ['合格', '待补训', '不合格']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = baseColumns.slice(0, 3)

const ledger = ref<GradeLedger | null>(null)
const expandedIds = ref<Set<number>>(new Set())

const closeTarget = ref<Row | null>(null)
const rosterEntries = ref<Array<{ 姓名: string; 成绩: string }>>([])
const dialogError = ref('')
const submitting = ref(false)

const thresholds = computed<Record<Tier, string>>(() => ledger.value?.thresholds ?? { 合格: '80-100', 待补训: '60-79', 不合格: '0-59' })
const ledgerItems = computed(() => ledger.value?.items ?? [])
const retrainingGroups = computed(() => ledger.value?.retraining_groups ?? [])

const stats = computed(() => {
  const waiting = rows.value.filter((row) => row.status === '待开班').length
  const currentMonth = String(new Date().toISOString().slice(0, 7))
  const monthClosed = ledgerItems.value.filter((item) => item.有效 && String(item.培训日期 ?? '').startsWith(currentMonth)).length
  return [
    { label: '待开班培训', value: waiting },
    { label: '本月结班数', value: monthClosed },
    { label: '考核未通过', value: ledger.value?.totals['不合格'] ?? 0 },
  ]
})

// 分档结果列直接取台账接口的数据，保证表格与台账、补训名单同一口径
const tierCellMap = computed<Map<number, { text: string; muted: boolean }>>(() => {
  const map = new Map<number, { text: string; muted: boolean }>()
  for (const item of ledgerItems.value) {
    if (item.已取消) {
      map.set(item.id, { text: '已取消，不计入台账', muted: true })
    } else if (item.已覆盖) {
      map.set(item.id, { text: '已被同编号新收尾覆盖', muted: true })
    } else {
      map.set(item.id, { text: item.分档结果, muted: false })
    }
  }
  return map
})

function displayCell(row: Row, column: string): string {
  if (column === tierColumn) {
    const cell = tierCellMap.value.get(Number(row.id))
    return cell ? cell.text : '—'
  }
  const value = row[column]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function barHeight(count: number): number {
  const max = Math.max(1, ...tiers.map((tier) => ledger.value?.totals[tier] ?? 0))
  return Math.max(count === 0 ? 0 : 12, Math.round((count / max) * 100))
}

function formatScore(score: number): string {
  return Number.isInteger(score) ? String(score) : String(Number(score.toFixed(1)))
}

function toggleExpand(id: number) {
  if (expandedIds.value.has(id)) {
    expandedIds.value.delete(id)
  } else {
    expandedIds.value.add(id)
  }
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function saveRetrainingFile() {
  // 同源走 vite 代理，浏览器直接下载为本地文件
  const anchor = document.createElement('a')
  anchor.href = `${ENDPOINT}/retraining/export`
  anchor.download = '补训名单.csv'
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
}

function openCreate() {
  errorMessage.value = '培训记录登记入口尚未接入审批流'
}

async function runAction(action: string, row: Row) {
  if (action === '确认结班') {
    await openCloseDialog(row)
    return
  }
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '资质培训动作未生效，请稍后重试')
    }
    successMessage.value = payload.message
    await Promise.all([reload(), loadLedger()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资质培训操作失败'
  }
}

function splitAudience(text: string): string[] {
  return text.split(/[，,、;；/\s]+/).map((name) => name.trim()).filter(Boolean)
}

async function openCloseDialog(row: Row) {
  dialogError.value = ''
  closeTarget.value = row
  rosterEntries.value = []
  try {
    const response = await request(`${ENDPOINT}/${row.id}`)
    if (!response.ok) {
      throw new Error('培训记录明细读取失败')
    }
    const detail = await response.json()
    const people = detail?.['成绩台账']?.['人员'] as RosterEntry[] | undefined
    if (Array.isArray(people) && people.length) {
      // 重复收尾时带出上一次（当前最后一次）成绩，方便改分
      rosterEntries.value = people.map((person) => ({
        姓名: String(person.姓名 ?? ''),
        成绩: formatScore(Number(person.成绩)),
      }))
    } else {
      rosterEntries.value = splitAudience(String(row['培训对象'] ?? '')).map((name) => ({ 姓名: name, 成绩: '' }))
    }
    if (!rosterEntries.value.length) {
      rosterEntries.value.push({ 姓名: '', 成绩: '' })
    }
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '培训记录明细读取失败'
  }
}

function closeDialog() {
  if (submitting.value) {
    return
  }
  closeTarget.value = null
  rosterEntries.value = []
  dialogError.value = ''
}

async function submitClose() {
  if (!closeTarget.value) {
    return
  }
  dialogError.value = ''
  const 人员成绩 = rosterEntries.value.map((entry) => ({
    姓名: entry.姓名.trim(),
    成绩: entry.成绩.trim(),
  }))
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${closeTarget.value.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '确认结班', 人员成绩 } }),
    })
    const payload = await response.json().catch(() => null)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? '结班未生效，请稍后重试')
    }
    const message = String(payload.message ?? '培训记录已确认结班')
    closeTarget.value = null
    rosterEntries.value = []
    await Promise.all([reload(), loadLedger()])
    successMessage.value = message
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '确认结班失败'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?size=200&${query}`)
    if (!response.ok) {
      throw new Error('培训记录列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资质培训列表读取失败'
  }
}

async function loadLedger() {
  try {
    const response = await request(`${ENDPOINT}/grade-ledger`)
    if (!response.ok) {
      throw new Error('成绩分档台账读取失败')
    }
    ledger.value = (await response.json()) as GradeLedger
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '成绩分档台账读取失败'
  }
}

onMounted(() => {
  void reload()
  void loadLedger()
})
</script>

<style scoped>
.success-text { color: #067647; }
.muted { color: var(--muted); font-size: 12px; }

.ledger-panel {
  margin-top: 20px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 14px 16px;
}
.ledger-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.ledger-head h3, .ledger-block h4, .chart-card h4 { margin: 0 0 4px; }
.ledger-head .btn[disabled] { opacity: 0.5; cursor: not-allowed; }

.chart-card { border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; margin: 12px 0; }
.bar-chart { display: flex; align-items: flex-end; gap: 32px; height: 180px; padding: 12px 8px 0; }
.bar-col { flex: 0 0 120px; display: flex; flex-direction: column; align-items: center; height: 100%; }
.bar-count { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
.bar-track { flex: 1; width: 56px; display: flex; align-items: flex-end; background: #f1f5f9; border-radius: 6px 6px 0 0; overflow: hidden; }
.bar-fill { width: 100%; border-radius: 6px 6px 0 0; transition: height 0.25s ease; min-height: 0; }
.bar-label { font-size: 12px; color: var(--muted); margin-top: 6px; }

.tier-bg-合格 { background: #12b76a; }
.tier-bg-待补训 { background: #f79009; }
.tier-bg-不合格 { background: #f04438; }
.tier-text-合格 { color: #067647; }
.tier-text-待补训 { color: #b54708; }
.tier-text-不合格 { color: #b42318; }

.ledger-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-top: 12px; }
.ledger-block { min-width: 0; }
.ledger-table { margin-top: 6px; }
.row-muted { color: var(--muted); }
.detail-cell { background: #f8fafc; }
.tier-chip { display: inline-block; font-size: 12px; border-radius: 999px; padding: 2px 10px; margin: 2px 6px 2px 0; border: 1px solid var(--border); background: #fff; }
.tier-bg-chip-合格 { border-color: #a6f4c5; }
.tier-bg-chip-待补训 { border-color: #fdb022; }
.tier-bg-chip-不合格 { border-color: #fda29b; }

.tag { display: inline-block; font-size: 12px; border-radius: 4px; padding: 1px 8px; }
.tag-ok { background: #ecfdf3; color: #067647; }
.tag-retrain { background: #fffaeb; color: #b54708; }
.tag-cancel { background: #f2f4f7; color: var(--muted); }
.tag-superseded { background: #fffaeb; color: #b54708; }

.retrain-list { display: flex; flex-direction: column; gap: 10px; margin-top: 6px; max-height: 420px; overflow-y: auto; }
.retrain-group { border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; }
.retrain-group-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
.retrain-group ul { list-style: none; margin: 0; padding: 0; }
.retrain-group li { display: flex; justify-content: space-between; font-size: 13px; padding: 3px 0; border-top: 1px dashed var(--border); }
.retrain-empty { padding: 24px 0; }

.modal-mask { position: fixed; inset: 0; background: rgba(16, 24, 40, 0.45); display: flex; align-items: center; justify-content: center; z-index: 20; }
.modal-card { width: 560px; max-height: 86vh; overflow-y: auto; background: #fff; border-radius: 10px; padding: 16px 20px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; }
.modal-head h3 { margin: 0; font-size: 16px; }
.roster-table { margin-top: 10px; }
.roster-table input { width: 100%; border: 1px solid var(--border); border-radius: 4px; padding: 5px 8px; font-size: 13px; }
.roster-toolbar { margin-top: 8px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.link.danger { color: #b42318; }
.link:disabled { color: var(--muted); cursor: not-allowed; }
</style>
