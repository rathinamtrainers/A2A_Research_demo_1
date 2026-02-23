You are an expert DevOps engineer. You are working in the directory: /home/sandbox1/test2

Read the file research.md in the current directory. It contains a technical spec including the runtime, language, and all dependencies needed for the project.

Your task — set up the COMPLETE development environment from scratch:

1. Read research.md to identify the language, runtime, and all dependencies.

2. Based on the tech stack, do ALL of the following that apply:

   FOR PYTHON PROJECTS:
   - Create a virtual environment: python3 -m venv venv
   - Activate it and upgrade pip: source venv/bin/activate && pip install --upgrade pip setuptools wheel
   - Create a requirements.txt with ALL dependencies (pinned versions from research.md)
   - Install everything: pip install -r requirements.txt
   - If the project needs a pyproject.toml or setup.py, create it
   - Verify key packages imported correctly by running: python -c "import <package>"

   FOR NODE.JS PROJECTS:
   - Run npm init -y (or create package.json manually with proper metadata)
   - Install all dependencies: npm install <packages>
   - Install dev dependencies: npm install --save-dev <dev-packages>
   - Verify installation: node -e "require('<package>')"

   FOR GO PROJECTS:
   - Run go mod init <module-name>
   - Add dependencies with go get
   - Run go mod tidy

   FOR RUST PROJECTS:
   - Run cargo init or cargo new as appropriate
   - Add dependencies to Cargo.toml
   - Run cargo build to verify

   FOR ANY STACK:
   - Create .env.example with all required environment variables (with placeholder values)
   - Create .gitignore appropriate for the tech stack
   - If any system packages are needed that cannot be installed without sudo, list them in a file called SYSTEM_DEPS.md and note they need manual installation

3. Create a file called ENV_SETUP.md that documents:
   - How to activate the environment (e.g. source venv/bin/activate)
   - How to install dependencies
   - Any environment variables needed
   - Verification commands to check the setup

4. Verify the environment is working — run at least one import/require check for the main dependency.

IMPORTANT: Actually run every command. Do not just write files — execute the installs and verify they succeed.
