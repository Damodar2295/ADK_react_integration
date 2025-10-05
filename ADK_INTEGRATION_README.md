# ADK Integration Guide

This document explains how to embed the Google Agent Development Kit (ADK) webserver UI inside your React/Next.js application to create a unified agent interface.

## 🚀 Overview

The ADK integration allows you to:
- **Embed ADK UI** inside your React pages using `<iframe>`
- **Proxy ADK routes** through Next.js for seamless navigation
- **Communicate** between parent app and ADK using `postMessage`
- **Handle fallbacks** when ADK server is unavailable
- **Maintain security** with proper cross-origin handling

## 📁 File Structure

```
src/
├── components/
│   └── AdkEmbed.tsx              # Main ADK embedding component
├── hooks/
│   └── useAdkCommunication.ts    # Hook for ADK communication
├── app/
│   └── agent-ui/
│       └── page.tsx              # Shell page with embedded ADK
├── test-adk-integration.js       # Integration test script
└── next.config.js                # Next.js proxy configuration
```

## 🔧 Setup Instructions

### 1. Start ADK Server

```bash
# Terminal 1 - Start ADK webserver
adk web
# This starts ADK on http://localhost:8000
```

### 2. Start Next.js App

```bash
# Terminal 2 - Start Next.js development server
npm run dev
# This starts Next.js on http://localhost:3000
```

### 3. Test Integration

```bash
# Terminal 3 - Run integration tests
node test-adk-integration.js
```

### 4. Access Agent UI

Open http://localhost:3000/agent-ui in your browser to see the embedded ADK interface.

## 🎯 Components Overview

### AdkEmbed Component (`src/components/AdkEmbed.tsx`)

**Purpose**: Embeds ADK UI in an `<iframe>` with communication capabilities.

**Props**:
```typescript
interface AdkEmbedProps {
  adkUrl?: string;           // ADK server URL (default: '/adk' for proxy)
  agentName?: string;        // Agent name to initialize
  sessionToken?: string;     // Session token for auth
  userId?: string;           // User ID for context
  onMessage?: (message: any) => void;  // Handle messages from ADK
  onError?: (error: Error) => void;    // Handle errors
  className?: string;        // CSS class for styling
}
```

**Features**:
- ✅ Automatic connection checking
- ✅ Fallback UI when ADK unavailable
- ✅ Secure cross-origin messaging
- ✅ Loading states and error handling
- ✅ Context passing to ADK

### useAdkCommunication Hook (`src/hooks/useAdkCommunication.ts`)

**Purpose**: Manages communication between parent app and ADK iframe.

**Returns**:
```typescript
{
  sendMessage: (message: AdkMessage) => void;
  context: AdkContext;
  updateContext: (newContext: Partial<AdkContext>) => void;
  isConnected: boolean;
  connectionStatus: 'connected' | 'disconnected' | 'error';
  messages: AdkMessage[];
}
```

**Message Types**:
```typescript
interface AdkMessage {
  type: 'initialize' | 'context_update' | 'start_validation' | 'agent_response' | 'error';
  payload?: any;
  source?: string;
  timestamp?: number;
}
```

## 🔄 Communication Flow

### 1. Initial Setup
```javascript
// Parent app sends initialization context
sendMessage({
  type: 'initialize',
  payload: {
    agentName: 'NHA_Compliance_Assistant',
    userId: 'current-user',
    applicationId: 'CustomerPortal',
    controlId: 'AC-2.3'
  }
});
```

### 2. ADK Response Handling
```javascript
// ADK sends responses back
window.postMessage({
  type: 'agent_response',
  payload: { result: 'Validation complete' },
  source: 'adk-ui'
}, window.location.origin);
```

### 3. Context Updates
```javascript
// Update context dynamically
updateContext({ applicationId: 'NewApp' });
```

## 🚦 Routing & Proxying

### Next.js Configuration (`next.config.js`)

```javascript
// Proxy ADK routes through Next.js
async rewrites() {
  return [
    {
      source: '/adk/:path*',
      destination: 'http://localhost:8000/:path*',
    },
  ];
}

// CORS headers for ADK communication
async headers() {
  return [
    {
      source: '/adk/:path*',
      headers: [
        {
          key: 'Access-Control-Allow-Origin',
          value: 'http://localhost:8000',
        },
      ],
    },
  ];
}
```

### Route Structure

| Route | Purpose | Backend |
|-------|---------|---------|
| `/` | Main dashboard | Next.js |
| `/agent-ui` | Shell page with ADK | Next.js + ADK iframe |
| `/adk/*` | ADK UI routes (proxied) | ADK server via Next.js |

