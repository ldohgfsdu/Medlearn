const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('typescript')

function loadTypeScriptModule(filePath, mocks = {}) {
  const source = fs.readFileSync(filePath, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText

  const module = { exports: {} }
  const localRequire = (request) => {
    if (Object.prototype.hasOwnProperty.call(mocks, request)) return mocks[request]
    return require(request)
  }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  wrapper(localRequire, module, module.exports)
  return module.exports
}

module.exports = { loadTypeScriptModule }