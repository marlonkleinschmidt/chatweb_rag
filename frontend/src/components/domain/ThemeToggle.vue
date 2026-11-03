<script setup lang="ts">
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
import { useTheme } from '@/composables/useTheme'
import { ptBR } from '@/locales/pt-BR'

const theme = useTheme()
</script>

<template>
  <!-- The icon and the label describe the theme that will be activated -->
  <BaseButton
    variant="ghost"
    :aria-label="theme.theme === 'dark' ? ptBR.theme.toLight : ptBR.theme.toDark"
    :title="theme.theme === 'dark' ? ptBR.theme.toLight : ptBR.theme.toDark"
    @click="theme.toggle()"
  >
    <BaseIcon :name="theme.theme === 'dark' ? 'sun' : 'moon'" />
  </BaseButton>
</template>
