<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import FilePreview from './FilePreview.vue'

interface SampleImage {
  path: string
  url: string
  file_name: string
}

interface LabelApplication {
  applicant?: { display_name?: string; username?: string }
  is_new_model: boolean
  form_data: Record<string, unknown>
  label_sample_images: SampleImage[]
  created_at: string
}

const props = defineProps<{ application: LabelApplication }>()
const { t } = useI18n()

type FieldKey =
  | 'machine_type' | 'work_order' | 'quantity' | 'usage_time' | 'shipping_time' | 'cycle'
  | 'label_part_no' | 'adhesion_test' | 'start_serial' | 'print_count' | 'order_no' | 'customer_pn'
  | 'font_size_setting' | 'customer_mark' | 'ppid' | 'customer_part_no' | 'printer_type'
  | 'ribbon_model' | 'barcode_level' | 'label_sample' | 'thermal_transfer' | 'confirm_new_model'
  | 'review_change' | 'ie_new_model' | 'inspector'

type Cell = FieldKey | null
const rows: Cell[][] = [
  ['machine_type', 'work_order', 'quantity', 'usage_time', 'shipping_time', 'cycle'],
  ['label_part_no', 'adhesion_test', 'start_serial', 'print_count', 'order_no', 'customer_pn'],
  ['font_size_setting', 'customer_mark', 'ppid', null, 'customer_part_no', null],
  ['printer_type', null, 'ribbon_model', null, 'barcode_level', null],
  ['label_sample', null, 'thermal_transfer', null, 'confirm_new_model', null],
  ['review_change', null, 'ie_new_model', null, null, null],
  ['inspector', null, null, null, null, null],
]

const data = computed(() => props.application.form_data)
const fields = computed(() => {
  const nestedFields = data.value.fields
  return nestedFields && typeof nestedFields === 'object'
    ? nestedFields as Record<string, unknown>
    : data.value
})
const images = computed(() => props.application.label_sample_images || [])

function fieldValue(key: FieldKey) {
  const value = fields.value[key]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}

function topLevelValue(key: string) {
  const value = data.value[key]
  return value === null || value === undefined || value === '' ? '—' : String(value)
}
</script>

<template>
  <section class="application-summary">
    <header class="summary-heading">
      <h3>{{ t('upload.labelApplication') }}</h3>
      <el-tag>{{ t(`labelApply.printType.${data.print_type === 'new_model' ? 'newModel' : data.print_type || 'normal'}`) }}</el-tag>
    </header>
    <div class="summary-facts">
      <div><span>{{ t('flow.applicant') }}</span><strong>{{ application.applicant?.display_name || application.applicant?.username || '—' }}</strong></div>
      <div><span>{{ t('packing.createdAt') }}</span><strong>{{ new Date(application.created_at).toLocaleString() }}</strong></div>
      <div><span>{{ t('labelApply.line') }}</span><strong>{{ topLevelValue('line') }}</strong></div>
      <div><span>{{ t('labelApply.groupLeader') }}</span><strong>{{ topLevelValue('group_leader') }}</strong></div>
      <div><span>{{ t('labelApply.printer') }}</span><strong>{{ topLevelValue('printer') }}</strong></div>
    </div>
    <div class="summary-grid-wrap">
      <div class="summary-grid">
        <div v-for="(row, rowIndex) in rows" :key="rowIndex" class="summary-row">
          <div v-for="(key, columnIndex) in row" :key="`${rowIndex}-${columnIndex}`" class="summary-cell">
            <template v-if="key">
              <strong>{{ t(`labelApply.fields.${key}`) }}</strong>
              <span>{{ fieldValue(key) }}</span>
            </template>
            <span v-else> </span>
          </div>
        </div>
      </div>
    </div>
    <div class="summary-extras">
      <div><strong>{{ t('labelApply.remark') }}</strong><p>{{ topLevelValue('remark') }}</p></div>
      <div><strong>{{ t('labelApply.manufacturingManager') }}</strong><p>{{ topLevelValue('manufacturing_manager') }}</p></div>
    </div>
    <section v-if="images.length" class="sample-images">
      <h4>{{ t('upload.uploadLabelSample') }}</h4>
      <FilePreview
        v-for="image in images"
        :key="image.path"
        :file-name="image.file_name"
        :file-url="image.url"
        file-type="image"
      />
    </section>
  </section>
</template>

<style scoped>
.application-summary { display: grid; gap: 14px; }
.summary-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.summary-heading h3 { margin: 0; font-size: 14px; }
.summary-facts { display: grid; grid-template-columns: repeat(auto-fit, minmax(135px, 1fr)); gap: 10px; }
.summary-facts > div { display: grid; gap: 4px; padding: 10px; background: #f6f8f6; }
.summary-facts span { color: var(--muted); font-size: 10px; }
.summary-facts strong { overflow-wrap: anywhere; font-size: 12px; }
.summary-grid-wrap { overflow-x: auto; }
.summary-grid { min-width: 780px; border-top: 1px solid #89958d; border-left: 1px solid #89958d; }
.summary-row { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); }
.summary-cell { display: grid; align-content: start; gap: 8px; min-height: 65px; padding: 8px; border-right: 1px solid #89958d; border-bottom: 1px solid #89958d; overflow-wrap: anywhere; }
.summary-cell strong { font-size: 10px; }
.summary-cell span { color: #46544b; font-size: 11px; }
.summary-extras { display: grid; grid-template-columns: 2fr 1fr; gap: 14px; }
.summary-extras > div { padding: 10px; background: #f6f8f6; }
.summary-extras strong, .sample-images h4 { font-size: 11px; }
.summary-extras p { margin: 5px 0 0; white-space: pre-wrap; font-size: 12px; }
.sample-images { display: grid; gap: 12px; }
.sample-images h4 { margin: 0; }
@media (max-width: 600px) { .summary-extras { grid-template-columns: 1fr; } }
</style>
