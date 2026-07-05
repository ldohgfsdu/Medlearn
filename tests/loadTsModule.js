/* global __dirname */

const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function resolveLocalModule(basePath) {
  const candidates = [
    basePath,
    `${basePath}.ts`,
    `${basePath}.tsx`,
    `${basePath}.js`,
    `${basePath}.json`,
    path.join(basePath, 'index.ts'),
    path.join(basePath, 'index.tsx'),
    path.join(basePath, 'index.js'),
  ]
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? null
}

function loadTypeScriptModule(filePath, mocks = {}, moduleCache = new Map()) {
  const resolvedFilePath = path.resolve(filePath)
  if (moduleCache.has(resolvedFilePath)) return moduleCache.get(resolvedFilePath).exports

  const source = fs.readFileSync(resolvedFilePath, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText

  const module = { exports: {} }
  moduleCache.set(resolvedFilePath, module)
  const localRequire = (request) => {
    if (Object.prototype.hasOwnProperty.call(mocks, request)) return mocks[request]
    const requestedPath = request.startsWith('@/')
      ? path.join(__dirname, '..', request.slice(2))
      : request.startsWith('.')
        ? path.resolve(path.dirname(resolvedFilePath), request)
        : null
    if (requestedPath) {
      const localPath = resolveLocalModule(requestedPath)
      if (!localPath) throw new Error(`Cannot resolve local module ${request} from ${resolvedFilePath}`)
      if (/\.[cm]?[jt]sx?$/u.test(localPath) && !localPath.endsWith('.json')) {
        return loadTypeScriptModule(localPath, mocks, moduleCache)
      }
      return require(localPath)
    }
    return require(request)
  }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  wrapper(localRequire, module, module.exports)
  return module.exports
}

module.exports = { loadTypeScriptModule }
