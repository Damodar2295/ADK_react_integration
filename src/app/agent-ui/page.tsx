'use client';

import React, { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import AdkEmbed from '@/components/AdkEmbed';
import { useAdkCommunication } from '@/hooks/useAdkCommunication';

interface AgentUIProps {
  searchParams?: { [key: string]: string | string[] | undefined };
}

export default function AgentUIPage({ searchParams }: AgentUIProps) {
  const router = useRouter();
  const [currentApplication, setCurrentApplication] = useState<string>('');
  const [currentControl, setCurrentControl] = useState<string>('');

  // Initialize ADK communication
  const {
    sendMessage,
    context,
    updateContext,
    isConnected,
    connectionStatus,
    messages
  } = useAdkCommunication('/adk', {
    agentName: 'NHA_Compliance_Assistant',
    userId: 'current-user', // This should come from auth context
    applicationId: currentApplication,
    controlId: currentControl
  });

  // Handle navigation back to main app
  const handleBackToMain = () => {
    router.push('/');
  };

  // Handle application/control selection
  const handleApplicationSelect = (applicationId: string) => {
    setCurrentApplication(applicationId);
    updateContext({ applicationId });
  };

  const handleControlSelect = (controlId: string) => {
    setCurrentControl(controlId);
    updateContext({ controlId });
  };

  // Handle messages from ADK UI
  const handleAdkMessage = (message: any) => {
    console.log('Received from ADK:', message);

    // Handle specific ADK responses
    if (message.type === 'agent_response') {
      // Process agent responses and potentially update UI
      console.log('Agent response:', message.payload);
    }

    if (message.type === 'navigation_request') {
      // Handle navigation requests from ADK
      if (message.payload?.route) {
        router.push(message.payload.route);
      }
    }
  };

  // Handle ADK errors
  const handleAdkError = (error: Error) => {
    console.error('ADK Error:', error);
    // Could show error toast or fallback UI here
  };

  return (
    <div className="agent-ui-page">
      {/* Header with navigation */}
      <header className="agent-ui-header">
        <div className="header-content">
          <button
            onClick={handleBackToMain}
            className="back-button"
          >
            ← Back to Dashboard
          </button>
          <div className="header-info">
            <h1>Agent Interface</h1>
            <div className="connection-status">
              <span className={`status-indicator ${connectionStatus}`}>
                {connectionStatus === 'connected' && '🟢'}
                {connectionStatus === 'disconnected' && '🔴'}
                {connectionStatus === 'error' && '🟡'}
              </span>
              <span className="status-text">
                {connectionStatus === 'connected' && 'ADK Connected'}
                {connectionStatus === 'disconnected' && 'ADK Disconnected'}
                {connectionStatus === 'error' && 'ADK Error'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main content area */}
      <main className="agent-ui-main">
        {/* Sidebar with controls */}
        <aside className="agent-ui-sidebar">
          <div className="sidebar-section">
            <h3>Application</h3>
            <select
              value={currentApplication}
              onChange={(e) => handleApplicationSelect(e.target.value)}
              className="application-select"
            >
              <option value="">Select Application</option>
              <option value="CustomerPortal">Customer Portal</option>
              <option value="PaymentSystem">Payment System</option>
              <option value="UserManagement">User Management</option>
              <option value="Reporting">Reporting</option>
            </select>
          </div>

          <div className="sidebar-section">
            <h3>Control</h3>
            <select
              value={currentControl}
              onChange={(e) => handleControlSelect(e.target.value)}
              className="control-select"
            >
              <option value="">Select Control</option>
              <option value="AC-2.3">AC-2.3: NHA Management</option>
              <option value="IA-5.1">IA-5.1: Authentication</option>
              <option value="IAM-SCOPE-001">IAM-SCOPE-001: IAM Scope</option>
            </select>
          </div>

          {/* Context display */}
          <div className="sidebar-section">
            <h3>Context</h3>
            <div className="context-info">
              <p><strong>Application:</strong> {context.applicationId || 'Not selected'}</p>
              <p><strong>Control:</strong> {context.controlId || 'Not selected'}</p>
              <p><strong>Agent:</strong> {context.agentName}</p>
              <p><strong>User:</strong> {context.userId}</p>
            </div>
          </div>

          {/* Quick actions */}
          <div className="sidebar-section">
            <h3>Quick Actions</h3>
            <button
              onClick={() => sendMessage({ type: 'start_validation' })}
              className="action-button"
              disabled={!isConnected || !currentApplication}
            >
              Start Validation
            </button>
            <button
              onClick={() => sendMessage({ type: 'clear_context' })}
              className="action-button secondary"
              disabled={!isConnected}
            >
              Clear Context
            </button>
          </div>
        </aside>

        {/* Main ADK interface */}
        <div className="agent-ui-content">
          <AdkEmbed
            adkUrl="/adk"
            agentName={context.agentName}
            sessionToken={context.sessionToken}
            userId={context.userId}
            onMessage={handleAdkMessage}
            onError={handleAdkError}
            className="adk-embed-full"
          />
        </div>
      </main>

      <style jsx>{`
        .agent-ui-page {
          min-height: 100vh;
          background: #f8f9fa;
        }

        .agent-ui-header {
          background: white;
          border-bottom: 1px solid #e9ecef;
          padding: 1rem 0;
        }

        .header-content {
          max-width: 1200px;
          margin: 0 auto;
          padding: 0 2rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .back-button {
          background: #6c757d;
          color: white;
          border: none;
          padding: 0.5rem 1rem;
          border-radius: 4px;
          cursor: pointer;
          transition: background-color 0.2s;
        }

        .back-button:hover {
          background: #5a6268;
        }

        .header-info h1 {
          margin: 0;
          color: #495057;
        }

        .connection-status {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          margin-top: 0.5rem;
        }

        .status-indicator {
          font-size: 1.2rem;
        }

        .status-text {
          color: #6c757d;
          font-size: 0.9rem;
        }

        .agent-ui-main {
          max-width: 1200px;
          margin: 0 auto;
          padding: 2rem;
          display: grid;
          grid-template-columns: 300px 1fr;
          gap: 2rem;
        }

        .agent-ui-sidebar {
          background: white;
          padding: 1.5rem;
          border-radius: 8px;
          border: 1px solid #e9ecef;
          height: fit-content;
        }

        .sidebar-section {
          margin-bottom: 1.5rem;
        }

        .sidebar-section h3 {
          margin: 0 0 0.5rem 0;
          color: #495057;
          font-size: 1rem;
        }

        .application-select,
        .control-select {
          width: 100%;
          padding: 0.5rem;
          border: 1px solid #ced4da;
          border-radius: 4px;
          font-size: 0.9rem;
        }

        .context-info {
          background: #f8f9fa;
          padding: 0.75rem;
          border-radius: 4px;
          font-size: 0.85rem;
        }

        .context-info p {
          margin: 0.25rem 0;
        }

        .action-button {
          width: 100%;
          padding: 0.75rem;
          background: #007bff;
          color: white;
          border: none;
          border-radius: 4px;
          cursor: pointer;
          margin-bottom: 0.5rem;
          transition: background-color 0.2s;
        }

        .action-button:hover:not(:disabled) {
          background: #0056b3;
        }

        .action-button:disabled {
          background: #6c757d;
          cursor: not-allowed;
        }

        .action-button.secondary {
          background: #6c757d;
        }

        .action-button.secondary:hover:not(:disabled) {
          background: #5a6268;
        }

        .agent-ui-content {
          background: white;
          border-radius: 8px;
          border: 1px solid #e9ecef;
          overflow: hidden;
          min-height: 600px;
        }

        .adk-embed-full {
          height: 100%;
          width: 100%;
        }

        @media (max-width: 768px) {
          .agent-ui-main {
            grid-template-columns: 1fr;
            gap: 1rem;
            padding: 1rem;
          }

          .header-content {
            padding: 0 1rem;
            flex-direction: column;
            gap: 1rem;
            text-align: center;
          }
        }
      `}</style>
    </div>
  );
}
