/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable static exports for Railway
  output: 'standalone',
  
  // Environment variables for production
  env: {
    // Do not fallback to localhost in production without explicit env
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL,
  },
  
  // Image optimization
  images: {
    domains: [
      'media.api-sports.io',
      'upload.wikimedia.org',
      'www.thesportsdb.com',
      'crests.football-data.org'
    ],
    formats: ['image/webp', 'image/avif'],
  },
  
  // API routes configuration
  async rewrites() {
    // Use local backend in development, production URL in production
    const backendUrl = process.env.NODE_ENV === 'development' 
      ? 'http://localhost:8000'
      : (process.env.NEXT_PUBLIC_BACKEND_URL || 'https://example.invalid');
    
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      // Fallback favicon to avoid 404s in production
      {
        source: '/favicon.ico',
        destination: '/fip-logo.png',
      },
    ]
  },

  // Server configuration for better proxy handling
  serverRuntimeConfig: {
    // Increase timeout for proxy requests
    proxyTimeout: 90000, // 90 seconds for slow endpoints
  },

  // Custom webpack configuration for better proxy handling
  webpack: (config, { dev }) => {
    if (dev) {
      // Increase timeout for development proxy
      config.devServer = {
        ...config.devServer,
        proxy: {
          '/api/**': {
            target: 'http://localhost:8000',
            changeOrigin: true,
            timeout: 90000, // 90 seconds
            proxyTimeout: 90000,
          }
        }
      };
    }
    return config;
  },
  
  // HTTP agent configuration
  httpAgentOptions: {
    keepAlive: true,
  },
  
  // Performance optimizations (temporarily disabled)
  experimental: {
    // optimizeCss: true, // Disabled due to critters module issue
    optimizePackageImports: ['@radix-ui/react-icons', 'lucide-react'],
  },
  
  // Security headers
  async headers() {
    return [
      {
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'origin-when-cross-origin',
          },
        ],
      },
    ]
  },
}

export default nextConfig