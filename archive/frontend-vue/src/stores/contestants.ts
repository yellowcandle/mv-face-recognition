import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ApiService } from '@/core/services/api'
import type { Contestant } from '@/core/types/api'

export const useContestantsStore = defineStore('contestants', () => {
  // State
  const contestants = ref<Contestant[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)
  const searchQuery = ref('')
  const selectedContestant = ref<Contestant | null>(null)
  
  // Getters
  const contestantCount = computed(() => contestants.value.length)
  
  const contestantsWithEmbeddings = computed(() => 
    contestants.value.filter(c => c.embedding_available)
  )
  
  const embeddingCoverage = computed(() => 
    contestantCount.value > 0 
      ? (contestantsWithEmbeddings.value.length / contestantCount.value) * 100 
      : 0
  )
  
  const filteredContestants = computed(() => {
    if (!searchQuery.value) return contestants.value
    
    const query = searchQuery.value.toLowerCase()
    return contestants.value.filter(contestant =>
      contestant.name.toLowerCase().includes(query) ||
      contestant.id.toLowerCase().includes(query)
    )
  })
  
  const contestantsByLetter = computed(() => {
    const grouped: Record<string, Contestant[]> = {}
    
    filteredContestants.value.forEach(contestant => {
      const firstLetter = contestant.name.charAt(0).toUpperCase()
      if (!grouped[firstLetter]) {
        grouped[firstLetter] = []
      }
      grouped[firstLetter].push(contestant)
    })
    
    // Sort each group by name
    Object.keys(grouped).forEach(letter => {
      grouped[letter].sort((a, b) => a.name.localeCompare(b.name))
    })
    
    return grouped
  })
  
  // Actions
  const loadContestants = async () => {
    try {
      loading.value = true
      error.value = null
      const data = await ApiService.getContestants()
      contestants.value = data
    } catch (err) {
      error.value = 'Failed to load contestants'
      console.error('Error loading contestants:', err)
    } finally {
      loading.value = false
    }
  }
  
  const getContestant = async (id: string) => {
    try {
      const contestant = await ApiService.getContestant(id)
      return contestant
    } catch (err) {
      console.error('Error getting contestant:', err)
      throw err
    }
  }
  
  const selectContestant = (contestant: Contestant) => {
    selectedContestant.value = contestant
  }
  
  const clearSelection = () => {
    selectedContestant.value = null
  }
  
  const setSearchQuery = (query: string) => {
    searchQuery.value = query
  }
  
  const clearSearch = () => {
    searchQuery.value = ''
  }
  
  const refreshEmbeddings = async () => {
    try {
      loading.value = true
      error.value = null
      await ApiService.refreshEmbeddings()
      await loadContestants() // Reload to get updated embedding status
    } catch (err) {
      error.value = 'Failed to refresh embeddings'
      console.error('Error refreshing embeddings:', err)
    } finally {
      loading.value = false
    }
  }
  
  const getStats = async () => {
    try {
      const stats = await ApiService.getContestantStats()
      return stats
    } catch (err) {
      console.error('Error getting contestant stats:', err)
      throw err
    }
  }
  
  const clearError = () => {
    error.value = null
  }
  
  return {
    // State
    contestants,
    loading,
    error,
    searchQuery,
    selectedContestant,
    
    // Getters
    contestantCount,
    contestantsWithEmbeddings,
    embeddingCoverage,
    filteredContestants,
    contestantsByLetter,
    
    // Actions
    loadContestants,
    getContestant,
    selectContestant,
    clearSelection,
    setSearchQuery,
    clearSearch,
    refreshEmbeddings,
    getStats,
    clearError
  }
})