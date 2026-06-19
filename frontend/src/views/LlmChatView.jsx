import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useViewEyebrow } from '../design/Eyebrow'
import { apiPost } from '../api/client'
import { Panel, StatusChip } from '../design/Primitives'
import { FONTS, GAMER } from '../shared/design/tokens'
import '../design/qortroller-kit.css'

const LOCAL_TOOLS = [
    {
        type: "function",
        function: {
            name: "list_files",
            description: "List all files in the QorTroller repository (excluding standard ignored folders like node_modules and .git).",
            parameters: {
                type: "object",
                properties: {}
            }
        }
    },
    {
        type: "function",
        function: {
            name: "read_file",
            description: "Read the contents of a specific code or documentation file in the QorTroller repository.",
            parameters: {
                type: "object",
                properties: {
                    path: {
                        type: "string",
                        description: "Relative path of the file to read (e.g. 'contracts/contracts/ProtocolCoherenceRegistry.sol' or 'AGENTS.md')."
                    }
                },
                required: ["path"]
            }
        }
    },
    {
        type: "function",
        function: {
            name: "git_history",
            description: "Get the recent 10 git commits in the repository to understand recent code changes.",
            parameters: {
                type: "object",
                properties: {}
            }
        }
    }
];

export function LlmChatView() {
    // Set up the Eyebrow Bar spine at the top of the stage
    useViewEyebrow({
        num: '08',
        name: 'AI · AUTONOMOUS CODEBASE AGENT',
        status: 'ONLINE',
        statusTone: 'chain',
        readouts: [
            { label: 'MODEL', value: 'DEEPSEEK·V4', tone: 'chain' },
            { label: 'TOOLS', value: '3 LOCAL', tone: 'amber' },
            { label: 'SERVICE', value: 'QUICKSILVER·PRO', tone: 'chain' },
        ],
    })

    const [messages, setMessages] = useState([
        {
            role: 'assistant',
            content: 'System initialized. I am the QorTroller V.A.P.I. autonomous codebase agent. I can search the repository, read source files, inspect git history, and answer protocol questions — all from this interface. Try asking me to read a file, explain a contract, or show the latest commits.'
        }
    ])
    const [inputValue, setInputValue] = useState('')
    const [loading, setLoading] = useState(false)
    const [errorMsg, setErrorMsg] = useState('')
    const [costAccumulator, setCostAccumulator] = useState(0.0)

    const chatEndRef = useRef(null)

    // Scroll to bottom on new messages
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages, loading])

    const handleSend = async (textToSend) => {
        const queryText = textToSend || inputValue
        if (!queryText.trim() || loading) return

        setLoading(true)
        setErrorMsg('')
        if (!textToSend) setInputValue('')

        const newMessages = [...messages, { role: 'user', content: queryText }]
        setMessages(newMessages)

        const apiKey = import.meta.env.VITE_QUICKSILVER_API_KEY || "sk-el_TumeRtoQdi-lY-YQmTQ"

        // Exclude the initial welcome message and visual tool indicators from LLM prompt
        let payloadMessages = newMessages
            .filter(m => !m.isToolIndicator && m.content !== 'System initialized. I am the QorTroller V.A.P.I. cognitive assistant. You can chat with me, test telemetry session integrity, or generate player scouting profiles. What would you like to verify today?')
            .slice(-10)
            .map(m => {
                const item = { role: m.role, content: m.content || null }
                if (m.tool_calls) item.tool_calls = m.tool_calls
                if (m.tool_call_id) item.tool_call_id = m.tool_call_id
                if (m.name) item.name = m.name
                return item
            })

        const hasSystem = payloadMessages.some(m => m.role === 'system')
        if (!hasSystem) {
            const systemPrompt = (
                "You are the QorTroller V.A.P.I. autonomous codebase agent with access to local repository tools. " +
                "Here is the project context to prevent hallucinations:\n" +
                "QorTroller is the reference implementation of V.A.P.I. (Verifiable Autonomous Physical Intelligence), a DePIN sub-category " +
                "for competitive gaming. Gamers and their controllers (Sony DualShock Edge CFI-ZCP1) produce physical telemetry data and own " +
                "that data. It generates a 228-byte Proof of Autonomous Cognition (PoAC) record per cognition cycle, anchored on IoTeX L1, " +
                "to cryptographically prove liveness and prevent botting/cheating. It is NOT a DeFi lending protocol.\n\n" +
                "YOU HAVE ACCESS TO THESE LOCAL TOOLS — use them whenever the user asks about code, files, contracts, or recent changes:\n" +
                "1. list_files — List all files in the QorTroller repository\n" +
                "2. read_file(path) — Read the contents of any source file (e.g. 'AGENTS.md', 'bridge/vapi_bridge/operator_api.py')\n" +
                "3. git_history — Get the 10 most recent git commits\n\n" +
                "When asked about code structure, specific files, contracts, or implementation details, ALWAYS use the read_file tool " +
                "to fetch real source code before answering. Never guess file contents. Be concise and actionable."
            )
            payloadMessages.unshift({ role: 'system', content: systemPrompt })
        }

        let keepRunning = true
        let loopCount = 0

        try {
            while (keepRunning && loopCount < 5) {
                loopCount++

                const response = await fetch("https://api.quicksilverpro.io/v1/chat/completions", {
                    method: "POST",
                    headers: {
                        "Authorization": `Bearer ${apiKey}`,
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        model: "deepseek-v4-flash",
                        messages: payloadMessages,
                        tools: LOCAL_TOOLS
                    })
                })

                if (!response.ok) {
                    const errText = await response.text()
                    throw new Error(`API returned status ${response.status}: ${errText}`)
                }

                const data = await response.json()
                const message = data.choices?.[0]?.message

                if (!message) {
                    throw new Error("No response message returned from the LLM.")
                }

                if (message.content) {
                    setMessages(prev => [...prev, { role: 'assistant', content: message.content }])
                }

                const assistantMsgForPayload = { role: 'assistant', content: message.content || null }
                if (message.tool_calls) {
                    assistantMsgForPayload.tool_calls = message.tool_calls
                }
                payloadMessages.push(assistantMsgForPayload)

                if (message.tool_calls && message.tool_calls.length > 0) {
                    for (const toolCall of message.tool_calls) {
                        const toolName = toolCall.function.name
                        const toolArgs = JSON.parse(toolCall.function.arguments || "{}")

                        setMessages(prev => [...prev, {
                            role: 'assistant',
                            content: `🔧 Running local tool: \`${toolName}\` ${toolArgs.path ? `on \`${toolArgs.path}\`` : ''}...`,
                            isToolIndicator: true
                        }])

                        let toolResult = ""
                        try {
                            const res = await apiPost('/agent/local-host/execute', {
                                tool: toolName,
                                arguments: toolArgs
                            })
                            toolResult = res.result
                        } catch (err) {
                            console.error(err)
                            toolResult = `Error: Local bridge server is offline or returned an error. Make sure the python bridge is running on port 8080 and api key is valid. Detail: ${err.message}`
                        }

                        payloadMessages.push({
                            role: 'tool',
                            tool_call_id: toolCall.id,
                            name: toolName,
                            content: typeof toolResult === 'string' ? toolResult : JSON.stringify(toolResult)
                        })

                        const resultSnippet = typeof toolResult === 'string' 
                            ? toolResult.slice(0, 150) + (toolResult.length > 150 ? '...' : '')
                            : JSON.stringify(toolResult).slice(0, 150)

                        setMessages(prev => [...prev, {
                            role: 'assistant',
                            content: `✅ Tool \`${toolName}\` executed. Output:\n\`\`\`\n${resultSnippet}\n\`\`\``,
                            isToolIndicator: true
                        }])
                    }
                } else {
                    keepRunning = false
                    setCostAccumulator(prev => prev + 0.000006)
                }
            }
        } catch (err) {
            console.error(err)
            setErrorMsg(err.message || 'Failed to connect to the cognitive agent.')
            setMessages(prev => prev.slice(0, -1))
        } finally {
            setLoading(false)
        }
    }

    const handleKeyPress = (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault()
            handleSend()
        }
    }

    const runPreset = (presetType) => {
        if (loading) return
        if (presetType === 'integrity') {
            const mockTelemetry = {
                "L0_accelerometer": [0.04, 0.98, 1.2],
                "L1_gyroscope": [0.02, 0.88, 1.05],
                "L4_tremor_peak_hz": 11.5,
                "L5_touchpad_entropy": 4.1,
                "L9_presence_sensor": 1
            }
            handleSend(`Please run the session integrity evaluation on this L0-L9 telemetry dataset:\n${JSON.stringify(mockTelemetry, null, 2)}`)
        } else if (presetType === 'scouting') {
            const mockReplay = {
                "session_id": "vhr_session_9281",
                "action_frequency_per_minute": 240,
                "precision_score": 0.89,
                "playstyle_markers": ["aggressive_pass_rush", "consistent_rhythm"]
            }
            handleSend(`Please generate a playstyle scouting report for this verified human replay (VHR) data:\n${JSON.stringify(mockReplay, null, 2)}`)
        } else if (presetType === 'poac') {
            handleSend("Explain the structure of the 228-byte Proof of Autonomous Cognition (PoAC) record and how it prevents gaming bots.")
        }
    }

    return (
        <div className="qt-design-root" style={{
            display: 'flex',
            flexDirection: 'row',
            flex: 1,
            minHeight: 0,
            background: 'radial-gradient(circle at 50% 50%, #030a10 0%, #010408 100%)',
            padding: 16,
            gap: 16,
            overflow: 'hidden'
        }}>
            {/* Left Column: Info & Action Presets */}
            <div style={{
                width: 320,
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
                flexShrink: 0
            }}>
                <Panel eyebrow="INFO" meta="QUICKSILVER PRO" breath>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <div style={{ fontSize: 13, color: 'var(--text-dim)', lineHeight: 1.4 }}>
                            Autonomous codebase agent powered by DeepSeek V4 Flash via QuickSilver Pro. Can **search files**, **read source code**, and **inspect git history** in real-time. Requires the local bridge server for tool execution.
                        </div>
                        <div style={{
                            padding: '8px 10px',
                            background: 'rgba(0, 212, 255, 0.05)',
                            border: '1px dashed rgba(0, 212, 255, 0.2)',
                            borderRadius: 4,
                            fontSize: 11,
                            fontFamily: FONTS.mono,
                            color: GAMER.cyan
                        }}>
                            Estimated cost: ${costAccumulator.toFixed(6)}
                        </div>
                    </div>
                </Panel>

                <Panel eyebrow="PRESETS & TRIGGER INJECTS">
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                        <button
                            onClick={() => runPreset('integrity')}
                            disabled={loading}
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'flex-start',
                                gap: 2,
                                width: '100%',
                                padding: '8px 10px',
                                background: 'rgba(255,255,255,0.02)',
                                border: '1px solid rgba(255,255,255,0.06)',
                                borderRadius: 4,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                textAlign: 'left',
                            }}
                            className="preset-btn"
                        >
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--accent-amber)', fontFamily: FONTS.mono }}>[TEST] INTEGRITY</span>
                            <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>Inject mock L0-L9 telemetry</span>
                        </button>

                        <button
                            onClick={() => runPreset('scouting')}
                            disabled={loading}
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'flex-start',
                                gap: 2,
                                width: '100%',
                                padding: '8px 10px',
                                background: 'rgba(255,255,255,0.02)',
                                border: '1px solid rgba(255,255,255,0.06)',
                                borderRadius: 4,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                textAlign: 'left',
                            }}
                            className="preset-btn"
                        >
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--chain)', fontFamily: FONTS.mono }}>[TEST] VHR PROFILE</span>
                            <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>Scout player intent/playstyle</span>
                        </button>

                        <button
                            onClick={() => runPreset('poac')}
                            disabled={loading}
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'flex-start',
                                gap: 2,
                                width: '100%',
                                padding: '8px 10px',
                                background: 'rgba(255,255,255,0.02)',
                                border: '1px solid rgba(255,255,255,0.06)',
                                borderRadius: 4,
                                cursor: 'pointer',
                                transition: 'all 0.15s ease',
                                textAlign: 'left',
                            }}
                            className="preset-btn"
                        >
                            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text)', fontFamily: FONTS.mono }}>[INFO] POAC STRUCTURE</span>
                            <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>Explain anti-cheat proof format</span>
                        </button>
                    </div>
                </Panel>

                <Panel eyebrow="STATUS" meta="HARDWARE LIVENESS">
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#00ff88', boxShadow: '0 0 8px #00ff88' }} />
                        <span style={{ fontSize: 11, fontFamily: FONTS.mono, color: '#00ff88' }}>COGNITIVE_API_STABLE</span>
                    </div>
                </Panel>
            </div>

            {/* Right Column: Main Chat Console */}
            <div style={{
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
                background: 'rgba(6, 12, 20, 0.4)',
                border: '1px solid rgba(255, 255, 255, 0.05)',
                borderRadius: 8,
                overflow: 'hidden',
                backdropFilter: 'blur(12px)',
                boxShadow: '0 12px 40px rgba(0, 0, 0, 0.6)'
            }}>
                {/* Chat Header */}
                <div style={{
                    padding: '12px 16px',
                    borderBottom: '1px solid rgba(255,255,255,0.05)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    background: 'rgba(10, 20, 32, 0.6)'
                }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <span style={{ fontFamily: FONTS.mono, fontSize: 12, color: 'var(--text)', fontWeight: 700 }}>V.A.P.I. COGNITIVE ENGINE</span>
                        <StatusChip tone="live">READY</StatusChip>
                    </div>
                    <span style={{ fontSize: 10, fontFamily: FONTS.mono, color: 'var(--text-faint)' }}>
                        MODEL: deepseek-v4-flash
                    </span>
                </div>

                {/* Messages Body */}
                <div style={{
                    flex: 1,
                    padding: 16,
                    overflowY: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: 16
                }}>
                    <AnimatePresence initial={false}>
                        {messages.map((msg, index) => {
                            const isUser = msg.role === 'user'
                            return (
                                <motion.div
                                    key={index}
                                    initial={{ opacity: 0, y: 10 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0 }}
                                    transition={{ duration: 0.15 }}
                                    style={{
                                        display: 'flex',
                                        flexDirection: 'column',
                                        alignItems: isUser ? 'flex-end' : 'flex-start',
                                        maxWidth: '85%',
                                        alignSelf: isUser ? 'flex-end' : 'flex-start'
                                    }}
                                >
                                    {/* Author tag */}
                                    <span style={{
                                        fontSize: 9,
                                        fontFamily: FONTS.mono,
                                        color: isUser ? GAMER.cyan : 'var(--text-faint)',
                                        marginBottom: 4,
                                        letterSpacing: '0.08em',
                                        textTransform: 'uppercase'
                                    }}>
                                        {isUser ? 'Operator' : 'AI Assistant'}
                                    </span>

                                    {/* Bubble */}
                                    <div style={{
                                        padding: msg.isToolIndicator ? '6px 10px' : '10px 14px',
                                        borderRadius: 6,
                                        background: isUser ? 'rgba(0, 212, 255, 0.12)' : msg.isToolIndicator ? 'rgba(255, 170, 0, 0.04)' : 'rgba(255, 255, 255, 0.03)',
                                        border: `1px solid ${isUser ? 'rgba(0, 212, 255, 0.25)' : msg.isToolIndicator ? 'rgba(255, 170, 0, 0.15)' : 'rgba(255, 255, 255, 0.06)'}`,
                                        color: msg.isToolIndicator ? 'var(--accent-amber)' : 'var(--text)',
                                        fontSize: msg.isToolIndicator ? 11 : 13,
                                        lineHeight: 1.5,
                                        whiteSpace: 'pre-wrap',
                                        fontFamily: (isUser || msg.isToolIndicator) ? FONTS.mono : FONTS.body,
                                        boxShadow: isUser ? '0 0 15px rgba(0, 212, 255, 0.04)' : 'none'
                                    }}>
                                        {msg.content}
                                    </div>
                                </motion.div>
                            )
                        })}
                    </AnimatePresence>

                    {loading && (
                        <div style={{ display: 'flex', flexDirection: 'column', alignSelf: 'flex-start' }}>
                            <span style={{ fontSize: 9, fontFamily: FONTS.mono, color: 'var(--text-faint)', marginBottom: 4 }}>
                                AI Assistant
                            </span>
                            <div style={{
                                padding: '10px 14px',
                                borderRadius: 6,
                                background: 'rgba(255, 255, 255, 0.02)',
                                border: '1px solid rgba(255, 255, 255, 0.04)',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6
                            }}>
                                <div className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-faint)' }} />
                                <div className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-faint)', animationDelay: '0.2s' }} />
                                <div className="pulse-dot" style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--text-faint)', animationDelay: '0.4s' }} />
                            </div>
                        </div>
                    )}

                    {errorMsg && (
                        <div style={{
                            alignSelf: 'center',
                            background: 'rgba(255, 59, 92, 0.1)',
                            border: '1px solid rgba(255, 59, 92, 0.3)',
                            borderRadius: 4,
                            padding: '8px 16px',
                            color: '#ff3b5c',
                            fontSize: 12,
                            fontFamily: FONTS.mono
                        }}>
                            ERROR: {errorMsg}
                        </div>
                    )}
                    <div ref={chatEndRef} />
                </div>

                {/* Input Bar */}
                <div style={{
                    padding: 16,
                    borderTop: '1px solid rgba(255,255,255,0.05)',
                    background: 'rgba(8, 14, 24, 0.8)'
                }}>
                    <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
                        <textarea
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={handleKeyPress}
                            placeholder="Type a message or load a trigger preset..."
                            disabled={loading}
                            rows={1}
                            style={{
                                flex: 1,
                                background: '#04080e',
                                color: 'var(--text)',
                                border: '1px solid rgba(255,255,255,0.08)',
                                borderRadius: 4,
                                padding: '10px 12px',
                                fontFamily: FONTS.mono,
                                fontSize: 12,
                                resize: 'none',
                                outline: 'none',
                                transition: 'all 0.2s ease',
                                boxShadow: 'inset 0 2px 4px rgba(0,0,0,0.5)',
                            }}
                            className="chat-input"
                        />
                        <button
                            onClick={() => handleSend()}
                            disabled={loading || !inputValue.trim()}
                            style={{
                                padding: '10px 20px',
                                border: `1px solid ${inputValue.trim() ? GAMER.cyan : 'rgba(255,255,255,0.08)'}`,
                                borderRadius: 4,
                                background: inputValue.trim() ? 'rgba(0, 212, 255, 0.1)' : 'transparent',
                                color: inputValue.trim() ? GAMER.cyan : 'var(--text-faint)',
                                fontFamily: FONTS.mono,
                                fontSize: 12,
                                fontWeight: 700,
                                cursor: inputValue.trim() ? 'pointer' : 'not-allowed',
                                transition: 'all 0.2s ease',
                                boxShadow: inputValue.trim() ? '0 0 10px rgba(0, 212, 255, 0.1)' : 'none'
                            }}
                        >
                            SEND
                        </button>
                    </div>
                </div>
            </div>
        </div>
    )
}
