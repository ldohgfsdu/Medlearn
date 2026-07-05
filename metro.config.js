const { getDefaultConfig } = require('expo/metro-config')

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname)

// Exclude non-bundler directories from Metro bundler
config.resolver.blockList = [
  /supabase\/.*/,
  /\.pytest_cache\/.*/,
  /generated\/.*/,
]

module.exports = config