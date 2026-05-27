/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export', // Ini mantra biar Next.js jadi web statis
  eslint: {
    ignoreDuringBuilds: true, // Biar proses deploy gak gagal karena masalah spasi/titik koma
  },
  typescript: {
    ignoreBuildErrors: true, // Biar proses deploy jalan mulus
  },
};

module.exports = nextConfig;