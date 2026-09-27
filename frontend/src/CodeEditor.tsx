import Editor, { loader } from "@monaco-editor/react";
import "monaco-editor/esm/vs/basic-languages/python/python.contribution";
import * as monaco from "monaco-editor/esm/vs/editor/editor.api";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";
(self as any).MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });
export default Editor;

import "monaco-editor/esm/vs/basic-languages/cpp/cpp.contribution";
import "monaco-editor/esm/vs/basic-languages/java/java.contribution";

import "monaco-editor/esm/vs/basic-languages/javascript/javascript.contribution";
import "monaco-editor/esm/vs/basic-languages/go/go.contribution";
import "monaco-editor/esm/vs/basic-languages/csharp/csharp.contribution";
