<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { getFileUrl } from '../utils/file'

const props = defineProps<{
  fileName: string
  fileUrl: string
  fileType: string
}>()

const { t } = useI18n()
const resolvedFileUrl = computed(() => getFileUrl(props.fileUrl))
const normalizedType = computed(() => props.fileType.toLowerCase().replace(/^\./, ''))
const isImage = computed(() => ['jpg', 'jpeg', 'png', 'image'].includes(normalizedType.value))
const isPdf = computed(() => normalizedType.value === 'pdf')
</script>

<template>
  <section class="file-preview">
    <div class="file-preview-toolbar">
      <strong>{{ fileName }}</strong>
      <div>
        <a v-if="fileUrl" :href="resolvedFileUrl" target="_blank" rel="noopener noreferrer">{{ t('upload.preview') }}</a>
        <a v-if="fileUrl" :href="resolvedFileUrl" :download="fileName">{{ t('upload.download') }}</a>
      </div>
    </div>
    <el-image
      v-if="fileUrl && isImage"
      class="file-image"
      :src="resolvedFileUrl"
      :alt="fileName"
      :preview-src-list="[resolvedFileUrl]"
      fit="contain"
    />
    <iframe
      v-else-if="fileUrl && isPdf"
      class="file-pdf"
      :src="resolvedFileUrl"
      :title="fileName"
    />
    <p v-else class="file-download-hint">{{ t('upload.downloadToView') }}</p>
  </section>
</template>

<style scoped>
.file-preview { display: grid; gap: 10px; min-width: 0; }
.file-preview-toolbar { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 10px; }
.file-preview-toolbar strong { overflow-wrap: anywhere; font-size: 12px; }
.file-preview-toolbar > div { display: flex; gap: 12px; }
.file-preview-toolbar a { color: var(--green); font-size: 12px; font-weight: 600; }
.file-image, .file-pdf { width: 100%; height: min(58vh, 620px); border: 1px solid var(--line); background: #f6f8f6; }
.file-pdf { border: 0; }
.file-download-hint { margin: 0; padding: 30px 16px; background: #f6f8f6; color: var(--muted); font-size: 12px; text-align: center; }
</style>
