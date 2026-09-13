import { useEffect, Dispatch, SetStateAction } from 'react'
import { UserProfile } from '../types'
import { copyTextToClipboard } from '../utils/clipboard'

interface UseKeyboardNavigationOptions {
  results: UserProfile[]
  selectedProfileId: string | null
  setSelectedProfileId: (id: string | null) => void
  activeSelectedProfile: UserProfile | null
  isFocusMode: boolean
  setIsFocusMode: Dispatch<SetStateAction<boolean>>
  handleToggleTheme: () => void
  toggleBookmark: (id: string) => void
  handleRequestMobilization: (profile: UserProfile) => void
  handlePrevProfile: () => void
  handleNextProfile: () => void
  setIsShortcutsOpen: Dispatch<SetStateAction<boolean>>
  showToast: (msg: string) => void
  viewMode?: 'split' | 'grid' | 'table'
  setViewMode?: (mode: 'split' | 'grid' | 'table') => void
  onToggleCompare?: (profile: UserProfile) => void
}

export function useKeyboardNavigation({
  results,
  selectedProfileId,
  setSelectedProfileId,
  activeSelectedProfile,
  isFocusMode,
  setIsFocusMode,
  handleToggleTheme,
  toggleBookmark,
  handleRequestMobilization,
  handlePrevProfile,
  handleNextProfile,
  setIsShortcutsOpen,
  showToast,
  viewMode,
  setViewMode,
  onToggleCompare,
}: UseKeyboardNavigationOptions) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const activeTag = document.activeElement?.tagName || ''
      const isResultNavigationKey = ['ArrowDown', 'ArrowUp', 'Home', 'End', 'j', 'k'].includes(e.key)
      const isFocusedResult = document.activeElement?.id?.startsWith('specialist-result-')
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(activeTag) ||
        (['BUTTON', 'A'].includes(activeTag) && !isResultNavigationKey && !(e.key === 'Enter' && isFocusedResult))) {
        return
      }

      if (e.key === '?') {
        e.preventDefault()
        setIsShortcutsOpen((prev) => !prev)
        return
      }

      if (e.key.toLowerCase() === 't') {
        e.preventDefault()
        handleToggleTheme()
        return
      }

      // View Layout Mode Switching: 1 for Split, 2 for Grid/Cards, 3 for Table/Matrix
      if (!isFocusMode && setViewMode) {
        if (e.key === '1') {
          e.preventDefault()
          setViewMode('split')
          showToast('View: Split Workspace')
          return
        }
        if (e.key === '2') {
          e.preventDefault()
          setViewMode('grid')
          showToast('View: Cards Grid')
          return
        }
        if (e.key === '3') {
          e.preventDefault()
          setViewMode('table')
          showToast('View: Matrix Spreadsheet')
          return
        }
      }

      if (e.key.toLowerCase() === 'f' && activeSelectedProfile) {
        e.preventDefault()
        setIsFocusMode((prev) => !prev)
        return
      }

      if (e.key === 'Escape' && isFocusMode) {
        e.preventDefault()
        setIsFocusMode(false)
        return
      }

      if (results.length === 0) return

      const currentIndex = results.findIndex((r) => r.id === selectedProfileId)
      const selectResultAt = (index: number) => {
        const profile = results[index]
        if (!profile) return
        setSelectedProfileId(profile.id)
        requestAnimationFrame(() => {
          const row = document.getElementById(`specialist-result-${profile.id}`)
          row?.focus()
          row?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
        })
      }

      if (e.key === 'ArrowDown' || e.key.toLowerCase() === 'j') {
        e.preventDefault()
        const nextIndex = currentIndex < results.length - 1 ? currentIndex + 1 : 0
        selectResultAt(nextIndex)
      } else if (e.key === 'ArrowUp' || e.key.toLowerCase() === 'k') {
        e.preventDefault()
        const prevIndex = currentIndex > 0 ? currentIndex - 1 : results.length - 1
        selectResultAt(prevIndex)
      } else if (e.key === 'Home') {
        e.preventDefault()
        selectResultAt(0)
      } else if (e.key === 'End') {
        e.preventDefault()
        selectResultAt(results.length - 1)
      } else if (e.key === 'ArrowLeft' && isFocusMode) {
        e.preventDefault()
        handlePrevProfile()
      } else if (e.key === 'ArrowRight' && isFocusMode) {
        e.preventDefault()
        handleNextProfile()
      } else if (e.key.toLowerCase() === 's' && activeSelectedProfile) {
        e.preventDefault()
        toggleBookmark(activeSelectedProfile.id)
      } else if (e.key.toLowerCase() === 'x' && activeSelectedProfile && onToggleCompare) {
        e.preventDefault()
        onToggleCompare(activeSelectedProfile)
      } else if (e.key.toLowerCase() === 'c' && activeSelectedProfile) {
        e.preventDefault()
        void copyTextToClipboard(activeSelectedProfile.email).then((copied) => {
          showToast(copied ? `Copied ${activeSelectedProfile.email}` : 'Could not copy the email address. Please try again.')
        })
      } else if (e.key.toLowerCase() === 'm' && activeSelectedProfile) {
        e.preventDefault()
        handleRequestMobilization(activeSelectedProfile)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    results, selectedProfileId, activeSelectedProfile, toggleBookmark,
    showToast, handleRequestMobilization, isFocusMode, handlePrevProfile,
    handleNextProfile, setIsShortcutsOpen, setIsFocusMode,
    handleToggleTheme, setSelectedProfileId, viewMode, setViewMode, onToggleCompare,
  ])
}
