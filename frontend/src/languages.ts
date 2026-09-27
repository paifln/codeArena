export const languages: Record<
  string,
  { label: string; file: string; editor: string }
> = {
  python3: { label: "Python 3.12", file: "main.py", editor: "python" },
  cpp20: { label: "C++20 (GCC 12)", file: "main.cpp", editor: "cpp" },
  java17: { label: "Java 17", file: "Main.java", editor: "java" },
  javascript: {
    label: "JavaScript (Node.js 18)",
    file: "main.js",
    editor: "javascript",
  },
  go: { label: "Go 1.19", file: "main.go", editor: "go" },
  csharp: { label: "C# (Mono 6.8)", file: "Main.cs", editor: "csharp" },
};
