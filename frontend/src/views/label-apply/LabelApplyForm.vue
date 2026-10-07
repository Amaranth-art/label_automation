<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { UploadFile, UploadRequestOptions, UploadRawFile } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'
import FilePreview from '../../components/FilePreview.vue'
import api from '../../services/api'

type PrintType = 'new_model' | 'normal' | 'rework' | 'repair'
type FormFieldKey =
  | 'machine_type'
  | 'work_order'
  | 'quantity'
  | 'usage_time'
  | 'shipping_time'
  | 'cycle'
  | 'label_part_no'
  | 'adhesion_test'
  | 'start_serial'
  | 'print_count'
  | 'order_no'
  | 'customer_pn'
  | 'font_size_setting'
  | 'customer_mark'
  | 'ppid'
  | 'customer_part_no'
  | 'printer_type'
  | 'ribbon_model'
  | 'barcode_level'
  | 'label_sample'
  | 'thermal_transfer'
  | 'confirm_new_model'
  | 'review_change'
  | 'ie_new_model'
  | 'inspector'

interface Department {
  id: number
  code: string
}

interface Person {
  id: number
  username: string
  display_name: string
}

interface SampleImage {
  uid: number
  path: string
  url: string
  file_name: string
}

interface PackingList {
  id: number
  order_no: string
  machine_type: string
  status: string
  current_node?: string
  file?: string
  file_name?: string
  file_url?: string
  file_type?: string
  created_at?: string
  uploader?: Person
}

interface FieldDefinition {
  key: FormFieldKey
  type?: 'number' | 'date'
}

interface FormFields {
  machine_type: string
  work_order: string
  quantity: number | null
  usage_time: string
  shipping_time: string
  cycle: string
  label_part_no: string
  adhesion_test: string
  start_serial: string
  print_count: number | null
  order_no: string
  customer_pn: string
  font_size_setting: string
  customer_mark: string
  ppid: string
  customer_part_no: string
  printer_type: string
  ribbon_model: string
  barcode_level: string
  label_sample: string
  thermal_transfer: string
  confirm_new_model: string
  review_change: string
  ie_new_model: string
  inspector: string
}

type TableCell = FieldDefinition | { note: string } | null

const { t, tm, rt } = useI18n()
const route = useRoute()
const departments = ref<Department[]>([])
const packingLists = ref<PackingList[]>([])
const people = ref<Person[]>([])
const sampleImages = ref<SampleImage[]>([])
const sampleUploadList = ref<UploadFile[]>([])
const selectedPackingListId = ref<number | ''>('')
const nextHandlerId = ref<number | ''>('')
const loading = ref(false)
const loadingPeople = ref(false)
const submitting = ref(false)
const handlersLoaded = ref(false)
const departmentsLoaded = ref(false)
let handlerRequestId = 0

const printType = ref<PrintType | ''>('')
const form = reactive({
  line: '',
  group_leader: '',
  printer: '',
  fields: {
    machine_type: '',
    work_order: '',
    quantity: null as number | null,
    usage_time: '',
    shipping_time: '',
    cycle: '',
    label_part_no: '',
    adhesion_test: '',
    start_serial: '',
    print_count: null as number | null,
    order_no: '',
    customer_pn: '',
    font_size_setting: '',
    customer_mark: '',
    ppid: '',
    customer_part_no: '',
    printer_type: '',
    ribbon_model: '',
    barcode_level: '',
    label_sample: '',
    thermal_transfer: '',
    confirm_new_model: '',
    review_change: '',
    ie_new_model: '',
    inspector: '',
  } as FormFields,
  remark: '',
  manufacturing_manager: '',
})

