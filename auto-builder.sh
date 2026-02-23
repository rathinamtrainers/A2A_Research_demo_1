#!/bin/bash
# auto-builder.sh — Autonomous app builder using Claude CLI
#
# Usage: ./auto-builder.sh "Your high-level requirement here" [project-directory]
#
# Fully automatic: researches, sets up environment, plans, implements,
# writes tests, and fixes — all via claude -p with prompts piped via stdin.

set -euo pipefail

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
REQUIREMENT="${1:?Usage: ./auto-builder.sh \"requirement\" [project-dir]}"
PROJECT_DIR="${2:-.}"
MODEL="sonnet"
MAX_TEST_RETRIES=3

CLAUDE_FLAGS="--model $MODEL --dangerously-skip-permissions"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

run_phase() {
    local phase_name="$1"
    local prompt_file="$2"
    local log_file="$3"

    echo ""
    echo "========================================================================"
    echo "  [$(timestamp)] $phase_name"
    echo "========================================================================"
    echo "  Prompt: $prompt_file"
    echo "  Log:    $log_file"
    echo "  Command: cat $prompt_file | claude $CLAUDE_FLAGS -p"
    echo "========================================================================"
    echo ""

    cd "$PROJECT_DIR"
    cat "$prompt_file" | claude $CLAUDE_FLAGS -p 2>&1 | tee "$log_file"
    local exit_code=${PIPESTATUS[1]}

    echo ""
    if [ $exit_code -ne 0 ]; then
        echo "  [$(timestamp)] FAILED — $phase_name exited with code $exit_code"
        echo "  Check log: $log_file"
        exit $exit_code
    fi
    echo "  [$(timestamp)] DONE — $phase_name completed successfully"
    echo ""
}

# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------
mkdir -p "$PROJECT_DIR"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
LOG_DIR="${PROJECT_DIR}/build-logs"
PROMPT_DIR="${PROJECT_DIR}/build-prompts"
mkdir -p "$LOG_DIR"
mkdir -p "$PROMPT_DIR"

echo ""
echo "========================================================================"
echo "  Auto-Builder — Full Automatic Mode"
echo "========================================================================"
echo ""
echo "  Requirement : $REQUIREMENT"
echo "  Project dir : $PROJECT_DIR"
echo "  Model       : $MODEL"
echo "  Prompts     : $PROMPT_DIR"
echo "  Logs        : $LOG_DIR"
echo ""

# ---------------------------------------------------------------------------
# Write all prompt files
# ---------------------------------------------------------------------------

# Phase 1: Research
cat > "$PROMPT_DIR/phase1-research.md" << 'PROMPT_EOF'
You are an expert software architect. Your task is to research the following requirement and produce a detailed technical specification.

REQUIREMENT:
__REQUIREMENT__

Instructions:
1. Research the topic thoroughly using web search and your knowledge.
2. Identify ALL key features, concepts, and components that should be demonstrated or implemented.
3. For each feature, describe what it does and why it matters.
4. List the recommended tech stack, libraries, and dependencies with EXACT version numbers.
5. Note any setup requirements, API keys, or external services needed.
6. Specify the runtime needed (Python version, Node version, etc.).
7. Save your complete research to a file called research.md in the current directory.

The research.md file MUST contain these sections:
- Overview (what the project does)
- Runtime & Language (e.g. Python 3.11+, Node 20+, etc.)
- Tech Stack & Dependencies (every package with version, and the install commands)
- Features List (detailed breakdown of every feature to implement)
- Architecture Notes (how components fit together)
- Setup Requirements (env vars, API keys, external services)
- References (useful documentation links)

Be thorough — this document drives the entire build including environment setup.
PROMPT_EOF
sed -i "s|__REQUIREMENT__|$REQUIREMENT|g" "$PROMPT_DIR/phase1-research.md"

# Phase 2: Environment Setup
cat > "$PROMPT_DIR/phase2-env-setup.md" << PROMPT_EOF
You are an expert DevOps engineer. You are working in the directory: $PROJECT_DIR

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
PROMPT_EOF

# Phase 3: Plan & Scaffold
cat > "$PROMPT_DIR/phase3-plan.md" << 'PROMPT_EOF'
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
PROMPT_EOF

# Phase 4: Implement
cat > "$PROMPT_DIR/phase4-implement.md" << 'PROMPT_EOF'
You are an expert software developer. You are working in a project directory that has:
- research.md (technical spec)
- PLAN.md (implementation checklist)
- A fully set up development environment with all dependencies installed
- Scaffold files with stubs ready to be implemented

Your task:
1. Read PLAN.md to understand all tasks.
2. Read every existing source file to understand the scaffold.
3. Implement EVERY feature listed in PLAN.md, one by one.
4. After completing each task, update PLAN.md to check it off: change - [ ] to - [x].
5. Make sure all imports are correct, all functions work, and the code is complete and runnable.
6. If you discover missing dependencies:
   - Add them to requirements.txt / package.json / the appropriate config file.
   - INSTALL them now (pip install, npm install, etc.) — do not just list them.
7. Do NOT leave any placeholder, TODO, or stub — implement everything fully.
8. Do NOT write tests in this phase — focus purely on implementation.

IMPORTANT:
- For Python projects, activate the venv before running anything: source venv/bin/activate
- For Node projects, ensure you run commands from the project root where node_modules lives.
- Actually verify critical pieces work by running quick smoke checks (e.g., python -c 'from mymodule import main').

Work methodically through every item in PLAN.md. Do not skip anything.
PROMPT_EOF

# Phase 5: Write Tests
cat > "$PROMPT_DIR/phase5-tests.md" << 'PROMPT_EOF'
You are an expert software tester. You are working in a project directory with a fully implemented application and a complete development environment.

