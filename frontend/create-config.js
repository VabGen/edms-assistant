// create-config.js
const fs = require('fs');
fs.writeFileSync('postcss.config.js', `module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
`, 'utf8');
console.log('postcss.config.js created without BOM');