const tableRows: TableCell[][] = [
  [
    { key: 'machine_type' }, { key: 'work_order' }, { key: 'quantity', type: 'number' },
    { key: 'usage_time', type: 'date' }, { key: 'shipping_time', type: 'date' }, { key: 'cycle' },
  ],
  [
    { key: 'label_part_no' }, { key: 'adhesion_test' }, { key: 'start_serial' },
    { key: 'print_count', type: 'number' }, { key: 'order_no' }, { key: 'customer_pn' },
  ],
  [
    { key: 'font_size_setting' }, { key: 'customer_mark' }, { key: 'ppid' },
    null, { key: 'customer_part_no' }, null,
  ],
  [
    { key: 'printer_type' }, null, { key: 'ribbon_model' },
    null, { key: 'barcode_level' }, null,
  ],
  [
    { key: 'label_sample' }, null, { key: 'thermal_transfer' },
    null, { key: 'confirm_new_model' }, null,
  ],
  [
    { key: 'review_change' }, null, { key: 'ie_new_model' },
    null, null, null,
  ],
  [
    { key: 'inspector' }, null, null, null, null, { note: 'signOffNote' },
  ],
]

const availablePackingLists = computed(() => packingLists.value.filter(
  (item) => item.current_node === 'label_apply' && item.status === 'pending',
))
const selectedPackingList = computed(() => availablePackingLists.value.find(
  (item) => item.id === selectedPackingListId.value,
))
const requiredFieldsComplete = computed(() => Boolean(
  printType.value
  && form.line.trim()
  && form.printer.trim()
  && form.fields.machine_type.trim()
  && form.fields.work_order.trim()
  && form.fields.quantity !== null
  && form.fields.label_part_no.trim(),
))
const nextDepartmentCode = computed(() => printType.value === 'new_model' ? 'eng' : 'qc')
const nextDepartment = computed(() => {
  const aliases = nextDepartmentCode.value === 'eng' ? ['eng', 'engineering'] : ['qc']
  return departments.value.find((item) => aliases.includes(item.code.toLowerCase()))
})
const canSubmit = computed(() => Boolean(
  requiredFieldsComplete.value
  && selectedPackingListId.value
  && sampleImages.value.length > 0
  && nextHandlerId.value
  && handlersLoaded.value,
))
const checklistItems = computed(() => tm('labelApply.checklistItems') as string[])

function fieldLabel(key: FormFieldKey) {
  return t(`labelApply.fields.${key}`)
}

function fieldIsRequired(key: FormFieldKey) {
  return ['machine_type', 'work_order', 'quantity', 'label_part_no'].includes(key)
}

function setFieldValue(key: FormFieldKey, value: string | number | Date | null | undefined) {
  const normalizedValue = value instanceof Date ? value.toISOString().slice(0, 10) : value
  if (key === 'quantity' || key === 'print_count') {
    form.fields[key] = typeof normalizedValue === 'number' ? normalizedValue : null
    return
  }
  form.fields[key] = typeof normalizedValue === 'string' ? normalizedValue : ''
}

function isAllowedImage(file: File | UploadRawFile) {
  return ['.jpg', '.jpeg', '.png'].includes(file.name.slice(file.name.lastIndexOf('.')).toLowerCase())
}

function beforeSampleUpload(file: UploadRawFile) {
  if (!isAllowedImage(file)) {
    ElMessage.error(t('upload.onlyImageAllowed'))
    return false
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error(t('upload.sizeExceeded'))
    return false
  }
  return true
}

async function uploadSampleImage(options: UploadRequestOptions) {
  const body = new FormData()
  body.append('files', options.file)
  try {
    const { data } = await api.post<{ files: Omit<SampleImage, 'uid'>[] }>(
      '/label-application/upload-sample/',
      body,
    )
    const uploaded = data.files.map((file) => ({ ...file, uid: options.file.uid }))
    sampleImages.value.push(...uploaded)
    options.onSuccess(data)
  } catch (error) {
    const uploadError = Object.assign(
      error instanceof Error ? error : new Error(t('errors.generic')),
      { status: 0, method: 'POST', url: '/api/label-application/upload-sample/' },
    )
    options.onError(uploadError)
    ElMessage.error(errorMessage(error))
  }
}

function removeSampleImage(file: UploadFile) {
  sampleImages.value = sampleImages.value.filter((image) => image.uid !== file.uid)
}

