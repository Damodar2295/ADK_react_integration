'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';

interface AdkEmbedProps {
    adkUrl?: string;
    agentName?: string;
    sessionToken?: string;
    userId?: string;
    onMessage?: (message: any) => void;
    onError?: (error: Error) => void;
    className?: string;
}

interface AdkMessage {
    type: string;
    payload?: any;
    source?: string;
}

const DEFAULT_ADK_URL = '/adk';

export const AdkEmbed: React.FC<AdkEmbedProps> = ({
    adkUrl = DEFAULT_ADK_URL,
    agentName,
    sessionToken,
    userId,
    onMessage,
    onError,
    className = ''
}) => {
    const iframeRef = useRef<HTMLIFrameElement>(null);
    const [isConnected, setIsConnected] = useState<boolean>(false);
    const [isLoading, setIsLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    // Check if ADK server is reachable
    const checkAdkConnection = useCallback(async () => {
        try {
            const response = await fetch(`${adkUrl}/health`, {
                method: 'GET',
                mode: 'cors',
            });
            if (response.ok) {
                setIsConnected(true);
                setError(null);
            } else {
                throw new Error(`ADK server responded with status: ${response.status}`);
            }
        } catch (err) {
            setIsConnected(false);
            setError(err instanceof Error ? err.message : 'Failed to connect to ADK server');
            onError?.(err instanceof Error ? err : new Error('ADK connection failed'));
        }
    }, [adkUrl, onError]);

    // Handle messages from iframe (ADK UI)
    const handleMessage = useCallback((event: MessageEvent) => {
        // Security: Accept messages from both direct ADK origin and our proxy
        const adkOrigin = adkUrl.startsWith('/') ? window.location.origin : new URL(adkUrl).origin;
        if (event.origin !== adkOrigin && event.origin !== window.location.origin) {
            return;
        }

        if (event.data?.source === 'adk-ui') {
            onMessage?.(event.data);
        }
    }, [adkUrl, onMessage]);

    // Send message to iframe (ADK UI)
    const sendMessage = useCallback((message: AdkMessage) => {
        if (iframeRef.current?.contentWindow) {
            iframeRef.current.contentWindow.postMessage(
                {
                    ...message,
                    source: 'parent-app',
                    timestamp: Date.now()
                },
                adkUrl.startsWith('/') ? window.location.origin : adkUrl
            );
        }
    }, [adkUrl]);

    // Initialize ADK connection and send context
    useEffect(() => {
        checkAdkConnection();

        // Set up message listener
        window.addEventListener('message', handleMessage);

        return () => {
            window.removeEventListener('message', handleMessage);
        };
    }, [checkAdkConnection, handleMessage]);

    // Send context to ADK UI when connected
    useEffect(() => {
        if (isConnected && iframeRef.current) {
            // Wait for iframe to load
            const sendContext = () => {
                sendMessage({
                    type: 'initialize',
                    payload: {
                        agentName,
                        sessionToken,
                        userId,
                        timestamp: Date.now()
                    }
                });
            };

            // Send context after a short delay to ensure iframe is ready
            const timeoutId = setTimeout(sendContext, 1000);

            return () => clearTimeout(timeoutId);
        }
    }, [isConnected, agentName, sessionToken, userId, sendMessage]);

    // Handle iframe load
    const handleIframeLoad = () => {
        setIsLoading(false);
        checkAdkConnection();
    };

    // Handle iframe error
    const handleIframeError = () => {
        setIsLoading(false);
        setError('Failed to load ADK interface');
        onError?.(new Error('ADK iframe failed to load'));
    };

    // Fallback UI when ADK server is not available
    if (!isConnected && error) {
        return (
            <div className={`adk-embed-fallback ${className}`}>
                <div className="fallback-content">
                    <div className="fallback-icon">🔌</div>
                    <h3>ADK Server Not Available</h3>
                    <p>{error}</p>
                    <div className="fallback-actions">
                        <button
                            onClick={checkAdkConnection}
                            className="retry-button"
                        >
                            Retry Connection
                        </button>
                        <p className="fallback-help">
                            Make sure to run: <code>adk web</code> on port 8000
                        </p>
                    </div>
                </div>
                <style jsx>{`
          .adk-embed-fallback {
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 400px;
            background: #f8f9fa;
            border: 2px dashed #dee2e6;
            border-radius: 8px;
            padding: 2rem;
          }

          .fallback-content {
            text-align: center;
            max-width: 400px;
          }

          .fallback-icon {
            font-size: 3rem;
            margin-bottom: 1rem;
          }

          .fallback-actions {
            margin-top: 1.5rem;
          }

          .retry-button {
            background: #007bff;
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 0.5rem;
          }

          .retry-button:hover {
            background: #0056b3;
          }

          .fallback-help {
            margin-top: 1rem;
            font-size: 0.9rem;
            color: #6c757d;
          }

          code {
            background: #e9ecef;
            padding: 0.2rem 0.4rem;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
          }
        `}</style>
            </div>
        );
    }

    return (
        <div className={`adk-embed-container ${className}`}>
            {/* Loading indicator */}
            {isLoading && (
                <div className="loading-overlay">
                    <div className="loading-spinner">
                        <div className="spinner"></div>
                        <p>Loading ADK Interface...</p>
                    </div>
                </div>
            )}

            {/* ADK iframe */}
            <iframe
                ref={iframeRef}
                src={adkUrl}
                className="adk-iframe"
                title="ADK Agent Interface"
                onLoad={handleIframeLoad}
                onError={handleIframeError}
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
            />

            <style jsx>{`
        .adk-embed-container {
          position: relative;
          width: 100%;
          height: 100%;
          min-height: 600px;
          border: 1px solid #e9ecef;
          border-radius: 8px;
          overflow: hidden;
        }

        .loading-overlay {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(255, 255, 255, 0.9);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
        }

        .loading-spinner {
          text-align: center;
        }

        .spinner {
          width: 40px;
          height: 40px;
          border: 4px solid #f3f3f3;
          border-top: 4px solid #007bff;
          border-radius: 50%;
          animation: spin 1s linear infinite;
          margin: 0 auto 1rem;
        }

        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }

        .adk-iframe {
          width: 100%;
          height: 100%;
          border: none;
          display: block;
        }
      `}</style>
        </div>
    );
};

export default AdkEmbed;
