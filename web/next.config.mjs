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
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://example.invalid';
    
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