import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import LoginView from '../views/LoginView.vue'
import LabelApplyForm from '../views/label-apply/LabelApplyForm.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    { path: '/', name: 'home', component: HomeView, meta: { requiresAuth: true } },
    { path: '/label-apply', name: 'label-apply', component: LabelApplyForm, meta: { requiresAuth: true } },
    { path: '/login', name: 'login', component: LoginView },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach((to) => {
  const signedIn = Boolean(localStorage.getItem('relay-access'))
  if (to.meta.requiresAuth && !signedIn) return { name: 'login' }
  if (to.name === 'login' && signedIn) return { name: 'home' }
})

export default router