function errorMessage(error: unknown) {
  const detail = (error as { response?: { data?: Record<string, unknown> | string } })?.response?.data
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object') {
    const firstValue = Object.values(detail)[0]
    if (Array.isArray(firstValue)) return String(firstValue[0])
    if (typeof firstValue === 'string') return firstValue
  }
  return t('errors.generic')
}

async function loadInitialData() {
  loading.value = true
  try {
    const [departmentResponse, packingResponse] = await Promise.all([
      api.get<Department[]>('/departments/'),
      api.get<PackingList[]>('/packing-list/'),
    ])
    departments.value = departmentResponse.data
    packingLists.value = packingResponse.data
    departmentsLoaded.value = true

    const requestedId = Number(route.query.packing_list_id)
    if (Number.isInteger(requestedId) && availablePackingLists.value.some((item) => item.id === requestedId)) {
      selectedPackingListId.value = requestedId
    } else {
      const [firstPackingList] = availablePackingLists.value
      if (availablePackingLists.value.length === 1 && firstPackingList) {
        selectedPackingListId.value = firstPackingList.id
      }
    }
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    loading.value = false
  }
}

async function loadNextHandlers() {
  const requestId = ++handlerRequestId
  people.value = []
  nextHandlerId.value = ''
  handlersLoaded.value = false
  if (!requiredFieldsComplete.value) return
  if (!departmentsLoaded.value) return

  if (!nextDepartment.value) {
    ElMessage.error(t('labelApply.errors.departmentUnavailable'))
    return
  }

  loadingPeople.value = true
  try {
    const { data } = await api.get<Person[]>('/users/', {
      params: { department: nextDepartment.value.id },
    })
    if (requestId !== handlerRequestId) return
    people.value = data
    handlersLoaded.value = true
  } catch (error) {
    if (requestId === handlerRequestId) ElMessage.error(errorMessage(error))
  } finally {
    if (requestId === handlerRequestId) loadingPeople.value = false
  }
}

function validateForm() {
  if (!printType.value) {
    ElMessage.error(t('labelApply.errors.printTypeRequired'))
    return false
  }
  if (!form.line.trim()) {
    ElMessage.error(t('labelApply.errors.lineRequired'))
    return false
  }
  if (!form.printer.trim()) {
    ElMessage.error(t('labelApply.errors.printerRequired'))
    return false
  }
  if (!form.fields.machine_type.trim()) {
    ElMessage.error(t('labelApply.errors.machineTypeRequired'))
    return false
  }
  if (!form.fields.work_order.trim()) {
    ElMessage.error(t('labelApply.errors.workOrderRequired'))
    return false
  }
  if (form.fields.quantity === null) {
    ElMessage.error(t('labelApply.errors.quantityRequired'))
    return false
  }
  if (!form.fields.label_part_no.trim()) {
    ElMessage.error(t('labelApply.errors.labelPartNoRequired'))
    return false
  }
  if (!sampleImages.value.length) {
    ElMessage.error(t('upload.labelSampleRequired'))
    return false
  }
  if (!selectedPackingListId.value) {
    ElMessage.error(t('labelApply.errors.packingListRequired'))
    return false
  }
  if (!nextHandlerId.value) {
    ElMessage.error(t('labelApply.errors.handlerRequired'))
    return false
  }
  return true
}

async function submitForm() {
  if (!validateForm()) return
  submitting.value = true
  const submittedPackingListId = Number(selectedPackingListId.value)
  try {
    await api.post('/label-application/', {
      packing_list_id: submittedPackingListId,
      form_data: {
        print_type: printType.value,
        line: form.line.trim(),
        group_leader: form.group_leader.trim(),
        printer: form.printer.trim(),
        fields: { ...form.fields },
        remark: form.remark.trim(),
        manufacturing_manager: form.manufacturing_manager.trim(),
      },
      label_sample_images: sampleImages.value.map((image) => image.path),
      next_handler_id: Number(nextHandlerId.value),
    })
    ElMessage.success(t('labelApply.success'))
    packingLists.value = packingLists.value.filter((item) => item.id !== submittedPackingListId)
    selectedPackingListId.value = ''
    printType.value = ''
    sampleImages.value = []
    sampleUploadList.value = []
    Object.assign(form, {
      line: '',
      group_leader: '',
      printer: '',
      fields: {
        machine_type: '', work_order: '', quantity: null, usage_time: '', shipping_time: '',
        cycle: '', label_part_no: '', adhesion_test: '', start_serial: '', print_count: null,
        order_no: '', customer_pn: '', font_size_setting: '', customer_mark: '', ppid: '',
        customer_part_no: '', printer_type: '', ribbon_model: '', barcode_level: '',
        label_sample: '', thermal_transfer: '', confirm_new_model: '', review_change: '',
        ie_new_model: '', inspector: '',
      },
      remark: '',
      manufacturing_manager: '',
    })
  } catch (error) {
    ElMessage.error(errorMessage(error))
  } finally {
    submitting.value = false
  }
}

