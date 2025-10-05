import { useCallback, useEffect, useRef, useState } from 'react';

interface AdkMessage {
    type: string;
    payload?: any;
    source?: string;
    timestamp?: number;
}

interface AdkContext {
    agentName?: string;
    sessionToken?: string;
    userId?: string;
    applicationId?: string;
    controlId?: string;
}

interface UseAdkCommunicationReturn {
    sendMessage: (message: AdkMessage) => void;
    context: AdkContext;
    updateContext: (newContext: Partial<AdkContext>) => void;
    isConnected: boolean;
    connectionStatus: 'connected' | 'disconnected' | 'error';
    messages: AdkMessage[];
}

export const useAdkCommunication = (
    adkUrl: string = '/adk',
    initialContext: AdkContext = {}
): UseAdkCommunicationReturn => {
    const iframeRef = useRef<HTMLIFrameElement | null>(null);
    const [isConnected, setIsConnected] = useState(false);
    const [connectionStatus, setConnectionStatus] = useState<'connected' | 'disconnected' | 'error'>('disconnected');
    const [messages, setMessages] = useState<AdkMessage[]>([]);
    const [context, setContext] = useState<AdkContext>(initialContext);

    // Send message to ADK iframe
    const sendMessage = useCallback((message: AdkMessage) => {
        if (iframeRef.current?.contentWindow) {
            const fullMessage: AdkMessage = {
                ...message,
                source: 'parent-app',
                timestamp: Date.now()
            };

            const targetOrigin = adkUrl.startsWith('/') ? window.location.origin : adkUrl;
            iframeRef.current.contentWindow.postMessage(fullMessage, targetOrigin);
            setMessages(prev => [...prev, fullMessage]);
        }
    }, [adkUrl]);

    // Update context and send to ADK
    const updateContext = useCallback((newContext: Partial<AdkContext>) => {
        const updatedContext = { ...context, ...newContext };
        setContext(updatedContext);

        // Send context update to ADK
        sendMessage({
            type: 'context_update',
            payload: updatedContext
        });
    }, [context, sendMessage]);

    // Handle messages from ADK iframe
    const handleMessage = useCallback((event: MessageEvent) => {
        // Security check - only accept from expected origins
        const expectedOrigins = [
            window.location.origin, // Our app
            ...(adkUrl.startsWith('/') ? [] : [adkUrl]) // Direct ADK URL if provided
        ];

        if (!expectedOrigins.includes(event.origin)) {
            return;
        }

        if (event.data?.source === 'adk-ui') {
            setMessages(prev => [...prev, event.data]);

            // Handle specific message types
            switch (event.data.type) {
                case 'ready':
                    setIsConnected(true);
                    setConnectionStatus('connected');

                    // Send initial context when ADK is ready
                    sendMessage({
                        type: 'initialize',
                        payload: context
                    });
                    break;

                case 'error':
                    setConnectionStatus('error');
                    console.error('ADK Error:', event.data.payload);
                    break;

                case 'agent_response':
                    // Handle agent responses
                    console.log('Agent Response:', event.data.payload);
                    break;

                case 'status_update':
                    // Handle status updates
                    console.log('ADK Status:', event.data.payload);
                    break;

                default:
                    console.log('ADK Message:', event.data);
            }
        }
    }, [adkUrl, context, sendMessage]);

    // Set up message listener
    useEffect(() => {
        window.addEventListener('message', handleMessage);
        return () => window.removeEventListener('message', handleMessage);
    }, [handleMessage]);

    // Check ADK server connectivity
    useEffect(() => {
        const checkConnection = async () => {
            try {
                // For proxied URLs, check if the proxy route exists
                const healthUrl = adkUrl.startsWith('/') ? `${adkUrl}/health` : `${adkUrl}/health`;

                const response = await fetch(healthUrl, {
                    method: 'GET',
                    mode: 'cors',
                });

                if (response.ok) {
                    setConnectionStatus('connected');
                } else {
                    setConnectionStatus('error');
                }
            } catch (error) {
                setConnectionStatus('error');
            }
        };

        checkConnection();

        // Check periodically
        const interval = setInterval(checkConnection, 10000); // Check every 10 seconds

        return () => clearInterval(interval);
    }, [adkUrl]);

    return {
        sendMessage,
        context,
        updateContext,
        isConnected,
        connectionStatus,
        messages
    };
};
