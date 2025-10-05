/** @type {import('next').NextConfig} */
const nextConfig = {
    async rewrites() {
        return [
            // Proxy ADK server routes through Next.js
            {
                source: '/adk/:path*',
                destination: 'http://localhost:8000/:path*',
            },
            // Alternative route for agent UI
            {
                source: '/agent-ui-proxy/:path*',
                destination: 'http://localhost:8000/:path*',
            },
        ];
    },

    // Headers for CORS and iframe embedding
    async headers() {
        return [
            {
                source: '/adk/:path*',
                headers: [
                    {
                        key: 'Access-Control-Allow-Origin',
                        value: 'http://localhost:8000',
                    },
                    {
                        key: 'Access-Control-Allow-Methods',
                        value: 'GET, POST, PUT, DELETE, OPTIONS',
                    },
                    {
                        key: 'Access-Control-Allow-Headers',
                        value: 'Content-Type, Authorization',
                    },
                ],
            },
        ];
    },

    // Development server configuration
    ...(process.env.NODE_ENV === 'development' && {
        // Enable hot reloading for ADK integration
        webpack: (config, { dev }) => {
            if (dev) {
                config.watchOptions = {
                    poll: 1000,
                    aggregateTimeout: 300,
                };
            }
            return config;
        },
    }),
};

module.exports = nextConfig;
