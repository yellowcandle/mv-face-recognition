<template>
  <v-app>
    <v-app-bar app color="primary" dark>
      <v-app-bar-nav-icon @click="drawer = !drawer"></v-app-bar-nav-icon>
      
      <v-app-bar-title>
        <v-icon class="mr-2">mdi-movie-open</v-icon>
        MV Face Recognition
      </v-app-bar-title>
      
      <v-spacer></v-spacer>
      
      <v-btn icon @click="toggleTheme">
        <v-icon>{{ isDark ? 'mdi-brightness-7' : 'mdi-brightness-4' }}</v-icon>
      </v-btn>
    </v-app-bar>

    <v-navigation-drawer
      v-model="drawer"
      app
      temporary
    >
      <v-list>
        <v-list-item
          v-for="item in menuItems"
          :key="item.title"
          :to="item.to"
          link
        >
          <template v-slot:prepend>
            <v-icon>{{ item.icon }}</v-icon>
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <v-container fluid>
        <router-view />
      </v-container>
    </v-main>

    <v-footer app>
      <v-spacer></v-spacer>
      <span>&copy; 2024 MV Face Recognition System</span>
      <v-spacer></v-spacer>
    </v-footer>
  </v-app>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useTheme } from 'vuetify'

const theme = useTheme()
const drawer = ref(false)

const isDark = computed(() => theme.global.current.value.dark)

const toggleTheme = () => {
  theme.global.name.value = isDark.value ? 'light' : 'dark'
}

const menuItems = [
  { title: 'Dashboard', icon: 'mdi-view-dashboard', to: '/' },
  { title: 'Video Processing', icon: 'mdi-video', to: '/video-processing' },
  { title: 'Face Recognition', icon: 'mdi-face-recognition', to: '/face-recognition' },
  { title: 'Analytics', icon: 'mdi-chart-line', to: '/analytics' },
  { title: 'Settings', icon: 'mdi-cog', to: '/settings' }
]
</script>