Your task:
1. Read PLAN.md and research.md to understand what was built.
2. Read ALL source files to understand the implementation.
3. Ensure the testing framework is installed:
   - For Python: pip install pytest pytest-cov pytest-asyncio (or whatever is appropriate) — activate venv first: source venv/bin/activate
   - For Node: npm install --save-dev jest (or mocha, vitest, etc.)
   - For other stacks: install the standard test runner
4. Write comprehensive tests covering every feature and component:
   - Unit tests for individual functions and classes.
   - Integration tests for component interactions.
   - Edge case tests for error handling and boundary conditions.
5. Place tests in a tests/ directory (or the project's conventional test location).
6. Make sure tests can be run with a single command and document that command in README.md.
7. Use mocks/stubs for external services (APIs, databases) so tests can run offline.
8. Do a quick sanity run of the tests to make sure the test runner itself works (even if some tests fail, the framework should execute).

Write thorough tests — they should catch real bugs, not just pass trivially.
PROMPT_EOF

# Phase 6: Run Tests & Fix
cat > "$PROMPT_DIR/phase6-fix.md" << 'PROMPT_EOF'
You are an expert software developer and debugger. You are working in a project directory with an implemented application, tests, and a fully set up development environment.

Your task:
1. Activate the environment if needed:
   - Python: source venv/bin/activate
   - Node: ensure node_modules exists
2. Identify the correct test command by reading the project files (look for pytest, jest, go test, etc.).
3. Run ALL tests.
4. If all tests pass, print EXACTLY this line at the end of your response: ALL_TESTS_PASSED
5. If any tests fail:
   a. Read the error output carefully.
   b. Identify the root cause of each failure — is it a bug in source code or in the test?
   c. Fix the code (source or test) as appropriate.
   d. If a fix requires a new dependency, install it now.
   e. Re-run the tests to verify your fixes.
   f. Repeat until all tests pass or you are confident in your fixes.
   g. If all tests pass after fixing, print EXACTLY: ALL_TESTS_PASSED
6. Do NOT disable, skip, or delete failing tests — fix the underlying issues.
PROMPT_EOF

# ---------------------------------------------------------------------------
# Execute all phases
# ---------------------------------------------------------------------------

# Phase 1
run_phase "Phase 1: Research" "$PROMPT_DIR/phase1-research.md" "$LOG_DIR/phase1-research.log"

if [ ! -f "$PROJECT_DIR/research.md" ]; then
    echo "ERROR: Phase 1 did not produce research.md — aborting."
    exit 1
fi
echo "  -> Verified: research.md exists"

# Phase 2
run_phase "Phase 2: Environment Setup" "$PROMPT_DIR/phase2-env-setup.md" "$LOG_DIR/phase2-env-setup.log"

# Phase 3
run_phase "Phase 3: Plan & Scaffold" "$PROMPT_DIR/phase3-plan.md" "$LOG_DIR/phase3-plan.log"

if [ ! -f "$PROJECT_DIR/PLAN.md" ]; then
    echo "ERROR: Phase 3 did not produce PLAN.md — aborting."
    exit 1
fi
echo "  -> Verified: PLAN.md exists"

# Phase 4
run_phase "Phase 4: Implement" "$PROMPT_DIR/phase4-implement.md" "$LOG_DIR/phase4-implement.log"

# Phase 5
run_phase "Phase 5: Write Tests" "$PROMPT_DIR/phase5-tests.md" "$LOG_DIR/phase5-tests.log"

# Phase 6: Retry loop
echo ""
echo "========================================================================"
echo "  [$(timestamp)] Phase 6: Run Tests & Fix (up to $MAX_TEST_RETRIES attempts)"
echo "========================================================================"
echo ""

TESTS_PASSED=false

for attempt in $(seq 1 $MAX_TEST_RETRIES); do
    echo "--- Attempt $attempt of $MAX_TEST_RETRIES ---"

    run_phase "Phase 6: Run Tests & Fix (attempt $attempt)" \
        "$PROMPT_DIR/phase6-fix.md" \
        "$LOG_DIR/phase6-attempt${attempt}.log"

    if grep -q "ALL_TESTS_PASSED" "$LOG_DIR/phase6-attempt${attempt}.log"; then
        echo ""
        echo "  [$(timestamp)] ALL TESTS PASSED on attempt $attempt!"
        TESTS_PASSED=true
        break
    fi

    if [ "$attempt" -eq "$MAX_TEST_RETRIES" ]; then
        echo ""
        echo "  WARNING: Tests did not fully pass after $MAX_TEST_RETRIES attempts."
        echo "  Check logs: $LOG_DIR/phase6-attempt*.log"
    fi
done

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo ""
echo "========================================================================"
echo "  [$(timestamp)] Auto-Builder Complete"
echo "========================================================================"
echo ""
echo "  Project dir  : $PROJECT_DIR"
echo "  Tests passed : $TESTS_PASSED"
echo ""
echo "  Generated files:"
find "$PROJECT_DIR" -type f \
    ! -path "*/build-logs/*" \
    ! -path "*/build-prompts/*" \
    ! -path "*/.git/*" \
    ! -path "*/venv/*" \
    ! -path "*/node_modules/*" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.pytest_cache/*" \
    ! -name "*.pyc" \
    ! -name "*.log" | sort | sed 's/^/    /'
echo ""
echo "  Build logs:"
ls -1 "$LOG_DIR/" | sed 's/^/    /'
echo ""
if [ "$TESTS_PASSED" = true ]; then
    echo "  SUCCESS — Project built and all tests passing!"
else
    echo "  PARTIAL — Project built but some tests may still be failing."
    echo "  Review phase 6 logs for details."
fi
echo ""
echo "  Project ready at: $PROJECT_DIR"
