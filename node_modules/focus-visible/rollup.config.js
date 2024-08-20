import uglify from 'rollup-plugin-uglify';

export default [
  {
    input: 'src/focus-visible.js',
    output: {
      file: 'dist/focus-visible.js',
      format: 'umd'
    }
  },
  {
    input: 'src/focus-visible.js',
    output: {
      file: 'dist/focus-visible.min.js',
      format: 'umd',
      sourcemap: true
    },
    plugins: [uglify()]
  }
];
