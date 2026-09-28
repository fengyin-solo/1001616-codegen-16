<template>
  <section class="page" data-module="training">
    <header class="page-head">
      <div>
        <h2>资质培训管理</h2>
        <p class="page-desc">维护培训记录，围绕培训编号、培训主题、培训对象、授课人员做登记、筛选与状态流转；课程收尾时按考核成绩生成合格、待补训、不合格三档台账。</p>
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
          <th>成绩分档</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] === '' || row[column] == null ? '—' : row[column] }}</td>
          <td>
            <span v-if="countsOf(row)" class="tier-chips">
              <span v-for="tier in tierOrder" :key="tier" class="chip" :class="chipClass(tier)">
                {{ tier }} {{ countsOf(row)?.[tier] ?? 0 }}
              </span>
            </span>
            <span v-else class="muted">未收尾</span>
          </td>
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
          <td :colspan="columns.length + 2" class="empty-state">暂无资质培训数据，可先登记培训记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条资质培训记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <!-- 成绩分档台账：图表人数与补训名单同处呈现，数字同源于后端台账 -->
    <section class="ledger-panel">
      <header class="ledger-head">
        <div>
          <h3>成绩分档台账</h3>
          <p class="page-desc">{{ ledger?.rule }}</p>
        </div>
        <button class="btn primary" type="button" :disabled="!ledger || ledger.remedial_total === 0" @click="exportRemedial">
          补训名单另存为文件（{{ ledger?.remedial_total ?? 0 }} 人）
        </button>
      </header>

      <div v-if="ledger" class="ledger-grid">
        <article class="card chart-card">
          <h4>各档人数（图表视图）</h4>
          <div class="bars">
            <div v-for="tier in ledger.tier_order" :key="tier" class="bar-col">
              <div class="bar-track">
                <div
                  class="bar-fill"
                  :style="{ height: overallBarHeight(tier), background: ledger.tier_colors[tier] }"
                ></div>
              </div>
              <strong class="bar-value">{{ ledger.totals[tier] }}</strong>
              <span class="bar-name">{{ tier }}</span>
            </div>
          </div>
          <p class="muted">参与分档共 {{ ledger.total_people }} 人次；合计 {{ ledger.total_people }} 人。</p>

          <h4 class="chart-sub">各培训分档构成</h4>
          <div class="stack-list">
            <div v-for="item in ledger.ledgers" :key="item.id" class="stack-row">
              <div class="stack-meta">
                <span class="stack-code">{{ item.培训编号 }}</span>
                <span class="muted">{{ item.培训主题 }}</span>
              </div>
              <div class="stack-track">
                <div
                  v-for="tier in ledger.tier_order"
                  :key="tier"
                  class="stack-seg"
                  :style="{ width: segmentPercent(item, tier), background: ledger.tier_colors[tier] }"
                  :title="`${tier} ${item.分档结果[tier]} 人`"
                ></div>
              </div>
              <span class="stack-counts">
                <span v-for="tier in ledger.tier_order" :key="tier">{{ tier }} {{ item.分档结果[tier] }}</span>
              </span>
            </div>
            <p v-if="!ledger.ledgers.length" class="muted">尚无已收尾培训，结班后这里会出现分档图表。</p>
          </div>
        </article>

        <article class="card remedial-card">
          <h4>待补训名单（按培训主题归拢）</h4>
          <div v-for="group in ledger.remedial_groups" :key="group.培训主题" class="remedial-group">
            <div class="remedial-title">
              <strong>{{ group.培训主题 }}</strong>
              <span class="muted">{{ group.人数 }} 人</span>
            </div>
            <table class="mini-table">
              <thead>
                <tr><th>姓名</th><th>考核成绩</th><th>培训编号</th><th>结班时间</th></tr>
              </thead>
              <tbody>
                <tr v-for="(person, idx) in group.items" :key="`${group.培训主题}-${person.姓名}-${idx}`">
                  <td>{{ person.姓名 }}</td>
                  <td>{{ person.考核成绩 }}</td>
                  <td>{{ person.培训编号 }}</td>
                  <td>{{ person.结班时间 }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p v-if="!ledger.remedial_groups.length" class="muted">当前没有待补训人员。</p>
        </article>
      </div>

      <article v-if="ledger && ledger.ledgers.length" class="card detail-card">
        <h4>分档明细</h4>
        <div v-for="item in ledger.ledgers" :key="`detail-${item.id}`" class="detail-block">
          <div class="detail-title">
            <strong>{{ item.培训编号 }}｜{{ item.培训主题 }}</strong>
            <span class="muted">结班时间 {{ item.结班时间 }}</span>
          </div>
          <table class="mini-table">
            <thead>
              <tr><th>姓名</th><th>考核成绩</th><th>分档</th></tr>
            </thead>
            <tbody>
              <tr v-for="member in item.人员明细" :key="`${item.id}-${member.姓名}`">
                <td>{{ member.姓名 }}</td>
                <td>{{ member.考核成绩 }}</td>
                <td><span class="chip" :class="chipClass(member.分档)">{{ member.分档 }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </section>

    <!-- 结班成绩录入弹窗 -->
    <div v-if="dialogOpen" class="modal-mask" @click.self="closeDialog">
      <div class="modal" role="dialog" aria-modal="true">
        <header class="modal-head">
          <h3>确认结班 · 录入考核成绩</h3>
          <button class="link" type="button" @click="closeDialog">关闭</button>
        </header>
        <p class="muted">
          {{ dialogRow?.培训编号 }}｜{{ dialogRow?.培训主题 }}<br />
          分数须为 0 到 100 之间的数字；有一项不合规本次收尾将被驳回。同一培训编号重复收尾时以最后一次成绩为准。
        </p>
        <table class="mini-table score-table">
          <thead>
            <tr><th>人员姓名</th><th>考核成绩</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="(scoreRow, index) in scoreRows" :key="index">
              <td>
                <input v-model="scoreRow.姓名" placeholder="如：张三" />
              </td>
              <td>
                <input v-model="scoreRow.考核成绩" inputmode="decimal" placeholder="0-100" />
              </td>
              <td>
                <button class="link danger" type="button" @click="removeScoreRow(index)">移除</button>
              </td>
            </tr>
          </tbody>
        </table>
        <button class="btn ghost" type="button" @click="addScoreRow">+ 增加一名人员</button>
        <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
        <footer class="modal-foot">
          <button class="btn" type="button" @click="closeDialog">取消</button>
          <button class="btn primary" type="button" :disabled="submitting" @click="submitClose">
            {{ submitting ? '提交中…' : '确认结班' }}
          </button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type TierName = '合格' | '待补训' | '不合格'
type Counts = Record<TierName, number>
type Row = Record<string, string | number | null>

interface MemberDetail {
  姓名: string
  考核成绩: number
  分档: TierName
}
interface LedgerItem {
  id: number
  培训编号: string
  培训主题: string
  结班时间: string
  人员明细: MemberDetail[]
  分档结果: Counts
}
interface RemedialPerson {
  培训编号: string
  姓名: string
  考核成绩: number
  结班时间: string
}
interface RemedialGroup {
  培训主题: string
  人数: number
  items: RemedialPerson[]
}
interface LedgerView {
  rule: string
  ledgers: LedgerItem[]
  totals: Counts
  total_people: number
  remedial_groups: RemedialGroup[]
  remedial_total: number
  tier_order: TierName[]
  tier_colors: Record<TierName, string>
}
interface ScoreRow {
  姓名: string
  考核成绩: string
}

const ENDPOINT = '/api/training'
const columns = ['培训编号', '培训主题', '培训对象', '授课人员', '培训课时', '考核成绩', '培训日期', '培训状态']
const actions = ['开班登记', '确认结班', '取消培训']
const tierOrder: TierName[] = ['合格', '待补训', '不合格']

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)
const ledger = ref<LedgerView | null>(null)

const dialogOpen = ref(false)
const dialogRow = ref<Row | null>(null)
const scoreRows = ref<ScoreRow[]>([])
const dialogError = ref('')
const submitting = ref(false)

const stats = computed(() => [
  { label: '待开班培训', value: rows.value.filter((row) => row.status === '待开班').length },
  { label: '本月结班数', value: rows.value.filter((row) => String(row.结班时间 ?? '').startsWith(currentMonth())).length },
  { label: '考核未通过', value: ledger.value?.totals['不合格'] ?? 0 },
])

function currentMonth(): string {
  const now = new Date()
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

function countsOf(row: Row): Counts | null {
  const counts = row.成绩分档
  return counts && typeof counts === 'object' ? (counts as Counts) : null
}

function chipClass(tier: string): string {
  return { 合格: 'chip-pass', 待补训: 'chip-remedial', 不合格: 'chip-fail' }[tier] ?? ''
}

function overallBarHeight(tier: TierName): string {
  const totalPeople = ledger.value?.total_people ?? 0
  const value = ledger.value?.totals[tier] ?? 0
  if (!totalPeople || !value) return '0%'
  return `${Math.max((value / totalPeople) * 100, 4)}%`
}

function segmentPercent(item: LedgerItem, tier: TierName): string {
  const totalPeople = item.人员明细.length
  if (!totalPeople) return '0%'
  return `${(item.分档结果[tier] / totalPeople) * 100}%`
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function exportRemedial() {
  window.open(`${ENDPOINT}/remedial-export`, '_blank')
}

function openCreate() {
  errorMessage.value = '培训记录登记入口尚未接入审批流'
}

function addScoreRow() {
  scoreRows.value.push({ 姓名: '', 考核成绩: '' })
}

function removeScoreRow(index: number) {
  scoreRows.value.splice(index, 1)
}

function closeDialog() {
  dialogOpen.value = false
  dialogRow.value = null
  scoreRows.value = []
  dialogError.value = ''
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  if (action === '确认结班') {
    dialogRow.value = row
    const previous = Array.isArray(row.成绩明细) ? (row.成绩明细 as Array<Record<string, unknown>>) : []
    scoreRows.value = previous.length
      ? previous.map((member) => ({
          姓名: String(member.姓名 ?? ''),
          考核成绩: String(member.考核成绩 ?? ''),
        }))
      : [{ 姓名: '', 考核成绩: '' }, { 姓名: '', 考核成绩: '' }, { 姓名: '', 考核成绩: '' }]
    dialogError.value = ''
    dialogOpen.value = true
    return
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    if (!response.ok) {
      throw new Error('资质培训动作未生效，请稍后重试')
    }
    const payload = await response.json()
    if (payload.ok === false) {
      errorMessage.value = payload.message ?? '资质培训动作未生效'
    } else {
      successMessage.value = payload.message ?? '操作已生效'
      await reload()
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '资质培训操作失败'
  }
}

function validateScoreRows(): string[] {
  const problems: string[] = []
  scoreRows.value.forEach((scoreRow, index) => {
    const name = scoreRow.姓名.trim()
    const label = name ? `人员「${name}」` : `第 ${index + 1} 行人员`
    if (!name) {
      problems.push(`第 ${index + 1} 行人员姓名未填写`)
    }
    const text = scoreRow.考核成绩.trim()
    if (text === '') {
      problems.push(`${label}的考核成绩未填写`)
      return
    }
    const score = Number(text)
    if (!Number.isFinite(score)) {
      problems.push(`${label}的考核成绩「${text}」无法识别为 0 到 100 之间的分数`)
      return
    }
    if (score < 0 || score > 100) {
      problems.push(`${label}的考核成绩 ${text} 不在 0 到 100 之间`)
    }
  })
  if (!scoreRows.value.length) {
    problems.push('至少需要一名人员的考核成绩才能结班')
  }
  return problems
}

async function submitClose() {
  dialogError.value = ''
  const problems = validateScoreRows()
  if (problems.length) {
    dialogError.value = `本次收尾不予通过：${problems.join('；')}`
    return
  }
  submitting.value = true
  try {
    const response = await request(`${ENDPOINT}/${dialogRow.value?.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({
        values: {
          action: '确认结班',
          成绩明细: scoreRows.value.map((scoreRow) => ({
            姓名: scoreRow.姓名.trim(),
            考核成绩: Number(scoreRow.考核成绩.trim()),
          })),
        },
      }),
    })
    if (!response.ok) {
      throw new Error('结班请求未送达，请稍后重试')
    }
    const payload = await response.json()
    if (payload.ok === false) {
      dialogError.value = payload.message ?? '本次收尾不予通过'
      return
    }
    successMessage.value = payload.message ?? '培训记录已确认结班'
    closeDialog()
    await Promise.all([reload(), reloadLedger()])
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '结班操作失败'
  } finally {
    submitting.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
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

async function reloadLedger() {
  try {
    const response = await request(`${ENDPOINT}/ledger`)
    if (!response.ok) {
      throw new Error('成绩分档台账读取失败')
    }
    ledger.value = (await response.json()) as LedgerView
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '成绩分档台账读取失败'
  }
}

onMounted(() => {
  void reload()
  void reloadLedger()
})
</script>

<style scoped>
.muted { color: var(--muted); font-size: 12px; }
.success-text { color: #15803d; }

.tier-chips { display: inline-flex; gap: 4px; flex-wrap: wrap; }
.chip { display: inline-block; border-radius: 10px; padding: 1px 8px; font-size: 12px; color: #fff; white-space: nowrap; }
.chip-pass { background: #16a34a; }
.chip-remedial { background: #d97706; }
.chip-fail { background: #dc2626; }

.ledger-panel { margin-top: 20px; }
.ledger-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.ledger-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 12px; margin-top: 10px; }
.card { background: #fff; border: 1px solid var(--border); border-radius: 8px; padding: 12px 14px; margin: 0; }
.card h4 { margin: 0 0 10px; font-size: 14px; }
.chart-sub { margin-top: 14px; }

.bars { display: flex; gap: 18px; align-items: flex-end; height: 180px; padding: 0 8px; }
.bar-col { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: flex-end; height: 100%; }
.bar-track { width: 56px; height: 140px; background: #eef2f7; border-radius: 6px 6px 0 0; display: flex; align-items: flex-end; overflow: hidden; }
.bar-fill { width: 100%; border-radius: 6px 6px 0 0; transition: height .2s ease; min-height: 0; }
.bar-value { margin-top: 6px; font-size: 16px; }
.bar-name { font-size: 12px; color: var(--muted); }

.stack-list { display: flex; flex-direction: column; gap: 8px; }
.stack-row { display: grid; grid-template-columns: 200px 1fr auto; gap: 10px; align-items: center; font-size: 12px; }
.stack-meta { display: flex; flex-direction: column; gap: 2px; }
.stack-code { font-weight: 600; }
.stack-track { display: flex; height: 14px; border-radius: 7px; overflow: hidden; background: #eef2f7; }
.stack-seg { height: 100%; }
.stack-counts { display: flex; gap: 8px; color: var(--muted); white-space: nowrap; }

.remedial-group { margin-bottom: 12px; }
.remedial-title { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px; }

.mini-table { width: 100%; border-collapse: collapse; }
.mini-table th, .mini-table td { border: 1px solid var(--border); padding: 5px 8px; font-size: 12px; text-align: left; }
.score-table input { width: 100%; padding: 4px 6px; border: 1px solid var(--border); border-radius: 4px; font: inherit; }

.detail-card { margin-top: 12px; }
.detail-block { margin-bottom: 14px; }
.detail-title { display: flex; justify-content: space-between; margin-bottom: 4px; font-size: 13px; }

.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, .45); display: flex; align-items: center; justify-content: center; z-index: 20; }
.modal { width: 560px; max-width: calc(100vw - 32px); max-height: 86vh; overflow: auto; background: #fff; border-radius: 10px; padding: 16px 18px; }
.modal-head { display: flex; justify-content: space-between; align-items: center; }
.modal-head h3 { margin: 0; font-size: 16px; }
.modal-foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 14px; }
.link.danger { color: #b42318; }

@media (max-width: 960px) {
  .ledger-grid { grid-template-columns: 1fr; }
  .stack-row { grid-template-columns: 1fr; }
}
</style>
