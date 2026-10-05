<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import api from '../services/api'
import { useSessionStore } from '../stores/session'

interface Department { id: number; code: string; name: string; name_zh: string }
interface PermissionGroup { id: number; name: string }
interface Person { id: number; username: string; display_name: string; role?: string; department?: Department }
interface PackingList { id: number; order_no: string; machine_type: string; file: string; status: string; created_at: string; uploader: Person; current_node?: string; flow_status?: string }
interface ApprovalNode { id: number; stage: string; handler: Person | null; actual_handler: Person | null; status: string; comment: string; reject_to: string; created_at: string; approved_at: string | null }
interface Flow { id: number; current_node: string; status: string; packing_list: PackingList; nodes: ApprovalNode[]; label_application: { is_new_model: boolean; form_data: Record<string, unknown> } | null }
interface Task extends ApprovalNode { flow_id: number; order_no: string; machine_type: string }

const { t, locale } = useI18n()
const session = useSessionStore()
const route = useRoute()
const departments = ref<Department[]>([])
const managedUsers = ref<Person[]>([])
const permissionGroups = ref<PermissionGroup[]>([])
const supervisorOptions = ref<Person[]>([])
const people = ref<Person[]>([])
const directReports = ref<Person[]>([])
const packingLists = ref<PackingList[]>([])
const tasks = ref<Task[]>([])
const loading = ref(true)
const activeTab = ref<'overview' | 'packing' | 'tasks' | 'admin'>('overview')
const statusFilter = ref('')
const departmentFilter = ref<number | ''>('')
const departmentScope = ref(false)
const uploadVisible = ref(false)
const uploadBusy = ref(false)
const selectedFile = ref<File | null>(null)
const uploadForm = reactive({ order_no: '', machine_type: '', label_handler_id: '' as string | number })
const detailVisible = ref(false)
const flow = ref<Flow | null>(null)
const detailBusy = ref(false)
const nextHandlerId = ref<number | string>('')
const comment = ref('')
const applicationData = ref('')
const newModel = ref(false)
const delegating = ref(false)
const actingFor = ref<number | string>('')
const rejectVisible = ref(false)
const rejectTo = ref('')
const rejectReason = ref('')
const actionBusy = ref(false)
const userDialogVisible = ref(false)
const departmentDialogVisible = ref(false)
const editingDepartment = ref<number | null>(null)
const userForm = reactive({ username: '', password: '', display_name: '', email: '', department_id: '' as number | '', role: 'supervisor', supervisor_id: '' as number | '', groups: [] as number[] })
const departmentForm = reactive({ name: '', name_zh: '', code: '' })

const isSupervisor = computed(() => session.user?.role === 'supervisor')
const canUpload = computed(() => isAdmin.value || ['business', 'biz'].includes(departmentCode.value))
const currentPendingNode = computed(() => flow.value?.nodes.find(
  (node) => node.stage === flow.value?.current_node && node.status === 'pending',
) || null)
const canActOnCurrentNode = computed(() => {
  const node = currentPendingNode.value
  if (!node || !session.user) return false
  if (session.user.is_staff || node.handler?.id === session.user.id) return true
  return session.user.role === 'supervisor'
    && node.handler?.department?.id === session.user.department?.id
})
const availableReturnStages = computed(() => {
  const seen = new Set<string>()
  return (flow.value?.nodes || []).filter((node) => {
    if (node.status !== 'approved' || seen.has(node.stage)) return false
    seen.add(node.stage)
    return true
  })
})
const activeFlows = computed(() => packingLists.value.filter((item) => !['completed', 'rejected'].includes(item.status)).length)
const completedFlows = computed(() => packingLists.value.filter((item) => item.status === 'completed').length)
const departmentCode = computed(() => session.user?.department?.code.toLowerCase() || '')
const isAdmin = computed(() => Boolean(session.user?.is_staff))

