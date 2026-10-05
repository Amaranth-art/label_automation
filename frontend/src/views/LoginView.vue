<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { useSessionStore } from '../stores/session'

const { t, locale } = useI18n()
const router = useRouter()
const session = useSessionStore()
const username = ref('')
const password = ref('')
const submitting = ref(false)

function setLocale(value: 'en' | 'zh') {
  locale.value = value
  localStorage.setItem('relay-locale', value)
}

async function submit() {
  submitting.value = true
  try {
    await session.signIn(username.value, password.value)
    await router.replace({ name: 'home' })
  } catch {
    ElMessage.error(t('auth.invalid'))
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <section class="login-layout">
    <div class="login-art" aria-hidden="true">
      <div class="art-orbit orbit-one"></div>
      <div class="art-orbit orbit-two"></div>
      <div class="paper-stack"><span></span><span></span><span></span></div>
      <div class="art-caption"><span>01 / 05</span><strong>{{ t('app.visualTitle') }}</strong></div>
    </div>
    <div class="login-panel">
      <div class="login-language">
        <el-button text @click="setLocale(locale === 'en' ? 'zh' : 'en')">{{ locale === 'en' ? '中文' : 'EN' }}</el-button>
      </div>
      <div class="login-content">
        <span class="eyebrow">{{ t('app.subtitle') }}</span>
        <h1>{{ t('app.name') }}</h1>
        <p>{{ t('auth.welcome') }}</p>
        <el-form class="login-form" label-position="top" @submit.prevent="submit">
          <el-form-item :label="t('auth.username')">
            <el-input v-model="username" autocomplete="username" size="large" @keyup.enter="submit" />
          </el-form-item>
          <el-form-item :label="t('auth.password')">
            <el-input v-model="password" type="password" show-password autocomplete="current-password" size="large" @keyup.enter="submit" />
          </el-form-item>
          <el-button type="primary" size="large" class="login-submit" :loading="submitting" @click="submit">
            {{ t('auth.signIn') }}
          </el-button>
        </el-form>
      </div>
      <div class="login-footer"><span class="brand-mark">R</span>{{ t('app.name') }} <span>·</span> {{ t('app.subtitle') }}</div>
    </div>
  </section>
</template>