watch([requiredFieldsComplete, nextDepartment], loadNextHandlers)

onMounted(loadInitialData)
</script>

<template>
  <section class="label-apply-page" v-loading="loading">
    <header class="label-apply-heading">
      <div>
        <span class="label-apply-eyebrow">{{ t('labelApply.eyebrow') }}</span>
        <h1>{{ t('labelApply.title') }}</h1>
      </div>
      <el-select
        v-model="selectedPackingListId"
        clearable
        filterable
        :placeholder="t('labelApply.packingList')"
        class="packing-list-select"
      >
        <el-option
          v-for="item in availablePackingLists"
          :key="item.id"
          :label="`${item.order_no} · ${item.machine_type}`"
          :value="item.id"
        />
      </el-select>
    </header>

    <div class="label-apply-workspace">
      <aside class="packing-preview-panel">
        <h2>{{ t('upload.packingList') }}</h2>
        <template v-if="selectedPackingList">
          <div class="packing-preview-facts">
            <strong>{{ selectedPackingList.order_no }}</strong>
            <span>{{ selectedPackingList.machine_type }}</span>
            <span v-if="selectedPackingList.uploader">{{ t('packing.uploader') }} · {{ selectedPackingList.uploader.display_name || selectedPackingList.uploader.username }}</span>
            <span v-if="selectedPackingList.created_at">{{ t('packing.createdAt') }} · {{ new Date(selectedPackingList.created_at).toLocaleString() }}</span>
          </div>
          <FilePreview
            :file-name="selectedPackingList.file_name || selectedPackingList.file?.split('/').pop() || ''"
            :file-url="selectedPackingList.file_url || selectedPackingList.file || ''"
            :file-type="selectedPackingList.file_type || ''"
          />
        </template>
        <p v-else class="packing-preview-empty">{{ t('labelApply.selectPackingListToPreview') }}</p>
      </aside>

      <el-form class="label-application-form" @submit.prevent="submitForm">
      <section class="application-paper">
        <div class="print-type-row">
          <strong>{{ t('labelApply.printType.label') }} <span class="required-mark">*</span></strong>
          <el-radio-group v-model="printType" class="print-type-options">
            <el-radio value="new_model">{{ t('labelApply.printType.newModel') }}</el-radio>
            <el-radio value="normal">{{ t('labelApply.printType.normal') }}</el-radio>
            <el-radio value="rework">{{ t('labelApply.printType.rework') }}</el-radio>
            <el-radio value="repair">{{ t('labelApply.printType.repair') }}</el-radio>
          </el-radio-group>
        </div>

        <div class="contact-fields">
          <label>
            <span>{{ t('labelApply.line') }} <span class="required-mark">*</span></span>
            <el-input v-model="form.line" />
          </label>
          <label>
            <span>{{ t('labelApply.groupLeader') }}</span>
            <el-input v-model="form.group_leader" />
          </label>
          <label>
            <span>{{ t('labelApply.printer') }} <span class="required-mark">*</span></span>
            <el-input v-model="form.printer" />
          </label>
        </div>

        <div class="application-grid-wrap">
          <div class="application-grid" role="table" :aria-label="t('labelApply.title')">
            <div v-for="(row, rowIndex) in tableRows" :key="rowIndex" class="application-grid-row" role="row">
              <div
                v-for="(cell, cellIndex) in row"
                :key="`${rowIndex}-${cellIndex}`"
                class="application-grid-cell"
                :class="{ 'empty-cell': !cell, 'note-cell': cell && 'note' in cell }"
                role="cell"
              >
                <template v-if="cell && 'key' in cell">
                  <label class="grid-field">
                    <span class="grid-field-label">
                      {{ fieldLabel(cell.key) }}
                      <span v-if="fieldIsRequired(cell.key)" class="required-mark">*</span>
                    </span>
                    <el-input
                      v-if="!cell.type"
                      v-model="form.fields[cell.key]"
                      size="small"
                    />
                    <el-input-number
                      v-else-if="cell.type === 'number'"
                      :model-value="form.fields[cell.key]"
                      @update:model-value="setFieldValue(cell.key, $event)"
                      :min="0"
                      :controls="false"
                      size="small"
                    />
                    <el-date-picker
                      v-else
                      :model-value="form.fields[cell.key]"
                      @update:model-value="setFieldValue(cell.key, $event)"
                      type="date"
                      value-format="YYYY-MM-DD"
                      size="small"
                    />
                  </label>
                </template>
                <span v-else-if="cell && 'note' in cell" class="signoff-note">{{ t(`labelApply.${cell.note}`) }}</span>
              </div>
            </div>
          </div>
        </div>

        <section class="checklist-panel">
          <h2>{{ t('labelApply.checklist') }}</h2>
          <ol>
            <li v-for="(item, index) in checklistItems" :key="index">{{ rt(item) }}</li>
          </ol>
        </section>

        <div class="additional-fields">
          <label class="remark-field">
            <span>{{ t('labelApply.remark') }}</span>
            <el-input v-model="form.remark" type="textarea" :rows="3" />
          </label>
          <label>
            <span>{{ t('labelApply.manufacturingManager') }}</span>
            <el-input v-model="form.manufacturing_manager" />
          </label>
        </div>
        <el-form-item :label="t('labelApply.sampleImages')" class="sample-upload-field">
          <el-upload
            v-model:file-list="sampleUploadList"
            accept=".jpg,.jpeg,.png"
            list-type="picture-card"
            multiple
            :before-upload="beforeSampleUpload"
            :http-request="uploadSampleImage"
            :on-remove="removeSampleImage"
          >
            <span class="sample-upload-add">+</span>
          </el-upload>
        </el-form-item>
      </section>

      <section v-if="requiredFieldsComplete" class="next-handler-panel">
        <div class="next-handler-heading">
          <div>
            <h2>{{ t('labelApply.nextHandler') }}</h2>
            <p>{{ t(`labelApply.nextDepartment.${nextDepartmentCode}`) }}</p>
          </div>
        </div>
        <el-select
          v-model="nextHandlerId"
          filterable
          :loading="loadingPeople"
          :placeholder="t('labelApply.nextHandlerPlaceholder')"
          class="next-handler-select"
        >
          <el-option
            v-for="person in people"
            :key="person.id"
            :label="person.display_name || person.username"
            :value="person.id"
          />
        </el-select>
        <p v-if="handlersLoaded && !people.length" class="no-handler-warning">{{ t('labelApply.noHandlers') }}</p>
      </section>

      <div class="label-apply-actions">
        <el-button type="primary" :loading="submitting" :disabled="!canSubmit" native-type="submit">
          {{ t('labelApply.submit') }}
        </el-button>
      </div>
      </el-form>
    </div>
  </section>
