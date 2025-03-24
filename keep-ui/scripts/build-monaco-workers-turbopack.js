const webpack = require("webpack");
const path = require("path");
const fs = require("fs");

const packageJson = require("../package.json");
const monacoEditorVersion = packageJson.dependencies["monaco-editor"];
const monacoYamlVersion = packageJson.dependencies["monaco-yaml"];

const publicWorkerDir = path.resolve(__dirname, "../public/monaco-workers");
const versionFilePath = path.resolve(publicWorkerDir, "version.json");

console.log(
  "You're running dev server with turbopack, so we're need to build the monaco workers"
);

if (fs.existsSync(versionFilePath)) {
  const version = JSON.parse(fs.readFileSync(versionFilePath, "utf8"));
  if (
    version.monacoEditorVersion === monacoEditorVersion &&
    version.monacoYamlVersion === monacoYamlVersion
  ) {
    console.log(
      `Using already built monaco-editor version ${version.monacoEditorVersion} and monaco-yaml version ${version.monacoYamlVersion}`
    );
    return;
  } else {
    console.log(
      "The monaco-editor version or monaco-yaml version has changed, rebuilding monaco workers"
    );
  }
} else {
  console.log(
    "public/monaco-workers/version.json doesn't exist, building monaco workers"
  );
}

const webpackConfig = {
  entry: {
    "editor.worker": "monaco-editor/esm/vs/editor/editor.worker.js",
    "json.worker": "monaco-editor/esm/vs/language/json/json.worker",
    "yaml.worker": "monaco-yaml/yaml.worker",
  },
  mode: "development",
  output: {
    path: publicWorkerDir,
    filename: "[name].js", // Changed from [name].bundle.js to [name].js
    globalObject: "self", // Ensures workers have the correct scope
  },
  module: {
    rules: [
      {
        test: /\.css$/,
        use: ["style-loader", "css-loader"],
      },
      {
        test: /\.ttf$/,
        type: "asset/resource",
      },
    ],
  },
};

// Add progress plugin if not already in the config
webpackConfig.plugins = webpackConfig.plugins || [];
webpackConfig.plugins.push(new webpack.ProgressPlugin());

// Run webpack with the imported config
webpack(webpackConfig, (err, stats) => {
  if (err) {
    console.error(err.stack || err);
    if (err.details) {
      console.error(err.details);
    }
    return;
  }

  const info = stats.toJson();

  if (stats.hasErrors()) {
    console.error(info.errors);
  }

  if (stats.hasWarnings()) {
    console.warn(info.warnings);
  }

  // Log success
  console.log(
    stats.toString({
      colors: true,
      chunks: false,
      modules: false,
    })
  );

  fs.writeFileSync(
    path.resolve(publicWorkerDir, "version.json"),
    JSON.stringify(
      {
        monacoEditorVersion,
        monacoYamlVersion,
        buildDate: new Date().toISOString(),
      },
      null,
      2
    )
  );
});
