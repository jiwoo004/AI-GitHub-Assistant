"""Advanced AI features for AI Git Assistant.

- Merge conflict analysis
- Code review
- General Q&A
- Diff explanation
"""

from backend import ollama_client


def analyze_merge_conflict(conflict_content: str, context: str = "") -> str:
    """Analyze merge conflict and suggest resolution.
    
    Args:
        conflict_content: The conflicted code section (including <<<<<<< >>>>>>)
        context: Additional context (file path, branch names, etc.)
    
    Returns:
        AI explanation and suggestion for resolution
    """
    prompt = f"""You are a Git merge conflict expert. Analyze the following merge conflict and provide:
1. What each side of the conflict is trying to do
2. Likely cause of the conflict
3. Recommended resolution strategy
4. Code example of resolved version (if applicable)

Context: {context}

Conflict:
```
{conflict_content}
```

Provide a concise, clear explanation in Korean."""
    
    return ollama_client.ask(prompt)


def review_code(code_content: str, file_path: str = "", focus: str = "") -> str:
    """Review code and provide suggestions.
    
    Args:
        code_content: The code to review
        file_path: File path context
        focus: Specific focus area (e.g., "performance", "security", "style")
    
    Returns:
        AI code review feedback
    """
    focus_str = f"Focus on {focus}." if focus else ""
    
    prompt = f"""You are an expert code reviewer. Review the following code and provide:
1. Potential issues (bugs, logic errors, edge cases)
2. Code quality suggestions (readability, maintainability)
3. Best practices recommendations
4. Specific improvements with code examples

File: {file_path}
{focus_str}

Code:
```
{code_content}
```

Provide constructive feedback in Korean."""
    
    return ollama_client.ask(prompt)


def explain_diff(diff_content: str, context: str = "") -> str:
    """Explain what a diff/patch does in human-readable terms.
    
    Args:
        diff_content: The unified diff format
        context: Additional context (PR description, issue, etc.)
    
    Returns:
        Human-readable explanation of the changes
    """
    prompt = f"""You are a code change explainer. Explain what this diff/patch does in clear, human-readable terms:

1. Summary of the change
2. What was removed and why
3. What was added and why
4. Impact of the change
5. Any potential concerns

Context: {context}

Diff:
```
{diff_content}
```

Provide a clear explanation in Korean suitable for a code review."""
    
    return ollama_client.ask(prompt)


def answer_question(question: str, context: str = "") -> str:
    """General Q&A about Git, code, development, etc.
    
    Args:
        question: User's question
        context: Additional context (file names, commands, etc.)
    
    Returns:
        AI answer
    """
    prompt = f"""You are a helpful Git and development assistant. Answer the following question clearly and concisely.

Context: {context}

Question: {question}

Provide a helpful answer in Korean."""
    
    return ollama_client.ask(prompt)


def interpret_command(user_input: str, context: str = "") -> str:
    """Interpret natural language user input into a structured git command.

    Args:
        user_input: The user's natural language command.
        context: Additional context (current branch, project state).

    Returns:
        A JSON string representing the command, or a plain text answer.
    """
    prompt = f"""You are an AI Git Assistant that translates natural language into executable commands.
Analyze the user's request and determine if it maps to one of the available commands.

Available commands and their JSON format:
- stage: Stage files.
  - `{{ "command": "stage", "files": ["file1.py", "all"] }}`
- commit: Commit staged files.
  - `{{ "command": "commit", "message": "Your commit message" }}`
- push: Push the current branch.
  - `{{ "command": "push" }}`
- pull: Pull changes for the current branch.
  - `{{ "command": "pull" }}`
- checkout: Switch to a different branch.
  - `{{ "command": "checkout", "branch": "branch-name" }}`
- merge: Merge a branch into the current branch.
  - `{{ "command": "merge", "branch": "branch-to-merge" }}`
- reset: Undo the last commit.
  - `{{ "command": "reset", "mode": "soft|hard" }}` (If the user just says "undo commit" or "cancel commit", default to "soft" unless they explicitly say "discard changes" or "hard".)
- check_status: Check for local or remote changes.
  - `{{ "command": "check_status" }}` (Use this for general questions like "anything to do?", "any updates?", "what should I do first?")

If the user's request matches a command, respond ONLY with the corresponding JSON.
Do not add any explanations or markdown.

If the user's request is a general question or does not match any command, answer the question in helpful, conversational Korean.

Context:
{context}

User Request: "{user_input}"
"""
    return ollama_client.ask(prompt)


def suggest_commit_messages(diff_content: str, context: str = "", count: int = 3) -> list:
    """Generate multiple detailed commit suggestions.
    
    Args:
        diff_content: The staged diff
        context: Additional context
        count: Number of suggestions to generate.
    
    Returns:
        A list of dicts, each with 'scope', 'subject', 'body'.
    """
    prompt = f"""You are a Git commit message expert. Based on this diff, suggest {count} distinct commit messages.

The format should be:
<기능/파일 등 범위>(<작업 내용 요약>)

Here are some good examples:
- 로그인 기능(백엔드 요청 기능 추가)
- 로그인 화면(이미지 추가)
- main.py(오타 수정)

Context: {context}

Diff:
```
{diff_content}
```

Respond in this exact JSON format (a list of {count} JSON objects, in Korean language).
The "scope" should be the feature or file name, and the "subject" should be a summary of the work.
The "body" should be a more detailed explanation if needed.

[
  {{
    "scope": "기능 또는 파일 이름 (반드시 한글)",
    "subject": "작업 내용 요약 (반드시 한글)",
    "body": "필요시 상세 설명 (반드시 한글)"
  }},
  ...
]"""
    
    try:
        import json
        response = ollama_client.ask(prompt)
        # Try to parse JSON response
        parsed = json.loads(response)
        # Ensure the result is a list
        if isinstance(parsed, dict):
            return [parsed]
        return parsed
    except Exception as e:
        # If parsing fails, return an error structure
        return [{"error": str(e), "raw_response": response}]


def summarize_history(history: list) -> str:
    """
    Analyze a list of commits and generate a summary.
    
    Args:
        history: A list of commit dicts from git_utils.get_commit_history.
    
    Returns:
        AI-generated summary of the recent history.
    """
    if not history:
        return "분석할 커밋 히스토리가 없습니다."

    # Format the history for the prompt
    history_text = "\n".join([f"- {c['subject']} (by {c['author']}, {c['date']})" for c in history])

    prompt = f"""You are a project manager AI. Analyze the following recent commit history and provide a high-level summary of the project's progress.

Focus on:
1.  What major features were added?
2.  What important bugs were fixed?
3.  What is the general development trend?

Recent Commits:
{history_text}

Provide the summary in Korean."""
    
    return ollama_client.ask(prompt)
