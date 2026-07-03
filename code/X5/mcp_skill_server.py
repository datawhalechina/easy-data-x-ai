from mcp.server.fastmcp import FastMCP

mcp = FastMCP("skill-mcp-demo")


@mcp.tool()
def review_code_diff(
    diff: str,
    focus: str = "correctness, maintainability, security, tests",
) -> str:
    """
    Review a code diff according to the code-review Skill checklist.

    Args:
        diff: Git diff, pull request diff, or changed code snippet.
        focus: Review focus areas.

    Returns:
        A structured review report grouped by severity.
    """
    return f"""# Code Review Result

## Focus
{focus}

## Input Summary
Received diff with {len(diff)} characters.

## Review Checklist
1. Correctness
2. Maintainability
3. Security
4. Tests
5. Compatibility
6. Project conventions

## Findings
- Critical: 暂无，需结合真实 diff 判断
- Major: 请检查核心逻辑、边界条件和异常路径
- Minor: 请检查命名、重复代码和可读性

## Suggested Next Steps
1. 补充或更新测试用例。
2. 重点检查 diff 中的输入校验、错误处理和兼容性影响。
3. 如果这是 PR，请结合 CI 日志和项目约定进一步审查。
"""


if __name__ == "__main__":
    mcp.run()
