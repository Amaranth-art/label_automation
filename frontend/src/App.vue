<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { useSessionStore } from './stores/session'
import api from './services/api'

const { t, locale } = useI18n()
const route = useRoute()
const router = useRouter()
const session = useSessionStore()
const isLogin = computed(() => route.name === 'login')
const passwordDialogVisible = ref(false)
const passwordSubmitting = ref(false)
const passwordForm = reactive({ old_password: '', new_password: '', confirm_password: '' })

onMounted(async () => {
  if (session.token && !session.user) {
    try {
      await session.loadUser()
    } catch {
      session.signOut()
    }
  }
})

function setLocale(value: 'en' | 'zh') {
  locale.value = value
  localStorage.setItem('relay-locale', value)
}

function signOut() {
  session.signOut()
  router.replace({ name: 'login' })
}

function resetPasswordForm() {
  passwordForm.old_password = ''
  passwordForm.new_password = ''
  passwordForm.confirm_password = ''
}

function handleUserCommand(command: string) {
  if (command === 'change-password') passwordDialogVisible.value = true
  if (command === 'sign-out') signOut()
}

function passwordErrorMessage(error: any) {
  const code = error?.response?.data?.code
  const messageKeys: Record<string, string> = {
    required: 'required',
    old_password_wrong: 'oldPasswordWrong',
    not_match: 'notMatch',
    same_as_old: 'sameAsOld',
  }
  if (code && messageKeys[code]) return t(`changePassword.${messageKeys[code]}`)
  return error?.response?.data?.detail || t('errors.generic')
}

async function submitPasswordChange() {
  if (!passwordForm.old_password || !passwordForm.new_password || !passwordForm.confirm_password) {
    ElMessage.error(t('changePassword.required'))
    return
  }
  passwordSubmitting.value = true
  try {
    await api.post('/auth/change-password/', passwordForm)
    passwordDialogVisible.value = false
    resetPasswordForm()
    ElMessage.success(t('changePassword.success'))
    window.setTimeout(() => {
      session.signOut()
      router.replace({ name: 'login' })
    }, 1500)
  } catch (error) {
    ElMessage.error(passwordErrorMessage(error))
  } finally {
    passwordSubmitting.value = false
  }
}
</script>

<template>
  <div class="app-frame" :class="{ 'login-frame': isLogin }">
    <header v-if="!isLogin" class="topbar">
      <RouterLink class="brand" to="/">
        <span class="brand-mark">R</span>
        <span class="brand-copy"><strong>{{ t('app.name') }}</strong><small>{{ t('app.subtitle') }}</small></span>
      </RouterLink>
      <div class="top-nav-spacer"></div>
      <div class="top-actions">
        <el-button-group class="language-switch">
          <el-button :type="locale === 'en' ? 'primary' : 'default'" @click="setLocale('en')">EN</el-button>
          <el-button :type="locale === 'zh' ? 'primary' : 'default'" @click="setLocale('zh')">中文</el-button>
        </el-button-group>
        <el-dropdown v-if="session.user" trigger="click" @command="handleUserCommand">
          <button class="user-chip user-menu-trigger" type="button">
            <span class="user-initial">{{ session.user.display_name.slice(0, 1).toUpperCase() }}</span>
            <span class="user-name">{{ session.user.display_name }}</span>
            <span class="user-menu-caret" aria-hidden="true">⌄</span>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="change-password">{{ t('changePassword.title') }}</el-dropdown-item>
              <el-dropdown-item command="sign-out" divided>{{ t('auth.signOut') }}</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>
    <div v-if="!isLogin" class="shell-body">
      <aside class="sidebar">
        <span class="sidebar-label">{{ t('dashboard.work') }}</span>
        <RouterLink to="/#overview" class="sidebar-link" :class="{ active: route.hash === '#overview' || !route.hash }">{{ t('nav.overview') }}</RouterLink>
        <RouterLink to="/#tasks" class="sidebar-link" :class="{ active: route.hash === '#tasks' }">{{ t('nav.tasks') }}</RouterLink>
        <RouterLink to="/#packing" class="sidebar-link" :class="{ active: route.hash === '#packing' }">{{ t('nav.packing') }}</RouterLink>
        <template v-if="session.user?.is_staff">
          <span class="sidebar-label sidebar-label-lower">{{ t('nav.admin') }}</span>
          <RouterLink to="/#admin" class="sidebar-link" :class="{ active: route.hash === '#admin' }">{{ t('nav.admin') }}</RouterLink>
        </template>
      </aside>
      <main class="main-content"><RouterView /></main>
    </div>
    <main v-else class="main-content main-content-login"><RouterView /></main>

    <el-dialog
      v-model="passwordDialogVisible"
      :title="t('changePassword.title')"
      width="min(460px, 94vw)"
      destroy-on-close
      @closed="resetPasswordForm"
    >
      <el-form label-position="top" @submit.prevent="submitPasswordChange">
        <el-form-item :label="t('changePassword.oldPassword')">
          <el-input v-model="passwordForm.old_password" type="password" show-password autocomplete="current-password" />
        </el-form-item>
        <el-form-item :label="t('changePassword.newPassword')">
          <el-input v-model="passwordForm.new_password" type="password" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item :label="t('changePassword.confirmPassword')">
          <el-input v-model="passwordForm.confirm_password" type="password" show-password autocomplete="new-password" @keyup.enter="submitPasswordChange" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">{{ t('changePassword.cancel') }}</el-button>
        <el-button type="primary" :loading="passwordSubmitting" @click="submitPasswordChange">{{ t('changePassword.submit') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>