</template>

<style scoped>
.label-apply-page { display: grid; gap: 20px; }
.label-apply-heading { display: flex; justify-content: space-between; align-items: flex-end; gap: 20px; }
.label-apply-eyebrow { color: var(--green); font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; }
.label-apply-heading h1 { margin: 8px 0 0; color: var(--ink); font: 600 30px/1.15 Georgia, 'Times New Roman', serif; }
.packing-list-select { width: min(360px, 100%); }
.label-apply-workspace { display: grid; grid-template-columns: minmax(260px, .75fr) minmax(0, 1.7fr); align-items: start; gap: 18px; }
.packing-preview-panel { position: sticky; top: 18px; display: grid; gap: 14px; min-width: 0; padding: 18px; border: 1px solid var(--line); background: #fff; }
.packing-preview-panel h2 { margin: 0; font-size: 14px; }
.packing-preview-facts { display: grid; gap: 6px; }
.packing-preview-facts strong { font-size: 13px; }
.packing-preview-facts span, .packing-preview-empty { margin: 0; color: var(--muted); font-size: 11px; }
.label-application-form { display: grid; gap: 18px; min-width: 0; }
.application-paper { display: grid; gap: 18px; padding: 24px; border: 1px solid var(--line); background: #fff; }
.print-type-row { display: flex; align-items: center; gap: 25px; min-height: 42px; border-bottom: 1px solid #dce3dd; }
.print-type-row > strong { flex: 0 0 auto; color: #34413a; font-size: 13px; }
.print-type-options { display: flex; flex-wrap: wrap; gap: 8px 18px; }
.contact-fields { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 22px; }
.contact-fields label, .additional-fields label { display: grid; align-items: center; grid-template-columns: auto minmax(120px, 1fr); gap: 10px; color: #34413a; font-size: 12px; }
.application-grid-wrap { overflow-x: auto; }
.application-grid { min-width: 1050px; border-top: 1px solid #78867d; border-left: 1px solid #78867d; }
.application-grid-row { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); }
.application-grid-cell { min-width: 0; min-height: 83px; padding: 8px; border-right: 1px solid #78867d; border-bottom: 1px solid #78867d; background: #fff; }
.application-grid-cell.empty-cell { background: #fbfcfb; }
.application-grid-cell.note-cell { display: flex; align-items: center; background: #fff; }
.grid-field { display: grid; align-content: start; gap: 7px; }
.grid-field-label { min-height: 29px; color: #34413a; font-size: 11px; font-weight: 600; line-height: 1.35; }
.grid-field :deep(.el-input-number), .grid-field :deep(.el-date-editor) { width: 100%; }
.grid-field :deep(.el-input__wrapper), .grid-field :deep(.el-input-number .el-input__wrapper) { box-shadow: 0 0 0 1px #dfe5df inset; }
.required-mark { color: #c34b32; }
.signoff-note { color: #536158; font-size: 11px; line-height: 1.5; }
.checklist-panel { padding: 16px 20px; background: #f2f5f2; color: #4b5850; }
.checklist-panel h2, .next-handler-panel h2 { margin: 0 0 12px; color: #34413a; font-size: 13px; }
.checklist-panel ol { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 7px 30px; margin: 0; padding-left: 21px; font-size: 11px; line-height: 1.55; }
.checklist-panel li:last-child { white-space: pre-line; }
.additional-fields { display: grid; grid-template-columns: minmax(0, 2fr) minmax(240px, 1fr); gap: 20px; }
.sample-upload-field { display: grid; gap: 8px; }
.sample-upload-add { font-size: 26px; line-height: 1; color: var(--muted); }
.remark-field { align-items: start !important; }
.next-handler-panel { display: grid; gap: 12px; padding: 20px 24px; border: 1px solid var(--line); background: #fff; }
.next-handler-heading p { margin: -5px 0 0; color: #77837c; font-size: 12px; }
.next-handler-select { width: min(460px, 100%); }
.no-handler-warning { margin: 0; color: #c34b32; font-size: 12px; }
.label-apply-actions { display: flex; justify-content: flex-end; }
@media (max-width: 760px) {
  .label-apply-workspace { grid-template-columns: 1fr; }
  .packing-preview-panel { position: static; }
  .label-apply-heading { align-items: stretch; flex-direction: column; }
  .packing-list-select { width: 100%; }
  .application-paper { padding: 16px 12px; }
  .print-type-row { align-items: flex-start; flex-direction: column; gap: 10px; padding-bottom: 12px; }
  .print-type-options { gap: 0 10px; }
  .contact-fields, .additional-fields { grid-template-columns: 1fr; gap: 13px; }
  .checklist-panel ol { grid-template-columns: 1fr; }
}
</style>
