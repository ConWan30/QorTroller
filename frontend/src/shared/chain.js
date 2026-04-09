// src/shared/chain.js
export const iotexTestnet = {
  id: 4690,
  name: 'IoTeX Testnet',
  nativeCurrency: { name: 'IOTX', symbol: 'IOTX', decimals: 18 },
  rpcUrls: {
    default: { http: ['https://babel-api.testnet.iotex.io'] },
    ws: { http: ['wss://babel-api.testnet.iotex.io/ws'] },
  },
  blockExplorers: {
    default: { name: 'IoTeXScan Testnet', url: 'https://testnet.iotexscan.io' },
  },
  testnet: true,
}

export const IOTEXSCAN = 'https://testnet.iotexscan.io'
export const IOPAY_DOWNLOAD = 'https://iopay.iotex.io'
