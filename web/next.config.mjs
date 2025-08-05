/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable static exports for Railway
  output: 'standalone',
  
  // Environment variables for production
  env: {
    NEXT_PUBLIC_BACKEND_URL: process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000',
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
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
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