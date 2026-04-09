// src/shared/store/authStore.js
import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuthStore = create(
  persist(
    (set) => ({
      apiKey:        '',
      tier:          null,   // 'gamer' | 'developer' | 'manufacturer'
      walletAddress: null,
      bridgeUrl:     '/agent', // proxied via Vite dev server → localhost:8080
      deviceId:      '',

      setTier:          (tier)          => set({ tier }),
      setApiKey:        (apiKey)        => set({ apiKey }),
      setWalletAddress: (walletAddress) => set({ walletAddress }),
      setDeviceId:      (deviceId)      => set({ deviceId }),
      clearAuth:        ()              => set({ apiKey: '', tier: null, walletAddress: null }),
    }),
    {
      name:    'vapi-auth',
      version: 1,
      // Don't persist api_key to localStorage — operator must re-enter each session
      partialize: (s) => ({ tier: s.tier, deviceId: s.deviceId }),
    }
  )
)
