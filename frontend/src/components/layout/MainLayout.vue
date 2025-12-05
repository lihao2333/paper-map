<script setup lang="ts">
import Sidebar from './Sidebar.vue'
import Header from './Header.vue'
</script>

<template>
  <div class="flex h-screen bg-background">
    <Sidebar />
    <div class="flex-1 flex flex-col min-h-0 overflow-hidden">
      <Header />
      <main class="flex-1 min-h-0 flex flex-col px-6 py-2 overflow-auto">
        <slot />
      </main>
    </div>
  </div>
</template>
