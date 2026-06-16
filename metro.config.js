const { getDefaultConfig } = require('expo/metro-config')

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname)

// Exclude server-side code from Metro bundler
config.resolver.blockList = [
  /supabase\/.*/,
]

module.exports = config