function departmentId(code: string) {
  const aliases: Record<string, string[]> = {
    label: ['label', 'label_room'],
    engineering: ['engineering', 'eng'],
    qc: ['qc'],
    ie: ['ie'],
  }
  return departments.value.find((department) => aliases[code]?.includes(department.code.toLowerCase()))?.id
}

function normalizeStageDepartment(stage: string) {
  if (stage === 'label_apply' || stage === 'label_close') return 'label'
  if (stage === 'eng') return 'engineering'
  if (stage === 'qc') return 'qc'
  return 'ie'
}

function departmentLabel(code?: string) {
  const normalized = code?.toLowerCase() || ''
  const aliases: Record<string, string[]> = {
    business: ['business', 'biz'],
    label: ['label', 'label_room'],
    eng: ['eng', 'engineering'],
    qc: ['qc'],
    ie: ['ie'],
  }
  const department = departments.value.find((item) => aliases[normalized]?.includes(item.code.toLowerCase()))
  if (department) return locale.value === 'zh' ? department.name_zh : department.name
  return t(`department.${aliases[normalized] ? normalized : 'business'}`)
}

function statusLabel(value: string) {
  const statuses = ['pending', 'processing', 'closing', 'completed', 'rejected']
  return t(`flowStatus.${statuses.includes(value) ? value : 'pending'}`)
}

function nodeStatusLabel(value: string) {
  const statuses = ['pending', 'approved', 'rejected']
  return t(`approvalStatus.${statuses.includes(value) ? value : 'pending'}`)
}

function stageLabel(stage: string) {
  const stages = ['label_apply', 'eng', 'qc', 'ie', 'label_close']
  return t(`stage.${stages.includes(stage) ? stage : 'label_apply'}`)
}

function userName(person?: Person | null) {
  return person?.display_name || person?.username || '—'
}

function openListRow(row: PackingList) {
  openFlow(row.id)
}

function errorMessage(error: any) {
  const detail = error?.response?.data
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const firstValue = Object.values(detail)[0]
    if (Array.isArray(firstValue)) return String(firstValue[0])
    if (typeof firstValue === 'string') return firstValue
  }
  return t('errors.generic')
}

async function loadUsers(departmentCodeValue: string, supervisorId?: number) {
  const id = departmentId(departmentCodeValue)
  if (supervisorId) directReports.value = []
  else people.value = []
  if (!id) return
  const params: Record<string, number> = { department: id }
  if (supervisorId) params.supervisor = supervisorId
  const { data } = await api.get<Person[]>('/users/', { params })
  if (supervisorId) directReports.value = data
  else people.value = data
}

async function loadAdminSupervisors(departmentIdValue: number | '') {
  supervisorOptions.value = []
  if (!departmentIdValue) return
  const { data } = await api.get<Person[]>('/users/', {
    params: { department: departmentIdValue, role: 'supervisor' },
  })
  supervisorOptions.value = data
}

function openUserDialog() {
  Object.assign(userForm, {
    username: '', password: '', display_name: '', email: '', department_id: '',
    role: 'supervisor', supervisor_id: '', groups: [],
  })
  userDialogVisible.value = true
}

