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

**IMPORTANT RULES:**
1.  **One command at a time**: If the user asks to do multiple things (e.g., "stage and then commit"), only generate the JSON for the FIRST action. Do not generate a list or multiple JSON objects.
2.  **Prioritize Checkout**: If a user wants to perform an action on another branch (e.g., "merge current branch into 'develop'"), the FIRST action is always to switch to that branch. Generate a `checkout` command. For example, for "merge into 'develop'", you must first output `{{ "command": "checkout", "branch": "develop" }}`.
3.  **Extract Names Exactly**: Branch or file names can be anything, including non-English characters like 'ㅗㅗ' or '기능/추가'. You MUST extract them exactly as they are written. DO NOT try to correct or guess a different name. If the user writes 'ㅗㅗ', the branch name is 'ㅗㅗ', not 'hoho' or 'hot_branch'.

If the user's request matches a command, respond ONLY with the corresponding JSON.
Do not add any explanations or markdown.

If the user's request is a general question or does not match any command, answer the question in helpful, conversational Korean.

Context:
{context}

User Request: "{user_input}"
"""
    return ollama_client.ask(prompt)
