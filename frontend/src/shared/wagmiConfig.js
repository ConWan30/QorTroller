// src/shared/wagmiConfig.js
import { createConfig, http } from 'wagmi'
import { injected } from 'wagmi/connectors'
import { iotexTestnet } from './chain'

export const wagmiConfig = createConfig({
  chains: [iotexTestnet],
  connectors: [
    injected({
      // ioPay injects window.ethereum (EIP-1193, ioPay 2.0 multi-chain)
      // No custom connector needed — standard injected() detects it automatically
      shimDisconnect: true,
    }),
  ],
  transports: {
    [iotexTestnet.id]: http('https://babel-api.testnet.iotex.io'),
  },
})
