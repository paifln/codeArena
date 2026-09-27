import os
import pytest
from judge.engine import judge
from judge.sandbox import DockerSandbox

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_SANDBOX_TESTS") != "1", reason="Requires sandbox image"
)
SOURCES = {
    "javascript": "const fs=require('fs'); const a=fs.readFileSync(0,'utf8').trim().split(/\\s+/).map(Number); console.log(a[0]+a[1]);",
    "go": 'package main\nimport "fmt"\nfunc main(){var a,b int;fmt.Scan(&a,&b);fmt.Println(a+b)}',
    "csharp": "using System; class MainClass {static void Main(){var a=Console.ReadLine().Split(); Console.WriteLine(int.Parse(a[0])+int.Parse(a[1]));}}",
}


@pytest.mark.parametrize("language", SOURCES)
def test_new_language_compile_execute_and_errors(language):
    sandbox = DockerSandbox()
    snapshot = {
        "time_limit": 2,
        "mem_limit": 256,
        "tests": [
            {"input_data": "1 2", "expected": "3", "is_sample": True},
            {"input_data": "21 34", "expected": "55"},
        ],
    }
    result = judge(SOURCES[language], language, snapshot, sandbox=sandbox)
    assert result.verdict == "ACCEPTED", (result.error, result.tests)
    broken = judge("this is not valid source", language, snapshot, sandbox=sandbox)
    assert broken.verdict == "COMPILATION_ERROR", broken
