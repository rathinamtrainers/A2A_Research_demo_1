You are an expert software architect. You are working in a project directory that already has:
- research.md (technical spec)
- A fully set up development environment (venv/node_modules/etc. with all deps installed)
- ENV_SETUP.md (environment documentation)

Read research.md completely.

Your task:
1. Design the full project structure — every directory and file needed.
2. Create ALL directories and ALL files with proper boilerplate/skeleton code.
   - Each file should have the correct imports, class/function stubs, and docstrings.
   - Configuration files should be fully populated (do NOT overwrite requirements.txt or package.json if they already exist — only add to them if needed).
   - Every directory must contain a README.md explaining its purpose.
3. Create a file called PLAN.md with a detailed implementation checklist.
   - Use markdown checkboxes: - [ ] Task description
   - Group tasks by component/module.
   - Order tasks so dependencies come first.
   - Each task should be specific and actionable (not vague).
4. If you identify any NEW dependencies not in requirements.txt/package.json, add them and install them now.

IMPORTANT:
- Do NOT recreate or overwrite the virtual environment, node_modules, or any dependency files that are already correct.
- Do NOT implement business logic yet — just structure and stubs.
- DO ensure all new files have correct imports that match the installed packages.