async function saveUser() {
  try {
    await api.post('/users/', {
      ...userForm,
      department_id: userForm.department_id,
      supervisor_id: userForm.supervisor_id || null,
    })
    ElMessage.success(t('admin.userCreated'))
    userDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function openDepartmentDialog(department?: Department) {
  editingDepartment.value = department?.id || null
  Object.assign(departmentForm, {
    name: department?.name || '',
    name_zh: department?.name_zh || '',
    code: department?.code || '',
  })
  departmentDialogVisible.value = true
}

async function saveDepartment() {
  try {
    if (editingDepartment.value) {
      await api.put(`/departments/${editingDepartment.value}/`, departmentForm)
    } else {
      await api.post('/departments/', departmentForm)
    }
    ElMessage.success(t('admin.departmentSaved'))
    departmentDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

async function loadData() {
  loading.value = true
  try {
    const departmentRequest = api.get<Department[]>('/departments/')
    const packingParams: Record<string, string | number> = {}
    if (statusFilter.value) packingParams.status = statusFilter.value
    if (departmentFilter.value) packingParams.department = departmentFilter.value
    const packingRequest = api.get<PackingList[]>('/packing-list/', { params: packingParams })
    const taskParams = departmentScope.value && isSupervisor.value ? { scope: 'department' } : {}
    const taskRequest = api.get<Task[]>('/approval/pending/', { params: taskParams })
    const [departmentResponse, packingResponse, taskResponse] = await Promise.all([
      departmentRequest, packingRequest, taskRequest,
    ])
    departments.value = departmentResponse.data
    packingLists.value = packingResponse.data
    tasks.value = taskResponse.data
    if (isAdmin.value) {
      const [usersResponse, groupsResponse] = await Promise.all([
        api.get<Person[]>('/users/'),
        api.get<PermissionGroup[]>('/groups/'),
      ])
      managedUsers.value = usersResponse.data
      permissionGroups.value = groupsResponse.data
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function openUpload() {
  uploadVisible.value = true
  try {
    await loadUsers('label')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
}

function onFileChange(file: UploadFile) {
  selectedFile.value = file.raw || null
}

async function submitUpload() {
  if (!selectedFile.value || !uploadForm.label_handler_id) return
  uploadBusy.value = true
  const body = new FormData()
  body.append('file', selectedFile.value)
  body.append('order_no', uploadForm.order_no)
  body.append('machine_type', uploadForm.machine_type)
  body.append('label_handler_id', String(uploadForm.label_handler_id))
  try {
    await api.post('/packing-list/', body)
    ElMessage.success(t('packing.uploadSuccess'))
    uploadVisible.value = false
    Object.assign(uploadForm, { order_no: '', machine_type: '', label_handler_id: '' })
    selectedFile.value = null
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error) || t('packing.uploadError'))
  } finally {
    uploadBusy.value = false
  }
}

async function openFlow(flowId: number) {
  detailVisible.value = true
  detailBusy.value = true
  flow.value = null
  nextHandlerId.value = ''
  actingFor.value = ''
  delegating.value = false
  comment.value = ''
  try {
    const { data } = await api.get<Flow>(`/approval/flow/${flowId}/`)
    flow.value = data
    newModel.value = data.label_application?.is_new_model || false
    applicationData.value = data.label_application ? JSON.stringify(data.label_application.form_data, null, 2) : ''
    const nextStage = nextStageFor(data.current_node)
    if (nextStage) await loadUsers(normalizeStageDepartment(nextStage))
    if (isSupervisor.value && currentPendingNode.value?.handler?.id !== session.user?.id) {
      await loadUsers(departmentCode.value, session.user?.id)
    }
  } catch (error) {
    detailVisible.value = false
    ElMessage.error(errorMessage(error))
  } finally {
    detailBusy.value = false
  }
}

function nextStageFor(stage: string) {
  if (stage === 'label_apply') return newModel.value ? 'eng' : 'qc'
  if (stage === 'eng') return 'qc'
  if (stage === 'qc') return 'ie'
  if (stage === 'ie') return 'label_close'
  return null
}

async function submitApplication() {
  if (!flow.value || !nextHandlerId.value) return
  let parsedData: Record<string, unknown> = {}
  try {
    parsedData = applicationData.value.trim() ? JSON.parse(applicationData.value) : {}
  } catch {
    ElMessage.error(t('errors.generic'))
    return
  }
  actionBusy.value = true
  try {
    await api.post('/label-application/', {
      packing_list: flow.value.packing_list.id,
      is_new_model: newModel.value,
      form_data: parsedData,
      next_handler_id: Number(nextHandlerId.value),
    })
    ElMessage.success(t('application.success'))
    await openFlow(flow.value.id)
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    actionBusy.value = false
  }
}

function buildActionPayload() {
  const payload: Record<string, unknown> = { comment: comment.value }
  if (nextHandlerId.value) payload.next_handler_id = Number(nextHandlerId.value)
  if (actingFor.value) payload.on_behalf_of = Number(actingFor.value)
  return payload
}

async function approve() {
  if (!flow.value || !currentPendingNode.value) return
  if (delegating.value && !actingFor.value) return
  const nextStage = nextStageFor(flow.value.current_node)
  if (nextStage && !nextHandlerId.value) return
  actionBusy.value = true
  try {
    await api.post(`/approval/${currentPendingNode.value.id}/approve/`, buildActionPayload())
    ElMessage.success(t('approval.success'))
    await openFlow(flow.value.id)
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    actionBusy.value = false
  }
}

async function submitRejection() {
  if (!flow.value || !currentPendingNode.value || !rejectTo.value || !rejectReason.value.trim()) return
  if (delegating.value && !actingFor.value) return
  actionBusy.value = true
  const payload: Record<string, unknown> = { reject_to: rejectTo.value, reason: rejectReason.value }
  if (actingFor.value) payload.on_behalf_of = Number(actingFor.value)
  try {
    await api.post(`/approval/${currentPendingNode.value.id}/reject/`, payload)
    rejectVisible.value = false
    rejectReason.value = ''
    ElMessage.success(t('approval.rejectSuccess'))
    await openFlow(flow.value.id)
    await loadData()
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    actionBusy.value = false
  }
}

watch(newModel, async (value) => {
  if (flow.value?.current_node !== 'label_apply') return
  nextHandlerId.value = ''
  try {
    await loadUsers(value ? 'engineering' : 'qc')
  } catch (error) {
    ElMessage.error(errorMessage(error))
  }
})

watch(departmentScope, loadData)
watch(() => userForm.department_id, (department) => {
  if (userForm.role === 'staff') loadAdminSupervisors(department)
})
watch(() => userForm.role, (role) => {
  if (role === 'staff') loadAdminSupervisors(userForm.department_id)
  else userForm.supervisor_id = ''
})
watch([statusFilter, departmentFilter], () => {
  if (!loading.value) loadData()
})
watch(() => route.hash, (hash) => {
  const tab = hash.slice(1)
  if (['overview', 'packing', 'tasks', 'admin'].includes(tab) && (tab !== 'admin' || isAdmin.value)) {
    activeTab.value = tab as typeof activeTab.value
  }
}, { immediate: true })
onMounted(loadData)
</script>

<template>
  <section class="workspace">
    <div class="workspace-heading">
      <div>
        <div class="eyebrow">{{ t('app.subtitle') }} <span>/</span> {{ departmentLabel(departmentCode) }}</div>
        <h1>{{ t('dashboard.title') }}</h1>
        <p>{{ t('dashboard.description') }}</p>
      </div>
      <div class="heading-actions">
        <el-button class="refresh-button" @click="loadData">{{ t('common.refresh') }}</el-button>
        <el-button v-if="canUpload" type="primary" @click="openUpload">{{ t('dashboard.startUpload') }}</el-button>
      </div>
    </div>

    <div class="metric-row">
      <button class="metric metric-accent" @click="activeTab = 'tasks'">
        <span>{{ t('dashboard.openTasks') }}</span><strong>{{ tasks.length }}</strong><small>{{ t('dashboard.queue') }}</small>
      </button>
      <button class="metric" @click="activeTab = 'packing'">
        <span>{{ t('dashboard.activeFlows') }}</span><strong>{{ activeFlows }}</strong><small>{{ t('dashboard.allFlows') }}</small>
      </button>
      <button class="metric metric-complete" @click="activeTab = 'packing'">
        <span>{{ t('dashboard.completed') }}</span><strong>{{ completedFlows }}</strong><small>{{ t('packing.title') }}</small>
      </button>
      <div class="metric-date"><span>{{ t('common.today') }}</span><strong>{{ new Date().toLocaleDateString() }}</strong><small>{{ session.user?.display_name }}</small></div>
    </div>

    <div class="work-panel">
      <div class="panel-toolbar">
        <div class="panel-tabs" role="tablist">
          <button :class="{ selected: activeTab === 'overview' }" @click="activeTab = 'overview'">{{ t('dashboard.overview') }}</button>
          <button :class="{ selected: activeTab === 'tasks' }" @click="activeTab = 'tasks'">{{ t('nav.tasks') }} <span v-if="tasks.length" class="tab-count">{{ tasks.length }}</span></button>
          <button :class="{ selected: activeTab === 'packing' }" @click="activeTab = 'packing'">{{ t('nav.packing') }}</button>
          <button v-if="isAdmin" :class="{ selected: activeTab === 'admin' }" @click="activeTab = 'admin'">{{ t('nav.admin') }}</button>
        </div>
        <div v-if="isSupervisor && activeTab !== 'packing' && activeTab !== 'admin'" class="scope-switch">
          <span>{{ t('approval.departmentQueue') }}</span>
          <el-switch v-model="departmentScope" />
        </div>
      </div>

      <div v-loading="loading" class="panel-body">
        <template v-if="activeTab === 'overview' || activeTab === 'packing'">
          <div class="section-heading">
            <div><h2>{{ activeTab === 'packing' ? t('packing.title') : t('dashboard.recent') }}</h2><p>{{ t('packing.subtitle') }}</p></div>
            <div class="list-tools">
              <el-select v-model="statusFilter" clearable :placeholder="t('packing.status')" class="filter-select">
                <el-option v-for="value in ['pending', 'processing', 'closing', 'completed', 'rejected']" :key="value" :label="statusLabel(value)" :value="value" />
              </el-select>
              <el-select v-model="departmentFilter" clearable :placeholder="t('admin.department')" class="filter-select">
                <el-option v-for="department in departments" :key="department.id" :label="departmentLabel(department.code)" :value="department.id" />
              </el-select>
              <el-button v-if="activeTab === 'overview'" text type="primary" @click="activeTab = 'packing'">{{ t('dashboard.allFlows') }} →</el-button>
            </div>
          </div>
          <el-table :data="activeTab === 'overview' ? packingLists.slice(0, 6) : packingLists" row-key="id" class="workflow-table" @row-click="openListRow">
            <el-table-column prop="order_no" :label="t('packing.orderNo')" min-width="145">
              <template #default="scope"><span class="order-cell">{{ scope.row.order_no }}</span></template>
            </el-table-column>
            <el-table-column prop="machine_type" :label="t('packing.machineType')" min-width="140" />
            <el-table-column :label="t('flow.current')" min-width="150">
              <template #default="scope">{{ stageLabel(scope.row.current_node || 'label_apply') }}</template>
            </el-table-column>
            <el-table-column :label="t('packing.status')" width="145">
              <template #default="scope"><el-tag :type="scope.row.status === 'completed' ? 'success' : scope.row.status === 'rejected' ? 'danger' : 'warning'" effect="light">{{ statusLabel(scope.row.status) }}</el-tag></template>
            </el-table-column>
            <el-table-column prop="created_at" :label="t('packing.createdAt')" min-width="170">
              <template #default="scope">{{ new Date(scope.row.created_at).toLocaleString() }}</template>
            </el-table-column>
            <el-table-column width="90" align="right">
              <template #default="scope"><el-button text @click.stop="openFlow(scope.row.id)">{{ t('common.open') }}</el-button></template>
            </el-table-column>
            <template #empty><div class="empty-state">{{ t('common.noData') }}</div></template>
          </el-table>
        </template>

        <template v-else-if="activeTab === 'tasks'">
          <div class="section-heading">
            <div><h2>{{ t('dashboard.pendingTasks') }}</h2><p>{{ departmentScope ? t('approval.departmentQueue') : t('approval.ownQueue') }}</p></div>
          </div>
          <div v-if="tasks.length" class="task-list">
            <button v-for="task in tasks" :key="task.id" class="task-row" @click="openFlow(task.flow_id)">
              <span class="task-stage"><span class="stage-dot"></span>{{ stageLabel(task.stage) }}</span>
              <span class="task-order"><strong>{{ task.order_no }}</strong><small>{{ task.machine_type }}</small></span>
              <span class="task-handler"><small>{{ t('dashboard.assignedTo') }}</small>{{ userName(task.handler) }}</span>
              <span class="task-time">{{ new Date(task.created_at).toLocaleDateString() }}</span>
              <span class="task-open">→</span>
            </button>
          </div>
          <div v-else class="quiet-empty"><span class="empty-rule"></span><p>{{ t('dashboard.noTasks') }}</p></div>
        </template>

        <template v-else>
          <div class="admin-heading"><div><h2>{{ t('admin.title') }}</h2><p>{{ t('admin.users') }} · {{ t('admin.departments') }}</p></div><el-button type="primary" @click="openUserDialog">{{ t('admin.addUser') }}</el-button></div>
          <div class="admin-grid">
            <section class="admin-section">
              <div class="admin-section-heading"><h3>{{ t('admin.users') }}</h3><span>{{ managedUsers.length }}</span></div>
              <el-table :data="managedUsers" class="workflow-table" max-height="440">
                <el-table-column prop="display_name" :label="t('admin.displayName')" min-width="135" />
                <el-table-column prop="username" :label="t('auth.username')" min-width="120" />
                <el-table-column :label="t('admin.department')" min-width="130"><template #default="scope">{{ departmentLabel(scope.row.department?.code) }}</template></el-table-column>
                <el-table-column :label="t('admin.role')" width="110"><template #default="scope">{{ t(`role.${scope.row.role || 'staff'}`) }}</template></el-table-column>
              </el-table>
            </section>
            <section class="admin-section">
              <div class="admin-section-heading"><h3>{{ t('admin.departments') }}</h3><el-button text type="primary" @click="openDepartmentDialog()">{{ t('admin.addDepartment') }}</el-button></div>
              <div v-for="department in departments" :key="department.id" class="department-row">
                <div><strong>{{ department.name }}</strong><span>{{ departmentLabel(department.code) }} · {{ department.code }}</span></div>
                <el-button text @click="openDepartmentDialog(department)">{{ t('common.save') }}</el-button>
              </div>
            </section>
          </div>
        </template>
      </div>
    </div>
  </section>

  <el-dialog v-model="uploadVisible" :title="t('packing.uploadTitle')" width="min(560px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="dialog-form">
      <div class="form-grid">
        <el-form-item :label="t('packing.orderNo')"><el-input v-model="uploadForm.order_no" /></el-form-item>
        <el-form-item :label="t('packing.machineType')"><el-input v-model="uploadForm.machine_type" /></el-form-item>
      </div>
      <el-form-item :label="t('packing.file')">
        <el-upload drag :auto-upload="false" :limit="1" :on-change="onFileChange" :on-remove="() => (selectedFile = null)">
          <div class="upload-copy"><strong>{{ t('packing.file') }}</strong><span>{{ t('packing.fileTypes') }}</span></div>
        </el-upload>
      </el-form-item>
      <el-form-item :label="t('packing.labelHandler')">
        <el-select v-model="uploadForm.label_handler_id" filterable class="full-width">
          <el-option v-for="person in people" :key="person.id" :label="userName(person)" :value="person.id" />
        </el-select>
      </el-form-item>
    </el-form>
    <template #footer><el-button @click="uploadVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" :loading="uploadBusy" :disabled="!selectedFile || !uploadForm.label_handler_id" @click="submitUpload">{{ t('packing.upload') }}</el-button></template>
  </el-dialog>

  <el-drawer v-model="detailVisible" :title="t('flow.details')" size="min(720px, 96vw)" destroy-on-close>
    <div v-loading="detailBusy" class="flow-drawer" v-if="flow">
      <div class="flow-document-head">
        <div><span class="eyebrow">{{ t('flow.document') }}</span><h2>{{ flow.packing_list.order_no }}</h2><p>{{ flow.packing_list.machine_type }}</p></div>
        <el-tag :type="flow.status === 'completed' ? 'success' : 'warning'">{{ statusLabel(flow.status) }}</el-tag>
      </div>
      <div class="document-facts">
        <div><span>{{ t('packing.uploader') }}</span><strong>{{ userName(flow.packing_list.uploader) }}</strong></div>
        <div><span>{{ t('packing.createdAt') }}</span><strong>{{ new Date(flow.packing_list.created_at).toLocaleString() }}</strong></div>
        <div><span>{{ t('flow.current') }}</span><strong>{{ stageLabel(flow.current_node) }}</strong></div>
      </div>

      <section v-if="canActOnCurrentNode && flow.current_node === 'label_apply'" class="action-section">
        <div class="action-heading"><span class="stage-index">01</span><div><h3>{{ t('application.title') }}</h3><p>{{ t('department.label') }}</p></div></div>
        <el-form label-position="top" class="dialog-form">
          <el-form-item><el-checkbox v-model="newModel">{{ t('application.newModel') }}</el-checkbox></el-form-item>
          <el-form-item :label="t('application.nextHandler')">
            <el-select v-model="nextHandlerId" filterable class="full-width">
              <el-option v-for="person in people" :key="person.id" :label="userName(person)" :value="person.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('application.formData')"><el-input v-model="applicationData" type="textarea" :rows="4" :placeholder="t('application.placeholder')" /></el-form-item>
          <el-button type="primary" :loading="actionBusy" :disabled="!nextHandlerId" @click="submitApplication">{{ t('application.submit') }}</el-button>
        </el-form>
      </section>

      <section v-else-if="canActOnCurrentNode && ['eng', 'qc', 'ie', 'label_close'].includes(flow.current_node)" class="action-section">
        <div class="action-heading"><span class="stage-index">02</span><div><h3>{{ t('approval.title') }}</h3><p>{{ stageLabel(flow.current_node) }}</p></div></div>
        <el-form label-position="top" class="dialog-form">
          <el-form-item v-if="isSupervisor && currentPendingNode?.handler?.id !== session.user?.id">
            <el-checkbox v-model="delegating">{{ t('approval.delegate') }}</el-checkbox>
          </el-form-item>
          <el-form-item v-if="delegating && isSupervisor && currentPendingNode?.handler?.id !== session.user?.id" :label="t('approval.actingFor')">
            <el-select v-model="actingFor" filterable class="full-width">
              <el-option v-for="person in directReports" :key="person.id" :label="userName(person)" :value="person.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="nextStageFor(flow.current_node)" :label="t('approval.nextHandler')">
            <el-select v-model="nextHandlerId" filterable class="full-width">
              <el-option v-for="person in people" :key="person.id" :label="userName(person)" :value="person.id" />
            </el-select>
          </el-form-item>
          <el-form-item :label="t('approval.comment')"><el-input v-model="comment" type="textarea" :rows="3" /></el-form-item>
          <div class="action-buttons">
            <el-button type="primary" :loading="actionBusy" :disabled="delegating && !actingFor" @click="approve">{{ t('approval.approve') }}</el-button>
            <el-button type="danger" plain @click="rejectVisible = true">{{ t('approval.reject') }}</el-button>
          </div>
        </el-form>
      </section>

      <section class="history-section">
        <div class="section-heading compact"><div><h3>{{ t('flow.timeline') }}</h3></div></div>
        <div class="history-list">
          <article v-for="(node, index) in flow.nodes" :key="node.id" class="history-item" :class="`history-${node.status}`">
            <span class="history-marker">{{ String(index + 1).padStart(2, '0') }}</span>
            <div class="history-content"><div class="history-top"><strong>{{ stageLabel(node.stage) }}</strong><el-tag size="small" :type="node.status === 'approved' ? 'success' : node.status === 'rejected' ? 'danger' : 'warning'">{{ nodeStatusLabel(node.status) }}</el-tag></div>
              <p>{{ t('dashboard.assignedTo') }} · {{ userName(node.handler) }}</p>
              <p v-if="node.actual_handler && node.actual_handler.id !== node.handler?.id">{{ t('approval.processedBy') }} · {{ userName(node.actual_handler) }}</p>
              <p v-if="node.comment" class="history-comment">{{ node.comment }}</p>
              <small>{{ new Date(node.approved_at || node.created_at).toLocaleString() }}</small>
            </div>
          </article>
        </div>
      </section>
    </div>
  </el-drawer>

  <el-dialog v-model="rejectVisible" :title="t('approval.reject')" width="min(480px, 94vw)">
    <el-form label-position="top">
      <el-form-item :label="t('approval.rejectTo')">
        <el-select v-model="rejectTo" class="full-width">
          <el-option v-for="node in availableReturnStages" :key="node.id" :label="stageLabel(node.stage)" :value="node.stage" />
        </el-select>
        <small v-if="!availableReturnStages.length" class="inline-hint">{{ t('approval.noPreviousStage') }}</small>
      </el-form-item>
      <el-form-item :label="t('approval.reason')"><el-input v-model="rejectReason" type="textarea" :rows="4" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="rejectVisible = false">{{ t('common.cancel') }}</el-button><el-button type="danger" :loading="actionBusy" :disabled="!rejectTo || !rejectReason.trim() || (delegating && !actingFor)" @click="submitRejection">{{ t('approval.reject') }}</el-button></template>
  </el-dialog>

  <el-dialog v-model="userDialogVisible" :title="t('admin.addUser')" width="min(620px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="dialog-form">
      <div class="form-grid">
        <el-form-item :label="t('auth.username')"><el-input v-model="userForm.username" autocomplete="off" /></el-form-item>
        <el-form-item :label="t('admin.displayName')"><el-input v-model="userForm.display_name" /></el-form-item>
        <el-form-item :label="t('admin.password')"><el-input v-model="userForm.password" type="password" show-password autocomplete="new-password" /></el-form-item>
        <el-form-item :label="t('admin.email')"><el-input v-model="userForm.email" /></el-form-item>
        <el-form-item :label="t('admin.department')">
          <el-select v-model="userForm.department_id" class="full-width">
            <el-option v-for="department in departments" :key="department.id" :label="departmentLabel(department.code)" :value="department.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('admin.role')">
          <el-select v-model="userForm.role" class="full-width">
            <el-option :label="t('role.supervisor')" value="supervisor" />
            <el-option :label="t('role.staff')" value="staff" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="userForm.role === 'staff'" :label="t('admin.supervisor')">
          <el-select v-model="userForm.supervisor_id" class="full-width">
            <el-option v-for="person in supervisorOptions" :key="person.id" :label="userName(person)" :value="person.id" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('admin.groups')">
          <el-select v-model="userForm.groups" multiple collapse-tags class="full-width">
            <el-option v-for="group in permissionGroups" :key="group.id" :label="group.name" :value="group.id" />
          </el-select>
        </el-form-item>
      </div>
    </el-form>
    <template #footer><el-button @click="userDialogVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="saveUser">{{ t('admin.saveUser') }}</el-button></template>
  </el-dialog>

  <el-dialog v-model="departmentDialogVisible" :title="t(editingDepartment ? 'admin.editDepartment' : 'admin.addDepartment')" width="min(500px, 94vw)" destroy-on-close>
    <el-form label-position="top" class="dialog-form">
      <el-form-item :label="t('admin.englishName')"><el-input v-model="departmentForm.name" /></el-form-item>
      <el-form-item :label="t('admin.chineseName')"><el-input v-model="departmentForm.name_zh" /></el-form-item>
      <el-form-item :label="t('admin.code')"><el-input v-model="departmentForm.code" :disabled="Boolean(editingDepartment)" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="departmentDialogVisible = false">{{ t('common.cancel') }}</el-button><el-button type="primary" @click="saveDepartment">{{ t('admin.saveDepartment') }}</el-button></template>
  </el-dialog>
</template>