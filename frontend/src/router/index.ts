import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: () => import('../views/Dashboard.vue')
    },
    {
      path: '/video-processing',
      name: 'VideoProcessing',
      component: () => import('../modules/video-processing/views/VideoProcessingView.vue')
    },
    {
      path: '/face-recognition',
      name: 'FaceRecognition',
      component: () => import('../modules/face-recognition/views/FaceRecognitionView.vue')
    },
    {
      path: '/analytics',
      name: 'Analytics',
      component: () => import('../modules/analytics/views/AnalyticsView.vue')
    },
    {
      path: '/settings',
      name: 'Settings',
      component: () => import('../modules/settings/views/SettingsView.vue')
    }
  ]
})

export default router