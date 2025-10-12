import { useMemo, useState } from 'react'
import { fileToEvidence, sendA2ARequest, parseA2AResponse, Evidence } from './lib/a2a'

function uuid() {
    if ('randomUUID' in crypto) return (crypto as any).randomUUID();
    return `u_${Date.now()}_${Math.random()}`;
}

export default function App() {
    const [appId, setAppId] = useState('APP_001')
    const [controlId, setControlId] = useState('CID_123')
    const [files, setFiles] = useState<File[]>([])
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState<any>(null)
    const [error, setError] = useState<string | null>(null)

    const userId = useMemo(() => {
        const existing = localStorage.getItem('userId');
        if (existing) return existing;
        const id = `user_${uuid()}`;
        localStorage.setItem('userId', id);
        return id;
    }, [])

    const sessionId = useMemo(() => {
        const existing = localStorage.getItem('sessionId');
        if (existing) return existing;
        const id = `sess_${uuid()}`;
        localStorage.setItem('sessionId', id);
        return id;
    }, [])

    async function onSubmit() {
        setLoading(true)
        setError(null)
        setResult(null)
        try {
            const evidences: Evidence[] = []
            for (const f of files) evidences.push(await fileToEvidence(f))

            const resp = await sendA2ARequest({ appId, controlId, evidences, userId, sessionId })
            const parsed = parseA2AResponse(resp)
            setResult(parsed || resp)
        } catch (e: any) {
            setError(e?.message || String(e))
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={{ maxWidth: 900, margin: '30px auto', fontFamily: 'Inter, system-ui' }}>
            <h2>🛡️ IAM Evidence Chat Agent</h2>
            <div style={{ padding: 12, border: '1px solid #eee', borderRadius: 8, marginBottom: 12 }}>
                <div>Agent URL: {import.meta.env.VITE_AGENT_URL || 'http://127.0.0.1:8003/run'}</div>
                <div>User: {userId}</div>
                <div>Session: {sessionId}</div>
            </div>

            <div style={{ display: 'grid', gap: 12 }}>
                <label>
                    App ID
                    <input value={appId} onChange={(e) => setAppId(e.target.value)} style={{ width: '100%' }} />
                </label>
                <label>
                    Control ID
                    <input value={controlId} onChange={(e) => setControlId(e.target.value)} style={{ width: '100%' }} />
                </label>

                <label>
                    Evidences
                    <input type="file" multiple onChange={(e) => setFiles([...(e.target.files ? Array.from(e.target.files) : [])])} />
                </label>

                <button onClick={onSubmit} disabled={loading} style={{ padding: '10px 14px' }}>
                    {loading ? 'Evaluating...' : 'Evaluate IAM Evidence'}
                </button>
            </div>

            {error && (
                <div style={{ marginTop: 16, color: '#b00020' }}>
                    Error: {error}
                </div>
            )}

            {result && (
                <div style={{ marginTop: 16 }}>
                    <h3>Result</h3>
                    <pre style={{ background: '#f7f7f7', padding: 12, borderRadius: 6, overflowX: 'auto' }}>
                        {JSON.stringify(result, null, 2)}
                    </pre>
                    {typeof result === 'object' && (result as any)?.audio_url && (
                        <audio controls src={(result as any).audio_url as string} />
                    )}
                </div>
            )}
        </div>
    )
}