## 🔒 Security Considerations

### Cross-Origin Protection
```javascript
// Only accept messages from expected origins
const handleMessage = (event: MessageEvent) => {
  const allowedOrigins = [
    window.location.origin,  // Our app
    'http://localhost:8000'  // ADK server (if direct)
  ];

  if (!allowedOrigins.includes(event.origin)) {
    return; // Ignore unauthorized messages
  }

  if (event.data?.source === 'adk-ui') {
    // Process ADK message
  }
};
```

### Iframe Sandbox
```html
<iframe
  src="/adk"
  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
  title="ADK Agent Interface"
/>
```

## 🧪 Testing

### Integration Test Script

Run the test script to verify everything works:

```bash
node test-adk-integration.js
```

**Tests Include**:
- ✅ ADK server connectivity
- ✅ Next.js app availability
- ✅ ADK proxy routes
- ✅ Agent UI accessibility

### Manual Testing Steps

1. **Start both servers** (ADK + Next.js)
2. **Open `/agent-ui`** in browser
3. **Verify iframe loads** ADK interface
4. **Test context passing** (select application/control)
5. **Verify postMessage** communication in browser console
6. **Test fallback UI** by stopping ADK server

## 🔧 Customization

### Adding New Controls

1. **Update NHA_CONTROLS** in `agent.py`:
```python
NHA_CONTROLS["NEW-CONTROL"] = {
    "name": "New Control Name",
    "workflow_phases": {
        "Q1": "Phase 1",
        "Q2": "Phase 2"
    }
}
```

2. **Add MongoDB prompt** in `control_prompts` collection
3. **Test new control** via the UI

### Styling Customization

The components use CSS-in-JS with styled-jsx. Customize styles by modifying the `<style jsx>` blocks in:

- `AdkEmbed.tsx` - Iframe and loading states
- `agent-ui/page.tsx` - Shell page layout

### Environment Variables

Add to your `.env` file:
```env
# ADK Configuration
ADK_PORT=8000
ADK_URL=http://localhost:8000

# Next.js Configuration
NEXT_PUBLIC_ADK_EMBED_URL=/adk
```

## 🚨 Troubleshooting

### Common Issues

**❌ "ADK server not reachable"**
- Make sure `adk web` is running
- Check if port 8000 is available
- Verify firewall settings

**❌ "CORS errors"**
- Ensure Next.js proxy configuration is correct
- Check `X-Frame-Options` headers
- Verify iframe `sandbox` attributes

**❌ "postMessage not working"**
- Check origin matching in message handlers
- Verify iframe src URL is correct
- Check browser console for errors

**❌ "Context not passing"**
- Verify `sendMessage` is called after iframe loads
- Check timing of context updates
- Ensure ADK UI has message listeners

### Debug Mode

Enable debug logging:
```javascript
// In browser console
localStorage.setItem('adk-debug', 'true');

// Check messages in useAdkCommunication hook
console.log('ADK Messages:', messages);
console.log('Connection Status:', connectionStatus);
```

## 📈 Performance Considerations

### Optimization Tips

1. **Lazy Loading**: Load ADK component only when needed
2. **Connection Pooling**: Reuse ADK connections when possible
3. **Message Batching**: Batch multiple context updates
4. **Error Boundaries**: Wrap ADK components in error boundaries

### Monitoring

Monitor these metrics:
- ADK server response times
- Iframe load times
- postMessage communication latency
- Error rates and types

## 🔮 Future Enhancements

### Potential Improvements

1. **WebSocket Communication**: Replace postMessage with WebSockets for real-time updates
2. **Service Worker Integration**: Cache ADK assets for offline support
3. **Progressive Enhancement**: Show basic UI even when ADK is unavailable
4. **Multi-Agent Support**: Embed multiple ADK instances simultaneously
5. **Advanced Routing**: Dynamic route generation based on agent capabilities

## 📚 Related Documentation

- [Next.js Rewrites Documentation](https://nextjs.org/docs/api-reference/next.config.js/rewrites)
- [HTML5 postMessage API](https://developer.mozilla.org/en-US/docs/Web/API/Window/postMessage)
- [Iframe Security Best Practices](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe)
- [ADK Development Guide](https://developers.google.com/agent-development-kit)

## 🤝 Contributing

To contribute to the ADK integration:

1. **Test thoroughly** across different browsers
2. **Document new features** in this README
3. **Update tests** when adding new functionality
4. **Follow security best practices** for iframe embedding

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Run the integration test script
3. Check browser console for detailed errors
4. Verify both servers are running correctly

---

**Built with ❤️ for seamless ADK integration in modern React applications.**
